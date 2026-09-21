from tools.analyze_kvzap_route_a466_pending_organization_contract import (
    organization_summary,
    snapshot,
    zero_breach_budget,
)


def _samples() -> dict[int, list[tuple[int, list[int]]]]:
    return {0: [(1, [8, 0]), (2, [8, 8])], 1: [(1, [5, 3]), (2, [0, 0])]}


def test_a466_same_total_budget_exposes_private_stranding_without_changing_pending():
    pending = [8, 0]
    head_local = snapshot(pending=pending, total_budget=12, organization="head_local_equal_quota")
    shared = snapshot(pending=pending, total_budget=12, organization="layer_shared")
    hierarchical = snapshot(pending=pending, total_budget=12, organization="hierarchical_private_plus_shared_overflow", private_quota=2)
    assert pending == [8, 0]
    assert head_local["peak_excess"] == 2
    assert head_local["stranded_private_reservation"] == 6
    assert shared["peak_excess"] == 0
    assert shared["stranded_private_reservation"] == 0
    assert hierarchical["peak_excess"] == 0
    assert hierarchical["shared_overflow_capacity"] == 8


def test_a466_hierarchical_endpoints_degenerate_to_shared_and_head_local():
    samples = _samples()
    budget = 16
    shared = organization_summary(samples=samples, total_budget=budget, organization="layer_shared")
    hierarchical_shared = organization_summary(samples=samples, total_budget=budget, organization="hierarchical_private_plus_shared_overflow", private_quota=0)
    head_local = organization_summary(samples=samples, total_budget=budget, organization="head_local_equal_quota")
    hierarchical_private = organization_summary(samples=samples, total_budget=budget, organization="hierarchical_private_plus_shared_overflow", private_quota=8)
    for field in ("breach_layer_opportunity_count", "peak_excess_logical_tokens", "max_consecutive_breach_duration", "stranded_private_reservation_during_breach_total"):
        assert shared[field] == hierarchical_shared[field]
        assert head_local[field] == hierarchical_private[field]


def test_a466_zero_breach_frontier_orders_capacity_pooling_bounds():
    samples = _samples()
    shared = zero_breach_budget(samples=samples, organization="layer_shared")
    head_local = zero_breach_budget(samples=samples, organization="head_local_equal_quota")
    hierarchical = zero_breach_budget(samples=samples, organization="hierarchical_private_plus_shared_overflow", private_quota=2)
    assert shared == 16
    assert hierarchical == 16
    assert head_local == 16
