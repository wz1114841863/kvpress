#!/usr/bin/env python3
"""Check a finite continuation-plan abstraction; this is not an RTL proof."""

import argparse
from collections import deque
from dataclasses import asdict, dataclass, replace
from itertools import product
import json
from pathlib import Path


GROUPS = 2
MEMBERS = 2
NAMESPACE = 3


@dataclass(frozen=True)
class State:
    admitted: int = 1
    working: int = 0
    published: int = 0
    r6: int = 0
    collected: int = 0
    writes: int = 0
    acks: int = 0
    committed: int = 0
    ready: int = 0
    permitted: int = 0
    # cleared records the exact group's R3 close ACK and working-bank clear.
    cleared: int = 0
    ingress_closed: int = 0
    rearmed: int = 0
    reads: tuple = (0, 0)


def group_mask(group):
    return ((1 << MEMBERS) - 1) << (group * MEMBERS)


def binding(group, ordinal):
    """Opaque data are independent symbolic facts, not inferred addresses."""
    return dict(entry_id=ordinal * 288 + group * 8, layer=group, kv_head=0,
                logical_position=ordinal, request_id=group, incarnation=0,
                payload_ref=(group + ordinal) % 2, transaction_group_tag=group,
                group_member_ordinal=ordinal, group_valid_records=MEMBERS,
                payload_handle_or_address=(group ^ ordinal) % 2,
                source_generation=1, destination_endpoint=0)


def exact_lookup(state, namespace, query):
    if namespace != NAMESPACE:
        return "Unseen"
    for group in range(GROUPS):
        for ordinal in range(MEMBERS):
            if query != binding(group, ordinal):
                continue
            bit = 1 << (group * MEMBERS + ordinal)
            if state.working == group:
                return "TransitionedPacked" if state.r6 & bit else "PendingMember"
            if state.committed & (1 << group):
                return "TransitionedPacked"
    return "Unseen"


def visible_pages(state, policy):
    if policy == "last_page_only" and state.ready:
        return 1 << (state.ready.bit_length() - 1)
    return state.ready


def violation(state, policy):
    if state.admitted & 2 and not (state.cleared & 1 and state.ingress_closed & 1):
        return dict(invariant="no_G1_admission_before_both_G0_close_ACKs",
                    group=1, actual="admitted", expected="wait_for_exact_group_ACK_join")
    for group in range(GROUPS):
        group_bit = 1 << group
        mask = group_mask(group)
        if state.ready & group_bit:
            if state.r6 & mask != mask or state.collected & mask != mask:
                return dict(invariant="no_ready_before_all_R6_and_collector",
                            group=group, actual="ready", expected="not_ready")
            if not state.admitted & group_bit:
                return dict(invariant="ready_requires_live_allocated_page",
                            group=group, actual="ready", expected="not_ready")
            if not visible_pages(state, policy) & group_bit:
                return dict(invariant="published_old_page_remains_queryable",
                            group=group, actual="not_found", expected="ready")
        for ordinal in range(MEMBERS):
            bit = 1 << (group * MEMBERS + ordinal)
            expected = "Unseen"
            if state.admitted & group_bit:
                expected = "TransitionedPacked" if state.r6 & bit else "PendingMember"
            actual = exact_lookup(state, NAMESPACE, binding(group, ordinal))
            if actual != expected:
                return dict(invariant="exact_late_lookup_survives_working_clear",
                            group=group, member=ordinal, actual=actual, expected=expected)
            if exact_lookup(state, NAMESPACE + 1, binding(group, ordinal)) != "Unseen":
                return dict(invariant="namespace_isolation", group=group, member=ordinal)
            for field in ("payload_ref", "payload_handle_or_address", "source_generation"):
                wrong = dict(binding(group, ordinal))
                wrong[field] ^= 1
                if exact_lookup(state, NAMESPACE, wrong) != "Unseen":
                    return dict(invariant="exact_opaque_field_match", field=field)
    return None


