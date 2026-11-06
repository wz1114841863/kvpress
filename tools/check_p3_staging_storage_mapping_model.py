#!/usr/bin/env python3
"""Finite-state P3 port-scheduling assessment; no RTL or EDA execution.

The reference models two unreset payload words with binary data and the
current no-replace write-ack/read-response protocol. The candidate uses one
1RW macro action per edge, a one-word deferred-write buffer and a read-Q
holding adapter. This is an abstract feasibility check, not RTL equivalence
or macro timing evidence. Same-address read/write behavior is not specified
by the source Mem contract, so the principal check excludes that collision;
a separate old-data extension is checked and labeled explicitly.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
import hashlib
from itertools import product
import json
from pathlib import Path


@dataclass(frozen=True)
class Reference:
    memory: tuple[int, int]
    write_ack: int | None = None
    read_rsp: tuple[int, int] | None = None


@dataclass(frozen=True)
class Candidate:
    memory: tuple[int, int]
    write_ack: int | None = None
    read_tag: int | None = None
    fresh: bool = False
    hold: int = 0
    macro_q: int = 0
    deferred: tuple[int, int] | None = None


WRITES = (None, (0, 0), (0, 1), (1, 0), (1, 1))
READS = (None, 0, 1)
# Arbitrary Q on a macro write tests that a stalled response is held outside
# the macro. No particular SRAM write-output mode is assumed.
ACTIONS = tuple(product(WRITES, READS, (False, True), (False, True),
                        (False, True), (0, 1)))


def store(memory: tuple[int, int], address: int, value: int) -> tuple[int, int]:
    return (value, memory[1]) if address == 0 else (memory[0], value)


def logical_memory(candidate: Candidate) -> tuple[int, int]:
    if candidate.deferred is None:
        return candidate.memory
    return store(candidate.memory, *candidate.deferred)


def same_observations(reference: Reference, candidate: Candidate, variant: str) -> bool:
    # Request ready is exactly the inverse of the corresponding pending flag.
    if reference.write_ack != candidate.write_ack:
        return False
    if (reference.read_rsp is None) != (candidate.read_tag is None):
        return False
    if reference.read_rsp is not None:
        data = candidate.macro_q if candidate.fresh or variant == 'live_q' else candidate.hold
        if reference.read_rsp != (candidate.read_tag, data):
            return False
    return reference.memory == logical_memory(candidate)


def transition(reference: Reference, candidate: Candidate, action: tuple,
               variant: str, collision_mode: str):
    write, read, write_ready, read_ready, reset, write_q = action
    write_fire = write is not None and reference.write_ack is None
    read_fire = read is not None and reference.read_rsp is None
    if collision_mode == 'nonalias' and write_fire and read_fire and write[0] == read:
        return None

    ref_memory = reference.memory
    ref_ack = None if write_ready else reference.write_ack
    ref_rsp = None if read_ready else reference.read_rsp
    if read_fire:
        ref_rsp = (read, reference.memory[read])
    if write_fire:
        ref_memory = store(ref_memory, *write)
        ref_ack = write[0]
    if reset:
        ref_ack = ref_rsp = None  # Mem bytes persist across synchronous reset.
    next_reference = Reference(ref_memory, ref_ack, ref_rsp)

    memory, q, deferred = candidate.memory, candidate.macro_q, None
    hold = candidate.macro_q if candidate.fresh else candidate.hold
    macro_actions = 0
    if candidate.deferred is not None:
        # The collision edge made BOTH protocol slots pending. The following
        # edge cannot accept another request, even if responses are consumed.
        assert not write_fire and not read_fire
        if not (variant == 'drop_on_reset' and reset):
            memory = store(memory, *candidate.deferred)
            q = write_q
            macro_actions = 1
    elif write_fire and (reset or not read_fire):
        # Reset cancels read responses, not Mem writes. Service a write at the
        # reset edge directly; never enqueue it into reset-cleared state.
        memory = store(memory, *write)
        q = write_q
        macro_actions = 1
    elif read_fire:
        q = memory[read]
        macro_actions = 1
        if write_fire and variant != 'drop_conflict':
            deferred = write
    assert macro_actions <= 1

    ack = None if write_ready else candidate.write_ack
    tag = None if read_ready else candidate.read_tag
    if write_fire:
        ack = write[0]
    if read_fire:
        tag = read
    if reset:
        ack = tag = None
    fresh = read_fire and not reset
    if tag is None:
        # Invalid payload/tag bits are outside the interface contract. This
        # canonicalization keeps the finite graph small, without clearing Mem.
        fresh, hold = False, 0
    next_candidate = Candidate(memory, ack, tag, fresh, hold, q, deferred)
    return next_reference, next_candidate, macro_actions


def explore(variant: str, collision_mode: str, max_states: int) -> dict:
    initial = [(Reference(m), Candidate(m)) for m in product((0, 1), repeat=2)]
    queue = deque(initial)
    seen = set(initial)
    parents = {state: None for state in initial}
    transitions = resets = collisions = drains = 0
    while queue:
        state = queue.popleft()
        for action in ACTIONS:
            result = transition(*state, action, variant, collision_mode)
            if result is None:
                continue
            ref, candidate, _ = result
            transitions += 1
            resets += bool(action[4])
            write_fire = action[0] is not None and state[0].write_ack is None
            read_fire = action[1] is not None and state[0].read_rsp is None
            collisions += write_fire and read_fire
            drains += state[1].deferred is not None
            successor = (ref, candidate)
            if not same_observations(ref, candidate, variant):
                trace = [action]
                cursor = state
                while parents[cursor] is not None:
                    cursor, previous_action = parents[cursor]
                    trace.append(previous_action)
                trace.reverse()
                return dict(pass_check=False, variant=variant, collision_mode=collision_mode,
                            states=len(seen), transitions=transitions,
                            initial_memory=cursor[0].memory, counterexample=trace)
            if successor not in seen:
                if len(seen) >= max_states:
                    raise RuntimeError('finite-state limit reached; no PASS may be claimed')
                seen.add(successor)
                parents[successor] = (state, action)
                queue.append(successor)
    return dict(pass_check=True, variant=variant, collision_mode=collision_mode,
                states=len(seen), transitions=transitions, reset_transitions=resets,
                simultaneous_read_write_transitions=collisions, deferred_drain_transitions=drains)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-json', type=Path, help='New result file; existing files are never overwritten')
    parser.add_argument('--max-states', type=int, default=20000)
    args = parser.parse_args()
    if args.output_json and args.output_json.exists():
        parser.error('output file already exists')
    checks = [explore('safe', mode, args.max_states) for mode in ('nonalias', 'old_data_extension')]
    negatives = [explore(name, 'nonalias', args.max_states)
                 for name in ('drop_conflict', 'drop_on_reset', 'live_q')]
    assert all(row['pass_check'] for row in checks)
    assert all(not row['pass_check'] for row in negatives)
    report = dict(schema_version='kvzap-p3-storage-mapping-finite-model-1.0',
                  status='abstract_model_pass_not_RTL_or_macro_closure',
                  model_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  counterexample_action_fields=['write_or_null', 'read_or_null',
                                                'write_ack_ready', 'read_rsp_ready',
                                                'synchronous_reset', 'arbitrary_write_q'],
                  model_domain=dict(payload_words=2, data_values=2,
                                    macro_operations_per_edge=1,
                                    reset='synchronous_protocol_clear_memory_persists',
                                    compare='ready_valid_valid_tags_data_and_overlay_memory',
                                    sidecar='separate_independent_write_lane_not_enumerated'),
                  checks=checks, negative_controls=negatives,
                  limits=['not_RTL_equivalence', 'not_general_state_space_proof',
                          'old_data_extension_not_source_Mem_collision_contract',
                          'no_physical_macro_latency_timing_area_or_energy_evidence'])
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'], checks=checks,
                          negative_controls_detected=[row['variant'] for row in negatives])))


if __name__ == '__main__':
    main()
