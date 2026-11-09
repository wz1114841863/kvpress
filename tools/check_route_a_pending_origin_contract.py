#!/usr/bin/env python3
"""Check proposed pending-object/member provenance; no RTL, ML or EDA work.

The catalogue is an abstract coherent owner-state service. Its observations
are trusted accepted lifecycle facts, not client-supplied authority grants.
Capacity/ports and a real RTL producer remain outside this contract check.
"""

import argparse
from dataclasses import asdict, dataclass, replace
import heapq
import json
from pathlib import Path

from check_route_a_registration_window_contract import explore


@dataclass(frozen=True)
class Data:
    epoch: int
    entry_id: int
    layer: int
    head: int
    position: int
    payload_ref: int
    handle: int
    storage_generation: int
    endpoint: int
    creation_identity: tuple

    @property
    def identity(self):
        return self.epoch, self.entry_id


@dataclass(frozen=True)
class Descriptor:
    epoch: int
    reference: int
    generation: int
    data_identity: tuple
    pending_ordinal: int
    source_last: bool
    valid_count: int = 1

    @property
    def identity(self):
        return self.epoch, self.reference, self.generation


@dataclass(frozen=True)
class Request:
    data: Data
    descriptor: Descriptor
    attention_identity: tuple
    source_instance: tuple
    mode: str = "object"
    window: tuple | None = None
    ordinal: int | None = None
    count: int | None = None


class OwnerReference:
    """New owner-service contract reference, not the existing v1 owner."""

    def __init__(self, epoch=7):
        self.epoch = epoch
        self.data = {}
        self.descriptors = {}
        self.pending = set()
        self.links = {}
        self.active_window = (epoch, 0)
        self.closed_through = -1

    def observe_maturity(self, data, descriptor):
        # Caller must supply an accepted Hot->Pending observation once per
        # entry/session plus immutable location/builder facts. This reference
        # does not implement a replay-history table to enforce that premise.
        assert data.epoch == descriptor.epoch == self.epoch
        assert data.identity == descriptor.data_identity
        assert data.entry_id == data.position * 288 + data.layer * 8 + data.head
        assert data.identity not in self.data
        assert descriptor.identity not in self.descriptors
        assert descriptor.valid_count == 1
        self.data[data.identity] = data
        self.descriptors[descriptor.identity] = descriptor
        self.pending.add(data.identity)

    def observe_ingress(self, identity, window, ordinal, count):
        # This is a real accepted ingress triple with a matching immutable
        # data/location witness, not a registration choosing its own group.
        assert identity in self.pending and window == self.active_window
        assert 0 <= ordinal < count <= 64 and identity not in self.links
        assert not any(link == (window, ordinal, count) for link in self.links.values())
        self.links[identity] = (window, ordinal, count)

    def observe_packed(self, identity):
        # All real accepted R6 transitions revoke new reads, even if the
        # legacy R3 Valid-only binding-qualified withdrawal is absent.
        assert identity in self.pending
        self.pending.remove(identity)

    def classify(self, request, selected_attention, selected_instance, selected_descriptor):
        if request.data.epoch != self.epoch or request.descriptor.epoch != self.epoch:
            return "StaleNamespace"
        if (request.attention_identity != selected_attention or
                request.source_instance != selected_instance or
                request.descriptor.identity != selected_descriptor):
            return "BadServicePair"
        if request.source_instance[0] != 1:
            return "BadServiceKind"
        if request.mode == "member":
            if request.window is None or request.window[0] != self.epoch:
                return "StaleNamespace"
            if request.window[1] <= self.closed_through:
                return "Closed"
            if request.window != self.active_window:
                return "WrongWindow"
        elif request.mode != "object" or any(
                value is not None for value in (request.window, request.ordinal, request.count)):
            return "MalformedScope"
        stored_descriptor = self.descriptors.get(request.descriptor.identity)
        if stored_descriptor is None:
            return "NotLiveDescriptor"
        if stored_descriptor != request.descriptor:
            return "NotOwned"
        if (request.descriptor.data_identity != request.data.identity or
                self.data.get(request.data.identity) != request.data):
            return "NotOwned"
        if request.data.identity not in self.pending:
            return "NotPending"
        if request.mode == "member" and self.links.get(request.data.identity) != (
                request.window, request.ordinal, request.count):
            return "NotMember"
        return "PendingVerified"

    def evict_packed(self, identity):
        # Permitted only after all old references have drained or have exact
        # independent custody. The tests choose the no-reference case.
        assert identity not in self.pending
        self.data.pop(identity)
        self.descriptors = {k: d for k, d in self.descriptors.items() if d.data_identity != identity}
        self.links.pop(identity, None)


