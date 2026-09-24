from collections import Counter

from tools.analyze_kvzap_route_a480_commit_aware_backlog import ScheduledTransaction
from tools.analyze_kvzap_route_a481b_fixed_service_sweep import audit_fixed_service_replay


PROFILE = {"profile": "test", "layout": "both_colocated_direct_v1", "bank_count": 8, "bank_mapping": "head_affine_v1"}


def tx(index, demands, *, predecessors=()):
    return ScheduledTransaction(
        index=index, phase="activation", checkpoint=0, layer=0, head=0,
        arrival_ordinal=0, predecessors=frozenset(predecessors),
        demands=Counter(demands), banks=frozenset(bank for bank, _ in demands),
    )


def test_fixed_quantum_changes_only_declared_service_availability():
    transactions = [tx(0, {(0, "rmw"): 1}), tx(1, {(0, "rmw"): 1})]
    q1 = audit_fixed_service_replay(transactions=transactions, opportunities=[("activation", 0)], profile=PROFILE, quantum=1, post_trace_drain_limit=4)
    q2 = audit_fixed_service_replay(transactions=transactions, opportunities=[("activation", 0)], profile=PROFILE, quantum=2, post_trace_drain_limit=4)
    assert q1["completion_state"] == q2["completion_state"] == "drained"
    assert q1["post_trace_drain_opportunities_used"] == 1
    assert q2["post_trace_drain_opportunities_used"] == 0
    assert q1["root_cause_amplification"]["rmw_service_shortage"]["root_incident_count"] == 1
    assert q2["root_cause_amplification"]["rmw_service_shortage"]["root_incident_count"] == 0


def test_fixed_quantum_preserves_dependency_order_and_reports_blocked_work():
    transactions = [tx(0, {(0, "write"): 1}), tx(1, {(0, "write"): 1}, predecessors=(0,))]
    audit = audit_fixed_service_replay(transactions=transactions, opportunities=[("activation", 0)], profile=PROFILE, quantum=1, post_trace_drain_limit=4)
    assert audit["committed_transaction_group_count"] == 2
    assert audit["readiness"]["trace_end_residual_backlog"]["dependency_blocked"] == 0
    assert audit["root_cause_amplification"]["same_bank_service_shortage"]["root_incident_count"] >= 1