def successors(state, policy):
    group = state.working
    if group >= 0:
        group_bit = 1 << group
        mask = group_mask(group)
        if not state.published & group_bit:
            yield "publish_G%d" % group, replace(state, published=state.published | group_bit)
        if state.published & group_bit:
            complete = state.r6 & mask == mask and state.collected & mask == mask
            for ordinal in range(MEMBERS):
                bit = 1 << (group * MEMBERS + ordinal)
                earlier = ((1 << ordinal) - 1) << (group * MEMBERS)
                # Publication members stay ordered. Archive follows all
                # completion; collector completion is a post-R6 joined fact.
                if state.r6 & earlier == earlier and state.collected & earlier == earlier:
                    if not state.r6 & bit:
                        yield "R6_accept_G%d_M%d" % (group, ordinal), replace(state, r6=state.r6 | bit)
                if state.r6 & bit and not state.collected & bit:
                    yield "collect_G%d_M%d" % (group, ordinal), replace(state, collected=state.collected | bit)
                # Wait until every R6/collector member is complete so this
                # stream can reuse the now-idle withdrawal journal read mux.
                if complete and not state.writes & bit and state.writes == state.acks:
                    yield "archive_write_G%d_M%d" % (group, ordinal), replace(state, writes=state.writes | bit)
                if state.writes & bit and not state.acks & bit:
                    yield "archive_ack_G%d_M%d" % (group, ordinal), replace(state, acks=state.acks | bit)
            if complete and state.acks & mask == mask and not state.committed & group_bit:
                yield "archive_group_commit_G%d" % group, replace(state, committed=state.committed | group_bit)
            # R5 readiness and journal archive are independent after the
            # joined R6 receipts. Reuse waits for both, but a read need not
            # wait for archive transport when the working history is live.
            ready_legal = complete
            if policy == "ready_at_visibility":
                ready_legal = True
            if ready_legal and not state.ready & group_bit:
                yield "install_R5_ready_G%d" % group, replace(state, ready=state.ready | group_bit)
            if state.ready & group_bit and state.committed & group_bit and not state.permitted & group_bit:
                yield "GroupReusePermit_G%d" % group, replace(state, permitted=state.permitted | group_bit)
            if policy == "clear_at_handoff" and complete:
                yield "clear_working_G%d_without_archive_commit" % group, replace(
                    state, working=-1, cleared=state.cleared | group_bit)
    # Both close messages/ACKs name the exact group. Their independent order
    # must not expose the next ingress before the controller joins both.
    for closing_group in range(GROUPS):
        bit = 1 << closing_group
        if not state.permitted & bit:
            continue
        if state.working == closing_group and not state.cleared & bit:
            yield "R3_close_ACK_G%d" % closing_group, replace(
                state, working=-1, cleared=state.cleared | bit)
        if not state.ingress_closed & bit:
            yield "ingress_close_ACK_G%d" % closing_group, replace(
                state, ingress_closed=state.ingress_closed | bit)
        close_joined = bool(state.cleared & bit and state.ingress_closed & bit)
        if policy == "early_rearm":
            close_joined = bool(state.ingress_closed & bit)
        if close_joined and not state.rearmed & bit:
            yield "controller_rearm_G%d" % closing_group, replace(state, rearmed=state.rearmed | bit)
    if (state.admitted == 1 and state.rearmed & 1 and
            (state.working == -1 or policy == "early_rearm")):
        yield "admit_G1", replace(state, admitted=3, working=1)
    for page in range(GROUPS):
        if visible_pages(state, policy) & (1 << page) and state.reads[page] < 2:
            reads = list(state.reads)
            reads[page] += 1
            yield "attention_read_G%d_%d" % (page, reads[page]), replace(state, reads=tuple(reads))


def goal(state):
    return (state.admitted == 3 and state.working == -1 and state.cleared == 3 and
            state.ingress_closed == 3 and state.rearmed == 3 and state.ready == 3)


def path_to(state, parents):
    events = []
    while parents[state] is not None:
        previous, event = parents[state]
        events.append(event)
        state = previous
    return list(reversed(events))


def explore(policy):
    initial = State()
    queue = deque([initial])
    parents = {initial: None}
    transitions = 0
    examined = 0
    goals = 0
    deadlocks = 0
    coverage = dict(second_group_admitted_without_attention=False,
                    both_groups_archived_and_working_cleared=False,
                    old_page_read_after_second_page_ready=False,
                    both_pages_read_twice=False,
                    ingress_close_ACK_before_R3=False,
                    R3_close_ACK_before_ingress=False)
    while queue:
        state = queue.popleft()
        examined += 1
        error = violation(state, policy)
        if error:
            return dict(policy=policy, result="COUNTEREXAMPLE", states_examined=examined,
                        states_discovered=len(parents), transitions_examined=transitions,
                        counterexample=dict(error, events=path_to(state, parents), state=asdict(state)))
        coverage["second_group_admitted_without_attention"] |= state.admitted == 3 and state.reads == (0, 0)
        coverage["both_groups_archived_and_working_cleared"] |= goal(state)
        coverage["both_pages_read_twice"] |= goal(state) and state.reads == (2, 2)
        coverage["ingress_close_ACK_before_R3"] |= bool(state.ingress_closed & 1) and not bool(state.cleared & 1)
        coverage["R3_close_ACK_before_ingress"] |= bool(state.cleared & 1) and not bool(state.ingress_closed & 1)
        if goal(state):
            goals += 1
        children = list(successors(state, policy))
        if not children and not goal(state):
            deadlocks += 1
        for event, following in children:
            transitions += 1
            if state.ready == 3 and event.startswith("attention_read_G0_"):
                coverage["old_page_read_after_second_page_ready"] = True
            if following not in parents:
                parents[following] = (state, event)
                queue.append(following)
    return dict(policy=policy, result="NO_MISMATCH_IN_FINITE_MODEL", states_examined=examined,
                states_discovered=len(parents), transitions_examined=transitions, mismatches=0,
                deadlocks=deadlocks, goal_states=goals, coverage=coverage)