@dataclass(frozen=True)
class Cut:
    a_packed: bool = False
    directory_commit: bool = False
    producer_sealed: bool = False
    ready: bool = False
    closing: bool = False
    queried: int = 0
    query_target: int = 0  # 1=A in G0; 2=B unrelated pending
    query_stage: int = 0  # idle, unresolved directory lookup, exact snapshot held
    query_value: bool = False
    query_revoked: bool = False
    query_poisoned: bool = False
    context: int = 0
    revoked: bool = False
    issued: bool = False
    terminal: bool = False
    a_handed_off: bool = False
    close_acks: int = 0
    next_open: bool = False
    b_bound_to_g1: bool = False
    illegal_permit: bool = False
    b_revoked: bool = False
    held_payload_changed: bool = False


def cut_steps(s, policy=""):
    if not s.a_packed:
        yield "true-R6-pack-A/local-revocation", replace(
            s, a_packed=True,
            revoked=s.revoked or s.context == 1,
            query_revoked=s.query_revoked or (s.query_stage == 2 and s.query_target == 1))
    if s.a_packed and not s.directory_commit:
        yield "coherent-directory-A-NotPending-ACK", replace(s, directory_commit=True)
    if s.a_packed and not s.producer_sealed:
        yield "G0-producer-projection-seal", replace(s, producer_sealed=True)
    if s.a_packed and not s.ready:
        yield "R5-ready-and-notice-custody", replace(s, ready=True)
    if s.producer_sealed and not s.closing:
        yield "close-cut/stop-new-unresolved-lookups", replace(s, closing=True)
    if not s.query_stage and (not s.closing or s.next_open):
        for target in (1, 2):
            bit = 1 << (target - 1)
            if not s.queried & bit:
                # An external proof may be stale until the directory ACK;
                # the receiver still rechecks against the local R6 shadow.
                value = target == 2 or not s.directory_commit
                yield f"lookup[{target}]-fire/target-unresolved", replace(
                    s, queried=s.queried | bit, query_target=target,
                    query_stage=1, query_value=value, query_revoked=False,
                    query_poisoned=False)
    if s.query_stage == 1:
        revoked = s.query_target == 1 and s.a_packed
        value = s.query_value
        if s.query_poisoned:
            revoked = False
        yield "resolve-D-to-E/full-stable-snapshot", replace(
            s, query_stage=2, query_revoked=revoked, query_value=value)
    if s.query_stage == 2:
        allowed = s.query_value and not s.query_revoked
        if policy == "trust_stale_positive":
            allowed = s.query_value
        if not allowed:
            yield "consume-explicit-negative/no-Unseen", replace(s, query_stage=0)
        elif not s.context:
            illegal = s.query_target == 1 and s.a_packed
            # After old shadows are discarded, a wrongly undrained stale
            # reply could appear to name a fresh object. Correct close never
            # leaves an unresolved response from that cut.
            if s.query_poisoned:
                illegal = True
            yield "accept-verified-pending-context", replace(
                s, query_stage=0, context=s.query_target, revoked=False,
                issued=False, terminal=False, illegal_permit=illegal)
    if s.context and not s.issued and not s.revoked:
        if s.context == 2 or not s.a_packed:
            yield "joint-issue/recheck-positive-owner-fact", replace(s, issued=True)
    if s.context and s.issued and not s.terminal:
        yield "matching-typed-terminal", replace(s, terminal=True)
    if s.context and ((s.revoked and not s.issued) or s.terminal):
        yield "real-cancel-or-source-drain-ACK", replace(
            s, context=0, revoked=False, issued=False, terminal=False)
    a_query_safe = s.query_stage != 1 and (
        not s.query_stage or s.query_target != 1 or s.query_revoked)
    a_context_safe = s.context != 1 or s.revoked
    if s.closing and s.a_packed and a_query_safe and a_context_safe and not s.a_handed_off:
        yield "A-custody-ACK/retain-sticky-query-and-context", replace(s, a_handed_off=True)
    safe = (s.closing and s.a_packed and s.directory_commit and s.ready and
            s.producer_sealed and s.a_handed_off and a_query_safe and a_context_safe)
    if policy == "ignore_unresolved_directory_query":
        safe = (s.closing and s.a_packed and s.directory_commit and s.ready and s.producer_sealed)
    if safe:
        for bit, event in ((1, "R3-journal-close-ACK"), (2, "ingress-close-ACK")):
            if not s.close_acks & bit:
                yield event, replace(s, close_acks=s.close_acks | bit)
    if s.close_acks == 3 and not s.next_open:
        change = dict(next_open=True)
        if policy == "global_revoke_on_G0_close":
            change.update(b_revoked=True)
        if policy == "ignore_unresolved_directory_query" and s.query_stage == 1:
            change.update(query_poisoned=True)
        yield "open-G1/only-G0-projection-released", replace(s, **change)
    if s.next_open and not s.b_bound_to_g1:
        yield "real-ingress-B-to-G1/same-data-and-descriptor", replace(s, b_bound_to_g1=True)
    if policy == "rewrite_held_reply" and s.query_stage == 2 and s.query_value and s.query_revoked:
        yield "wrongly-rewrite-held-valid-payload", replace(s, query_value=False, held_payload_changed=True)


