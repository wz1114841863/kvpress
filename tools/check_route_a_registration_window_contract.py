#!/usr/bin/env python3
"""Finite checks of a proposed registration-close contract, never an RTL proof.

No model weights, RTL compiler, remote service or EDA tool is used. Producer
freeze/seal, explicit offer rejection and owner handoff are NEW assumptions,
not properties inferred from the existing v1 ports.
"""

import argparse
from collections import deque
from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path


@dataclass(frozen=True)
class Window:
    mature: int = 0
    admitted: int = 0
    transitioned: int = 0
    frozen: bool = False
    producer: str = "unborn"
    accepted: bool = False
    query: int = 0  # none, needs journal, complete snapshot held, delivered
    reply: int = -1  # Unseen=0, PendingMember=1, TransitionedPacked=2
    revoked: bool = False
    sealed: bool = False
    ready: bool = False
    transferred: bool = False
    close_acks: int = 0
    next_open: bool = False


def window_steps(s, members, mutant=""):
    full = (1 << members) - 1
    if s.next_open:
        return
    for i in range(members):
        bit = 1 << i
        if not s.mature & bit and not s.frozen:
            producer = "queued" if i == 0 and s.producer == "unborn" else s.producer
            yield f"maturity[{i}]/create-once", replace(s, mature=s.mature | bit, producer=producer)
        if s.mature & bit and not s.admitted & bit:
            yield f"admission[{i}]", replace(s, admitted=s.admitted | bit)
        # R3's all-member publication precedes ordered authority handoff.
        if s.admitted == full and s.transitioned == bit - 1:
            yield f"real-R6-transition[{i}]", replace(
                s, transitioned=s.transitioned | bit,
                revoked=s.revoked or (i == 0 and s.accepted))
    if s.mature == full and not s.frozen:
        yield "producer-freeze-creation-rights", replace(s, frozen=True)
    if s.producer == "queued":
        yield "offer-registration/hold-until-disposition", replace(s, producer="offered")
        if s.transitioned == full:
            yield "retire-unoffered-obsolete-descriptor", replace(s, producer="settled")
    if s.producer == "offered" and not s.sealed:
        yield "registration-accept/copy-exact-facts", replace(
            s, producer="accept_ack", accepted=True, query=1)
        if s.transitioned == full:
            yield "offer-consumed-with-Closed-reject", replace(s, producer="reject_ack")
    if s.producer in ("accept_ack", "reject_ack"):
        yield "producer-receives-exact-disposition", replace(s, producer="settled")
    if s.accepted and s.query == 1 and not s.close_acks & 1:
        value = 2 if s.transitioned & 1 else 1 if s.admitted & 1 else 0
        yield f"lookup-fire/snapshot={value}", replace(s, query=2, reply=value)
    if s.query == 2:
        revoked = s.revoked or s.reply == 2
        if mutant == "late_reply_revives_pending":
            revoked = s.reply == 2
        yield "held-result-delivered", replace(s, query=3, revoked=revoked)
    if s.frozen and not s.sealed and (
        s.producer in ("none", "settled") or mutant == "seal_ignores_offer"
    ):
        yield "producer-seal-ACK", replace(s, sealed=True)
    if s.transitioned == full and not s.ready:
        yield "R5-ready/notice-custody", replace(s, ready=True)
    if s.accepted and s.query == 3 and s.revoked and not s.transferred:
        yield "owner-ACK/sticky-fact-independent-of-journal", replace(s, transferred=True)
    resolved = not s.accepted or (s.query == 3 and s.transferred)
    if mutant == "clear_ignores_query":
        resolved = True
    if s.sealed and s.transitioned == full and s.ready and resolved:
        for bit, name in ((1, "R3-clear-ACK"), (2, "ingress-close-ACK")):
            if not s.close_acks & bit:
                yield name, replace(s, close_acks=s.close_acks | bit)
    if s.close_acks == 3 or (mutant == "open_after_one_ACK" and s.close_acks):
        yield "open-G1/separate-phase", replace(s, next_open=True)