ARCHIVE_KEY_FIELDS = (
    ("entry_id", 24), ("layer", 6), ("kv_head", 3), ("logical_position", 15),
    ("request_id", 3), ("incarnation", 2), ("payload_ref", 64),
    ("transaction_group_tag", 8), ("group_member_ordinal", 7),
    ("group_valid_records", 7), ("payload_handle_or_address", 64),
    ("source_generation", 8), ("destination_endpoint", 3),
)
ARCHIVE_META_FIELDS = (("state", 2), ("namespace_epoch", 32), ("reserved", 8))


def pack_archive_record(key, state=2, namespace_epoch=NAMESPACE, reserved=0):
    """Keep the full exact key; no coordinate or opaque-field derivation."""
    assert set(key) == {name for name, _ in ARCHIVE_KEY_FIELDS}
    word = 0
    shift = 0
    values = dict(key, state=state, namespace_epoch=namespace_epoch, reserved=reserved)
    for name, width in ARCHIVE_KEY_FIELDS + ARCHIVE_META_FIELDS:
        value = values[name]
        assert isinstance(value, int) and 0 <= value < 1 << width, name
        word |= value << shift
        shift += width
    assert shift == 256
    return word


def unpack_archive_record(word):
    assert isinstance(word, int) and 0 <= word < 1 << 256
    fields = {}
    shift = 0
    for name, width in ARCHIVE_KEY_FIELDS + ARCHIVE_META_FIELDS:
        fields[name] = (word >> shift) & ((1 << width) - 1)
        shift += width
    return fields


def archive_record_matches(word, namespace_epoch, query):
    fields = unpack_archive_record(word)
    # Completed archives carry TransitionedPacked=2. Other response-state
    # policies belong to the real service contract, not this codec check.
    return (fields["state"] == 2 and fields["reserved"] == 0 and
            fields["namespace_epoch"] == namespace_epoch and
            all(query[name] == fields[name] for name, _ in ARCHIVE_KEY_FIELDS))


def archive_format_key_fidelity_check():
    assert sum(width for _, width in ARCHIVE_KEY_FIELDS) == 214
    assert 214 + sum(width for _, width in ARCHIVE_META_FIELDS) == 256
    names = tuple(name for name, _ in ARCHIVE_KEY_FIELDS)
    positive = 0
    negative = 0
    namespace_negative = 0
    invalid_state_negative = 0
    reserved_negative = 0
    for values in product((0, 1), repeat=len(names)):
        original = dict(zip(names, values))
        packed = pack_archive_record(original)
        restored = unpack_archive_record(packed)
        assert all(restored[name] == value for name, value in original.items())
        assert archive_record_matches(packed, NAMESPACE, original)
        positive += 1
        for field in names:
            wrong = dict(original)
            wrong[field] ^= 1
            assert not archive_record_matches(packed, NAMESPACE, wrong), field
            negative += 1
        assert not archive_record_matches(packed, NAMESPACE + 1, original)
        namespace_negative += 1
        assert not archive_record_matches(pack_archive_record(original, state=3), NAMESPACE, original)
        invalid_state_negative += 1
        assert not archive_record_matches(pack_archive_record(original, reserved=1), NAMESPACE, original)
        reserved_negative += 1

    zero = {name: 0 for name in names}
    boundary_keys = {tuple(zero[name] for name in names)}
    boundary_keys.add(tuple((1 << width) - 1 for _, width in ARCHIVE_KEY_FIELDS))
    for name, width in ARCHIVE_KEY_FIELDS:
        for value in (1, (1 << width) - 2, (1 << width) - 1):
            key = dict(zero)
            key[name] = value
            boundary_keys.add(tuple(key[name] for name in names))
    # Exercise the two independent 64-bit values at opposite extremes as
    # well as their high bits; no shared-base/alignment assumption is used.
    for payload, handle in product((0, 1, 1 << 63, (1 << 64) - 1), repeat=2):
        key = dict(zero, payload_ref=payload, payload_handle_or_address=handle)
        boundary_keys.add(tuple(key[name] for name in names))
    boundary_roundtrips = 0
    for values in sorted(boundary_keys):
        key = dict(zip(names, values))
        for state, epoch, reserved in product(range(4), (0, 1, 1 << 31, (1 << 32) - 1), (0, 1, 255)):
            packed = pack_archive_record(key, state, epoch, reserved)
            restored = unpack_archive_record(packed)
            assert all(restored[name] == value for name, value in key.items())
            assert restored["state"] == state and restored["namespace_epoch"] == epoch
            assert restored["reserved"] == reserved
            assert archive_record_matches(packed, epoch, key) == (state == 2 and reserved == 0)
            boundary_roundtrips += 1

    range_rejections = 0
    for name, width in ARCHIVE_KEY_FIELDS + ARCHIVE_META_FIELDS:
        for value in (-1, 1 << width):
            key = dict(zero)
            meta = dict(state=2, namespace_epoch=NAMESPACE, reserved=0)
            if name in key:
                key[name] = value
            else:
                meta[name] = value
            try:
                pack_archive_record(key, **meta)
            except AssertionError:
                range_rejections += 1
            else:
                raise AssertionError("out-of-range field accepted: " + name)
    return dict(result="FINITE_FULL_KEY_ARCHIVE_FORMAT_PASS", selected_record_bytes=32,
                exact_key_bits=214, state_bits=2, namespace_epoch_bits=32, reserved_bits=8,
                record_bits=256, coordinate_fields_retained=True,
                independent_opaque_fields_retained=True, field_widths=dict(ARCHIVE_KEY_FIELDS),
                positive_exact_queries=positive, single_field_negative_queries=negative,
                namespace_negative_queries=namespace_negative,
                invalid_state_negative_queries=invalid_state_negative,
                reserved_bit_negative_queries=reserved_negative,
                boundary_key_vectors=len(boundary_keys), boundary_roundtrips=boundary_roundtrips,
                out_of_range_fields_rejected=range_rejections,
                limits="finite representation-level checks including width extremes and symbolic 0/1 fields; not legal-workload coverage, RTL equivalence, storage integrity/ECC or physical implementation proof")