def cut_error(s):
    if s.illegal_permit:
        return "stale lookup result granted a new pending context after real packing"
    if s.b_revoked:
        return "closing G0 revoked unrelated still-pending B"
    if s.held_payload_changed:
        return "revocation mutated an independently held reply payload"
    if s.close_acks and not s.next_open and s.query_stage == 1:
        return "close ACK crossed an unresolved D-to-E lookup"
    if s.next_open and s.close_acks != 3:
        return "new group opened before two-sided close"
    if s.context == 1 and s.a_packed and not s.revoked:
        return "old A context lost its sticky revocation"
    return None


def run():
    if not __debug__:
        raise RuntimeError("Run without -O: contract checks require enabled assertions")
    owner = OwnerReference()
    a = Data(7, 0, 0, 0, 0, (1 << 63) + 5, (1 << 62) + 9, 3, 2, (1, 0))
    b = Data(7, 288, 0, 0, 1, (1 << 61) + 7, (1 << 60) + 11, 4, 2, (2, 0))
    da = Descriptor(7, 3, 1, a.identity, 9, False)
    db = Descriptor(7, 4, 1, b.identity, 10, True)
    owner.observe_maturity(a, da)
    owner.observe_maturity(b, db)
    owner.observe_ingress(a.identity, (7, 0), 0, 1)
    ra = Request(a, da, (3, 1), (1, 123, 5))
    rb = Request(b, db, (4, 2), (1, 456, 6))
    classify = lambda r: owner.classify(r, r.attention_identity, r.source_instance, r.descriptor.identity)
    positives = {}
    positives["member_before_R3_admission"] = classify(replace(ra, mode="member", window=(7, 0), ordinal=0, count=1))
    positives["unbound_pending_no_current_group"] = classify(rb)
    positives["same_member_via_object_route"] = classify(ra)
    positives["new_attention_same_immutable_descriptor"] = classify(replace(ra, attention_identity=(5, 2), source_instance=(1, 999, 7)))
    assert all(v == "PendingVerified" for v in positives.values())
    rejected = {}
    for field, value in asdict(a).items():
        changed = (0, 0) if field == "creation_identity" else value ^ 1
        rejected["data_" + field] = classify(replace(ra, data=replace(a, **{field: changed})))
    for field, value in asdict(da).items():
        changed = (7, 999) if field == "data_identity" else (not value if isinstance(value, bool) else value ^ 1)
        rejected["descriptor_" + field] = classify(replace(ra, descriptor=replace(da, **{field: changed})))
    rejected["relabel_B_as_G0_member"] = classify(replace(rb, mode="member", window=(7, 0), ordinal=0, count=1))
    rejected["wrong_service_identity"] = owner.classify(ra, (0, 0), ra.source_instance, da.identity)
    rejected["wrong_selected_instance"] = owner.classify(ra, ra.attention_identity, (1, 0, 0), da.identity)
    rejected["wrong_selected_descriptor"] = owner.classify(rb, rb.attention_identity, rb.source_instance, da.identity)
    rejected["wrong_source_kind"] = classify(replace(ra, source_instance=(0, 123, 5)))
    assert all(v != "PendingVerified" for v in rejected.values())
    assert all(v != "Unseen" for v in rejected.values())
    assert owner.descriptors[da.identity].source_last is False
    owner.observe_packed(a.identity)
    owner.closed_through = 0
    owner.active_window = (7, 1)
    late = {"old_member": classify(replace(ra, mode="member", window=(7, 0), ordinal=0, count=1)),
            "old_object": classify(ra),
            "old_relabelled_as_G1": classify(replace(ra, mode="member", window=(7, 1), ordinal=0, count=1)),
            "unrelated_B_after_G0_close": classify(rb)}
    assert late["unrelated_B_after_G0_close"] == "PendingVerified"
    assert all(late[k] != "PendingVerified" for k in late if k != "unrelated_B_after_G0_close")
    owner.evict_packed(a.identity)
    assert classify(ra) == "NotLiveDescriptor"
    owner.observe_ingress(b.identity, (7, 1), 0, 1)
    assert classify(replace(rb, mode="member", window=(7, 1), ordinal=0, count=1)) == "PendingVerified"
    assert owner.descriptors[db.identity] == db
    # Real authority revocation is not conditional on an R3 journal hit.
    owner.observe_packed(b.identity)
    assert classify(rb) == "NotPending"
    covers = {
        "unbound_B_context_survives_G0_close": lambda s: s.next_open and s.context == 2 and not s.revoked,
        "held_B_snapshot_survives_G0_close": lambda s: s.next_open and s.query_stage == 2 and s.query_target == 2,
        "A_lease_survives_G0_close": lambda s: s.next_open and s.context == 1 and s.issued and not s.terminal,
        "A_old_positive_snapshot_held_with_sticky_revoke": lambda s: s.next_open and s.query_stage == 2 and s.query_target == 1 and s.query_value and s.query_revoked,
        "B_later_binds_G1": lambda s: s.b_bound_to_g1,
        "directory_ACK_waits_for_local_shadow": lambda s: s.a_packed and not s.directory_commit and s.query_stage == 2 and s.query_target == 1 and s.query_revoked,
    }
    graph = explore(Cut(), cut_steps, cut_error, lambda s: s.next_open and s.b_bound_to_g1, covers)
    assert graph["verdict"] == "PASS" and graph["states_without_a_completion_path"] == 0
    assert set(graph["coverage"]) == set(covers)
    bad = {}
    for policy in ("trust_stale_positive", "ignore_unresolved_directory_query",
                   "global_revoke_on_G0_close", "rewrite_held_reply"):
        bad[policy] = explore(Cut(), lambda s: cut_steps(s, policy), cut_error, lambda s: s.next_open)
    assert all(r["verdict"] == "COUNTEREXAMPLE" for r in bad.values())
    # Synthetic scalar witness of the existing shared service budget. No
    # predictor is run and no frozen mask/workload is replaced.
    heads, tokens, hot, budget = 8, 1024, 128, 512
    queue = [(0, head) for head in range(heads)]
    heapq.heapify(queue)
    admitted = [0] * heads
    for _ in range(budget):
        position, head = heapq.heappop(queue)
        admitted[head] += 1
        if position + 1 < tokens - hot:
            heapq.heappush(queue, (position + 1, head))
    residual = [(tokens - hot) - n for n in admitted]
    assert admitted == [64] * 8 and residual == [832] * 8
    return {"schema": "route_a_pending_origin_contract_model_v1",
            "verdict": "PROPOSED_CONTRACT_CHECK_PASS_NOT_RTL_QUALIFICATION",
            "positive_identity_cases": positives, "negative_identity_cases": rejected,
            "late_and_unrelated_cases": late, "finite_graph": graph, "bad_policy_counterexamples": bad,
            "synthetic_budget_witness": {"heads": heads, "tokens": tokens, "hot": hot, "budget": budget,
                                         "mask": "synthetic keep-all, not an evaluated predictor mask",
                                         "matured_records": (tokens - hot) * heads,
                                         "admitted_per_head": admitted, "pending_per_head": residual,
                                         "pending_total": sum(residual)},
            "assumptions": ["data birth is an actual once-per-entry Hot-to-Pending fact plus immutable location facts",
                            "coherent owner catalogue and bounded query/context holding exist; no client can create/update catalogue facts",
                            "new direct issue rechecks pending state at the joint edge; old issued leases retain their records",
                            "unknown D-to-E lookups drain before group close; known snapshots retain full immutable facts and independent sticky revocation",
                            "catalogue removal/reuse requires real drain or exact independent custody and safe namespace/key reuse"],
            "not_proved": ["actual external producer or RTL implements this service", "catalogue capacity/ports/area or full32K coverage",
                           "arbitrary physical memory latency or coherency implementation", "whole-DUT equivalence or 2ns closure",
                           "multi-record direct-source continuation and all fault/retire/reset/wrap cuts"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, help="Write only the finite contract evidence")
    args = parser.parse_args()
    result = run()
    if args.output_json:
        args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verdict": result["verdict"], "states": result["finite_graph"]["states"],
                      "transitions": result["finite_graph"]["transitions"],
                      "positive_identity_cases": len(result["positive_identity_cases"]),
                      "negative_identity_cases": len(result["negative_identity_cases"]),
                      "counterexamples": len(result["bad_policy_counterexamples"]),
                      "synthetic_pending_total": result["synthetic_budget_witness"]["pending_total"]}))


if __name__ == "__main__":
    main()