def window_error(s, members):
    full = (1 << members) - 1
    if s.admitted & ~s.mature or s.transitioned & ~s.admitted:
        return "invented admission or authority transition"
    if s.admitted.bit_count() > members or members > 64:
        return "working journal bound exceeded"
    if s.sealed and (not s.frozen or s.producer not in ("none", "settled")):
        return "producer seal lies about outstanding creation/offer/disposition"
    if s.accepted and s.transitioned & 1 and s.query == 3 and not s.revoked:
        return "late Unseen/Pending reply resurrects pending eligibility"
    if s.close_acks & 1:
        if s.query == 1:
            return "accepted unsnapshotted lookup still depends on cleared journal"
        if s.accepted and (s.query != 3 or not s.transferred):
            return "old response/owner custody not resolved at clear"
        if not s.sealed or s.transitioned != full or not s.ready:
            return "clear precedes real publication/authority/readiness custody"
    if s.next_open and s.close_acks != 3:
        return "G1 opens before both independent old-group close ACKs"
    return None


@dataclass(frozen=True)
class Lease:
    phase: int = 0  # open,ack,work,stored,cancel,cancelAck,abort,abortAck,failure,done
    transitioned: bool = False
    eligibility: int = 0  # absent, response held, cached
    eligibility_value: bool = False
    issued: bool = False
    issued_after_transition: bool = False
    pinned: bool = False
    terminal: int = 0  # absent, OK, fault
    consumers: int = 0
    source_released: bool = False
    transferred: bool = False
    journal_cleared: bool = False
    next_open: bool = False
    owner_reused: bool = False


@dataclass(frozen=True)
class ProducerDrain:
    queued: int = 64
    offered: bool = False
    disposition_held: bool = False
    disposed: int = 0
    sealed: bool = False


def producer_steps(s):
    # Creation frozen and all members already packed. No selected/accepted
    # attention is silently canceled here; those belong to separate owners.
    if s.sealed:
        return
    if s.queued:
        yield "retire-one-unoffered-obsolete-record", replace(s, queued=s.queued - 1, disposed=s.disposed + 1)
        if not s.offered and not s.disposition_held:
            yield "offer-one-registration", replace(s, queued=s.queued - 1, offered=True)
    if s.offered:
        yield "consume-offer/Closed-disposition", replace(s, offered=False, disposition_held=True)
    if s.disposition_held:
        yield "matching-disposition-ACK", replace(s, disposition_held=False, disposed=s.disposed + 1)
    if not s.queued and not s.offered and not s.disposition_held:
        yield "seal-after-all64-dispositions", replace(s, sealed=True)


def producer_error(s):
    if s.queued + int(s.offered) + int(s.disposition_held) + s.disposed != 64:
        return "producer lost or invented a descriptor/disposition"
    if s.sealed and s.disposed != 64:
        return "seal preceded a real disposition"
    return None


def lease_steps(s, mutant=""):
    if not s.transitioned:
        change = dict(transitioned=True)
        if mutant == "cancel_issued_lease" and s.issued and not s.terminal:
            change.update(phase=4, pinned=False)
        yield "real-R6-transition/withdraw-new-issue", replace(s, **change)
    if s.phase < 3:
        names = ("endpoint-open", "exact-open-ACK", "R2-candidate-stored")
        yield names[s.phase], replace(s, phase=s.phase + 1)
    if s.phase == 3 and not s.issued and s.eligibility == 0:
        yield "read-only-eligibility-query", replace(
            s, eligibility=1, eligibility_value=not s.transitioned)
    if s.eligibility == 1:
        yield "eligibility-response/possibly-stale", replace(s, eligibility=2)
    if s.phase == 3 and not s.issued:
        if s.eligibility == 2 and s.eligibility_value and (
            not s.transitioned or mutant == "trust_cached_eligibility"
        ):
            yield "joint-R2-R1-external-lease-fire", replace(
                s, issued=True, pinned=True, issued_after_transition=s.transitioned)
        if s.transitioned:
            yield "exact-withdrawal-accepted", replace(s, phase=4)
    if 4 <= s.phase < 9:
        names = ("cancel-request", "exact-cancel-ACK", "endpoint-abort",
                 "exact-abort-ACK", "R6-failure-accepted")
        yield names[s.phase - 4], replace(s, phase=s.phase + 1)
    if s.issued and not s.terminal:
        yield "matching-typed-R1-terminal/OK", replace(s, terminal=1, pinned=False, consumers=15)
        yield "matching-typed-R1-terminal/fault/quarantine", replace(s, terminal=2, pinned=False)
    if s.terminal == 1:
        for i in range(4):
            if s.consumers & (1 << i):
                yield f"consumer-commit[{i}]", replace(s, consumers=s.consumers & ~(1 << i))
        if not s.consumers and not s.source_released:
            yield "real-source-release-ACK", replace(s, source_released=True)
    if s.transitioned and not s.transferred:
        # Existing records retain exact identity, handle, generation and work.
        # This NEW ACK attests custody; it grants no authority or cancellation.
        yield "owner-custody-ACK/retain-old-context", replace(s, transferred=True)
    if s.transferred and not s.journal_cleared:
        change = dict(journal_cleared=True)
        if mutant == "reuse_owner_on_journal_clear":
            change.update(owner_reused=True, pinned=False)
        yield "journal-close-after-window-obligations", replace(s, **change)
    if s.journal_cleared and not s.next_open:
        yield "G1-journal-open/old-service-context-still-pinned", replace(s, next_open=True)
    complete = (s.phase == 9 or s.source_released) and s.eligibility != 1
    if complete and not s.owner_reused:
        yield "old-context-recycle-after-all-real-ACKs", replace(s, owner_reused=True)


