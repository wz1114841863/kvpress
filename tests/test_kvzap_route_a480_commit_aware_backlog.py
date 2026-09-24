from collections import Counter

from tools.analyze_kvzap_route_a480_commit_aware_backlog import CausalController, ScheduledTransaction, blocking_cause, service_backlog


def tx(index, arrival, demands, *, predecessors=(), banks=None):
    return ScheduledTransaction(
        index=index, phase="steady_state_dequeue", checkpoint=arrival, layer=0, head=index,
        arrival_ordinal=arrival, predecessors=frozenset(predecessors),
        demands=Counter(demands), banks=frozenset(banks if banks is not None else [bank for bank, _ in demands]),
    )


def test_a480_blocking_causes_keep_intrinsic_rmw_and_cross_bank_separate():
    dependent = tx(1, 0, {(0, "write"): 1}, predecessors=(0,))
    assert blocking_cause(dependent, set(), Counter({(0, "write"): 1})) == "intrinsic_transaction_dependency"
    rmw = tx(2, 0, {(0, "rmw"): 1})
    assert blocking_cause(rmw, set(), Counter({(0, "rmw"): 0})) == "rmw_service_shortage"
    cross_bank = tx(3, 0, {(0, "write"): 1, (1, "write"): 1}, banks=(0, 1))
    assert blocking_cause(cross_bank, set(), Counter({(0, "write"): 0, (1, "write"): 1})) == "cross_bank_atomic_commit_waiting"


def test_a480_direct_baseline_drains_and_causal_replay_preserves_predecessors():
    transactions = [
        tx(0, 0, {(0, "write"): 1}),
        tx(1, 0, {(0, "rmw"): 1}, predecessors=(0,)),
        tx(2, 0, {(0, "write"): 1, (1, "write"): 1}, banks=(0, 1)),
    ]
    direct = service_backlog(transactions=transactions, opportunities=[("activation", 0)], policy="direct_unconstrained_commit", post_trace_drain_limit=0)
    causal = service_backlog(transactions=transactions, opportunities=[("activation", 0)], policy="causal_elastic_v1", post_trace_drain_limit=8)
    assert direct["completion_state"] == "drained"
    assert direct["committed_transaction_group_count"] == 3
    assert causal["completion_state"] == "drained"
    assert causal["backlog_group_observations_by_blocking_cause"]["cross_bank_atomic_commit_waiting"] >= 1


def test_a480_causal_controller_is_prefix_causal_and_uses_fixed_levels():
    first = CausalController(); second = CausalController()
    prefix = [(0, 0, 0), (130, 2, 0), (700, 70, 20), (0, 0, 0), (0, 0, 0)]
    decisions_a = [first.choose(layer_backlog=a, head_backlog=b, age_max=c) for a, b, c in prefix]
    decisions_b = [second.choose(layer_backlog=a, head_backlog=b, age_max=c) for a, b, c in prefix]
    assert decisions_a == decisions_b
    assert {quantum for _, quantum, _ in decisions_a} <= {1, 2, 4}