def check():
    candidate = explore("candidate")
    assert candidate["result"] == "NO_MISMATCH_IN_FINITE_MODEL"
    assert candidate["mismatches"] == 0 and candidate["deadlocks"] == 0
    assert all(candidate["coverage"].values()), candidate["coverage"]
    negative = [explore(policy) for policy in ("clear_at_handoff", "ready_at_visibility", "last_page_only", "early_rearm")]
    assert all(item["result"] == "COUNTEREXAMPLE" for item in negative)
    return dict(schema="route-a-continuation-plan-model-1", evidence_class="finite_abstract_protocol_model",
                status="PASS_FINITE_PLAN_CHECK_ONLY", groups=GROUPS, members_per_group=MEMBERS,
                max_archive_writes_outstanding=1, read_count_limit_per_page=2,
                candidate=candidate, bad_organization_counterexamples=negative,
                archive_format=archive_format_key_fidelity_check(),
                assumptions=["bindings initially admitted atomically into one working bank",
                             "publication is the existing visibility event, not R6 acceptance",
                             "collector event represents an exact post-R6 joined receipt",
                             "ordered member acceptance; archive writes begin only after all R6/collector members complete",
                             "archive streaming reuses the completed group's idle withdrawal journal read mux",
                             "per-row ack and whole-group archive commit are explicit service events",
                             "archive is a new charged persistent backing, not the existing single-entry descriptor owner",
                             "admitted groups have live allocated pages with matching fixed generation",
                             "R5 ready installation follows all joined R6/collector receipts independently of archive commit",
                             "GroupReusePermit requires both archive commit and R5-ready acknowledgement",
                             "R3 close ACK clears working; ingress close ACK is separate, and both carry exact abstract group tags",
                             "controller rearms only after both exact-group close ACKs; only then may the next group enter",
                             "close ACK ordering is independent of attention consumption",
                             "namespace matches and retained pages remain live; no reset, retire or wrap in this model"],
                not_proven=["existing or successor RTL correctness", "full 32K capacity or maximum-live bound",
                            "timing at 2 ns", "numeric correctness", "fairness under an unresponsive environment",
                            "physical macro port implementation", "ready/valid RTL payload-holding implementation",
                            "full-bitwidth stale ACK/epoch/generation comparator implementation",
                            "mapped area, traffic, energy or net benefit"],
                production_RTL_modified=False, ML_model_or_EDA_loaded=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write the finite-model JSON receipt")
    args = parser.parse_args()
    result = check()
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": result["status"], "candidate": result["candidate"],
                      "negative_counterexamples": len(result["bad_organization_counterexamples"]),
                      "archive_format": result["archive_format"]}, indent=2))


if __name__ == "__main__":
    main()