def lease_error(s):
    if s.issued_after_transition:
        return "cached eligibility overrode real authority/commit-edge recheck"
    if s.issued and not s.terminal and (not s.pinned or 4 <= s.phase <= 9):
        return "issued read was canceled/unpinned before matching typed terminal"
    if s.owner_reused and not ((s.phase == 9 or s.source_released) and s.eligibility != 1):
        return "journal release overwrote a live service/cancel/query context"
    if s.source_released and (s.terminal != 1 or s.consumers):
        return "invented source release or release before all consumers"
    if s.journal_cleared and not s.transferred:
        return "journal cleared before independent custody"
    return None


def explore(initial, steps, error, goal, covers=None):
    """All finite states/edges; no stutter edges. Progress is existential only."""
    parents = {initial: None}
    queue = deque([initial])
    reverse = {}
    goals = set()
    witnesses = {}
    edges = 0

    def trace(s):
        events = []
        while parents[s] is not None:
            previous, event = parents[s]
            events.append(event)
            s = previous
        return list(reversed(events))

    while queue:
        s = queue.popleft()
        problem = error(s)
        if problem:
            return {"verdict": "COUNTEREXAMPLE", "invariant": problem,
                    "states_seen": len(parents), "trace": trace(s), "state": asdict(s)}
        if goal(s):
            goals.add(s)
        for name, predicate in (covers or {}).items():
            if name not in witnesses and predicate(s):
                witnesses[name] = trace(s)
        for event, target in steps(s):
            edges += 1
            reverse.setdefault(target, []).append(s)
            if target not in parents:
                parents[target] = (s, event)
                queue.append(target)
    reachable_goal = set(goals)
    queue = deque(goals)
    while queue:
        for previous in reverse.get(queue.popleft(), ()):
            if previous not in reachable_goal:
                reachable_goal.add(previous)
                queue.append(previous)
    return {"verdict": "PASS", "states": len(parents), "transitions": edges,
            "goal_states": len(goals), "states_without_a_completion_path": len(parents) - len(reachable_goal),
            "coverage": witnesses,
            "progress_boundary": "existence of a completion path under acknowledgements, not fair/unbounded RTL liveness"}


def classifier(namespace, sequence, active_namespace, active_sequence, closed_through, exact_state,
               member_ownership=True):
    if namespace != active_namespace:
        return "StaleNamespace"
    if sequence <= closed_through:
        return "Closed"
    if sequence != active_sequence:
        return "WrongWindow"
    if not member_ownership:
        return "NotOwned"
    return ("Unseen", "PendingMember", "TransitionedPacked")[exact_state]


def closed_plan_action(attention_accepted, plan_accepted, lease_issued):
    """Required NEW disposition, not a claim that v1 supplies each path."""
    if lease_issued:
        assert plan_accepted and attention_accepted
        return "continue_exact_leased_read"
    if plan_accepted:
        assert attention_accepted
        return "cancel_abort_then_R6_failure"
    if attention_accepted:
        return "R6_preplan_fault_once"
    return "local_reject_no_attention_terminal"


