from collections import Counter

from tools.analyze_kvzap_route_a480_commit_aware_backlog import ScheduledTransaction, service_backlog
from tools.analyze_kvzap_route_a481a_readiness_root_cause import audit_causal_replay, baseline_equivalent


PROFILE = {"profile": "test", "layout": "both_colocated_direct_v1", "bank_count": 8, "bank_mapping": "head_affine_v1"}


def tx(index, demands, *, predecessors=()):
    return ScheduledTransaction(
        index=index, phase="activation", checkpoint=0, layer=0, head=0,
        arrival_ordinal=0, predecessors=frozenset(predecessors),
        demands=Counter(demands), banks=frozenset(bank for bank, _ in demands),
    )


def test_a481a_shortage_root_amplifies_through_downstream_dependency_chain():
    transactions = [
        tx(0, {(0, "rmw"): 1}),
        tx(1, {(0, "rmw"): 1}, predecessors=(0,)),
        tx(2, {(0, "rmw"): 1}, predecessors=(1,)),
    ]
    opportunities = [("activation", 0)]
    reference = service_backlog(transactions=transactions, opportunities=opportunities, policy="causal_elastic_v1", post_trace_drain_limit=8)
    audit = audit_causal_replay(transactions=transactions, opportunities=opportunities, profile=PROFILE, post_trace_drain_limit=8)
    assert baseline_equivalent(audit, reference)
    roots = audit["root_cause_amplification"]["rmw_service_shortage"]
    assert roots["root_incident_count"] >= 1
    assert roots["unique_downstream_transaction_count"] >= 1
    assert audit["readiness"]["sustained_post_service_ready_positive_logical_opportunity_run"] >= 1


def test_a481a_no_ready_work_is_not_mislabeled_as_service_shortage():
    transactions = [
        tx(0, {(0, "write"): 1}),
        tx(1, {(0, "write"): 1}, predecessors=(0,)),
    ]
    audit = audit_causal_replay(transactions=transactions, opportunities=[("activation", 0)], profile=PROFILE, post_trace_drain_limit=4)
    assert audit["completion_state"] == "drained"
    assert audit["readiness"]["post_service_ready_backlog"]["max"] == 1
    assert audit["root_cause_amplification"]["same_bank_service_shortage"]["root_incident_count"] >= 1