def run():
    if not __debug__:
        raise RuntimeError("Run without -O: contract checks require enabled assertions")
    checks = {}
    window_covers = {
        "Unseen_snapshot_survives_later_transition": lambda s: s.reply == 0 and s.revoked and s.query == 3,
        "Pending_snapshot_survives_later_transition": lambda s: s.reply == 1 and s.revoked and s.query == 3,
        "late_registration_observes_transition": lambda s: s.reply == 2 and s.query == 3,
        "producer_offer_rejected_with_ack": lambda s: s.producer == "reject_ack",
        "query_held_after_producer_seal": lambda s: s.sealed and s.query == 1,
        "R3_ACK_first": lambda s: s.close_acks == 1,
        "ingress_ACK_first": lambda s: s.close_acks == 2,
        "G1_open_without_attention": lambda s: s.next_open,
    }
    for members in (1, 2, 3):
        for descriptor in (False, True):
            name = f"window_members{members}_descriptor{int(descriptor)}"
            result = explore(Window(producer="unborn" if descriptor else "none"),
                             lambda s: window_steps(s, members), lambda s: window_error(s, members),
                             lambda s: s.next_open, window_covers if descriptor else None)
            assert result["verdict"] == "PASS" and result["goal_states"] > 0, (name, result)
            assert result["states_without_a_completion_path"] == 0, (name, result)
            if descriptor:
                assert set(result["coverage"]) == set(window_covers), (name, result["coverage"])
            checks[name] = result
    lease_covers = {
        "G1_before_cancel_ACK": lambda s: s.next_open and s.phase == 5,
        "G1_before_R1_terminal": lambda s: s.next_open and s.issued and not s.terminal,
        "G1_before_source_release": lambda s: s.next_open and s.terminal == 1 and not s.source_released,
        "stale_positive_eligibility_after_transition": lambda s: s.transitioned and not s.issued and s.eligibility == 2 and s.eligibility_value,
        "fault_preserves_quarantined_context": lambda s: s.next_open and s.terminal == 2 and not s.owner_reused,
        "context_recycle_after_success": lambda s: s.source_released and s.owner_reused,
        "context_recycle_after_cancel": lambda s: s.phase == 9 and s.owner_reused,
    }
    checks["lease_custody"] = explore(Lease(), lease_steps, lease_error,
                                      lambda s: s.next_open, lease_covers)
    assert checks["lease_custody"]["verdict"] == "PASS"
    assert checks["lease_custody"]["states_without_a_completion_path"] == 0
    assert set(checks["lease_custody"]["coverage"]) == set(lease_covers)
    checks["producer_full64_drain"] = explore(
        ProducerDrain(), producer_steps, producer_error, lambda s: s.sealed,
        {"held_offer": lambda s: s.offered,
         "held_disposition": lambda s: s.disposition_held,
         "all64_disposed_before_seal": lambda s: s.disposed == 64 and not s.sealed})
    assert checks["producer_full64_drain"]["verdict"] == "PASS"
    assert checks["producer_full64_drain"]["states_without_a_completion_path"] == 0
    mutants = {}
    for name in ("seal_ignores_offer", "clear_ignores_query", "open_after_one_ACK", "late_reply_revives_pending"):
        mutants[name] = explore(Window(), lambda s: window_steps(s, 2, name),
                                lambda s: window_error(s, 2), lambda s: s.next_open)
    for name in ("cancel_issued_lease", "trust_cached_eligibility", "reuse_owner_on_journal_clear"):
        mutants[name] = explore(Lease(), lambda s: lease_steps(s, name), lease_error, lambda s: s.next_open)
    assert all(r["verdict"] == "COUNTEREXAMPLE" for r in mutants.values()), mutants
    classifications = 0
    # Exact key is opaque here: vary all three abstract equality outcomes.
    for namespace in (6, 7, 8):
        for sequence in (0, 1, 2, 3):
            for equality in range(3):
                for owned in (False, True):
                    actual = classifier(namespace, sequence, 7, 2, 1, equality, owned)
                    if namespace != 7:
                        assert actual == "StaleNamespace"
                    elif sequence <= 1:
                        assert actual == "Closed"
                    elif sequence != 2:
                        assert actual == "WrongWindow"
                    elif not owned:
                        assert actual == "NotOwned"
                    else:
                        assert actual in ("Unseen", "PendingMember", "TransitionedPacked")
                    classifications += 1
    mutants["closed_token_as_Unseen"] = {
        "verdict": "COUNTEREXAMPLE", "trace": ["G0 transitioned and closed", "late G0 lookup after clear"],
        "invariant": "closed history must not be reported as Unseen",
        "correct": classifier(7, 1, 7, 2, 1, 0), "bad": "Unseen"}
    mutants["foreign_key_relabelled_as_current_window"] = {
        "verdict": "COUNTEREXAMPLE", "trace": ["G0 transitioned and closed", "G1 opens", "old binding relabelled with G1 token"],
        "invariant": "a current token alone cannot establish immutable member ownership",
        "correct": classifier(7, 2, 7, 2, 1, 0, False), "bad": "Unseen"}
    cuts = []
    for attention, plan, issued in ((False, False, False), (True, False, False),
                                    (True, True, False), (True, True, True)):
        action = closed_plan_action(attention, plan, issued)
        cuts.append(dict(attention_accepted=attention, plan_accepted=plan, lease_issued=issued,
                         required_action=action))
    assert cuts[0]["required_action"] == "local_reject_no_attention_terminal"
    assert cuts[1]["required_action"] == "R6_preplan_fault_once"
    assert cuts[2]["required_action"] == "cancel_abort_then_R6_failure"
    assert cuts[3]["required_action"] == "continue_exact_leased_read"
    mutants["invent_terminal_without_accepted_attention"] = {
        "verdict": "COUNTEREXAMPLE", "trace": ["registration offered without accepted attention", "closed window rejects registration"],
        "invariant": "a local registration rejection cannot invent an attention terminal",
        "correct": cuts[0]["required_action"], "bad": "R6_preplan_fault_once"}
    for name in ("closed_token_as_Unseen", "foreign_key_relabelled_as_current_window",
                 "invent_terminal_without_accepted_attention"):
        assert mutants[name]["correct"] != mutants[name]["bad"]
        mutants[name]["kind"] = "directed_policy_counterexample"
    for result in mutants.values():
        result.setdefault("kind", "exhaustive_bad_policy_counterexample")
    # Full64 directed witness, not exhaustive 2**64 occupancy verification.
    s = Window(producer="none")
    witness = []
    while not s.next_open:
        options = list(window_steps(s, 64))
        assert options
        event, s = options[0]
        assert not window_error(s, 64)
        witness.append(event)
    # Commit-edge authority wins in the same cycle even with a cached grant.
    edge_checks = []
    for external_ready in (False, True):
        for transition in (False, True):
            fires = external_ready and not transition
            assert not (fires and transition)
            edge_checks.append(dict(external_ready=external_ready, transition=transition,
                                    R2_R1_external_lease_joint_fire=fires))
    return {"schema": "route_a_registration_window_finite_model_v1", "verdict": "PASS_CONDITIONAL_CONTRACT_ONLY",
            "not_proved": ["existing producer implements seal or bounded delivery", "RTL refinement/equivalence",
                           "multiple descriptor owners or arbitrary source-plan mixtures", "data numeric correspondence",
                           "multi-record or source_last=false direct-source continuation",
                           "full32K traffic/capacity, wrap or unbounded liveness", "2ns, mapped area or net benefit"],
            "assumptions": ["producer creates descriptor once at maturity, freezes generation and acknowledges all offered dispositions before seal",
                            "single <=64-member working group, no G1 admission before both close ACKs",
                            "all old queries resolve and permanent revoked facts remain in bounded independent owners",
                            "active token is bound to immutable pending/member ownership, not trusted solely from request bits",
                            "all accepted unplanned attentions have an explicit R6-owned rejection path; the lease component starts after association acceptance",
                            "the successful consumer/source-release branch uses one source-ending direct record; source_last is not derived from group size",
                            "owner custody ACK does not recycle or cancel an issued read",
                            "closed/wrong-namespace requests explicitly reject, never become Unseen"],
            "checks": checks, "bad_policy_counterexamples": mutants,
            "classification_cases": classifications, "closed_plan_cuts": cuts,
            "same_cycle_joint_fire_cases": edge_checks,
            "full64_directed_trace": witness,
            "occupancy_argument": "only active-group unique ordinals write the <=64-row journal; next group opens after old close; transferred service contexts are separate bounded nonzero cost"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, help="Write the finite-model evidence; never modifies RTL")
    args = parser.parse_args()
    result = run()
    if args.output_json:
        args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verdict": result["verdict"],
                      "checks": {k: {p: v[p] for p in ("states", "transitions", "goal_states")} for k, v in result["checks"].items()},
                      "counterexamples": list(result["bad_policy_counterexamples"]),
                      "classification_cases": result["classification_cases"],
                      "full64_trace_events": len(result["full64_directed_trace"])}))


if __name__ == "__main__":
    main()
