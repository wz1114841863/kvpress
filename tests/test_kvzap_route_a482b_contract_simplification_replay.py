from collections import Counter

from tools.analyze_kvzap_route_a480_commit_aware_backlog import ScheduledTransaction
from tools.analyze_kvzap_route_a482b_contract_simplification_replay import (
    EAGER_OPTION,
    EXPANDED_OPTION,
    expand_modeled_rmw_demands,
    modeled_work_ledger,
    transaction_identity_equal,
    variant_transactions,
)


def transaction(index: int, demands: dict[tuple[int, str], int]) -> ScheduledTransaction:
    return ScheduledTransaction(
        index=index, phase="steady_state_dequeue", checkpoint=7, layer=1, head=2,
        arrival_ordinal=3, predecessors=frozenset({0}) if index else frozenset(),
        demands=Counter(demands), banks=frozenset(bank for bank, _ in demands),
    )


def test_expansion_replaces_only_existing_rmw_with_same_bank_read_and_write():
    demands = Counter({(3, "read"): 1, (3, "rmw"): 2, (4, "write"): 1})
    eager = expand_modeled_rmw_demands(demands, EAGER_OPTION)
    expanded = expand_modeled_rmw_demands(demands, EXPANDED_OPTION)
    assert eager == demands
    assert expanded == Counter({(3, "read"): 3, (3, "write"): 2, (4, "write"): 1})
    assert not any(operation == "rmw" for _, operation in expanded)


def test_variant_preserves_immutable_identity_and_only_changes_demand_class():
    base = [transaction(0, {(0, "rmw"): 1}), transaction(1, {(1, "read"): 1, (1, "rmw"): 1})]
    eager = variant_transactions(base, EAGER_OPTION)
    expanded = variant_transactions(base, EXPANDED_OPTION)
    assert transaction_identity_equal(base, eager)
    assert transaction_identity_equal(base, expanded)
    assert eager[0].demands == base[0].demands
    assert expanded[0].demands == Counter({(0, "read"): 1, (0, "write"): 1})
    assert expanded[1].demands == Counter({(1, "read"): 2, (1, "write"): 1})


def test_modeled_work_ledger_makes_expansion_cost_explicit():
    base = [transaction(0, {(0, "rmw"): 2, (1, "write"): 1})]
    eager = modeled_work_ledger(variant_transactions(base, EAGER_OPTION))
    expanded = modeled_work_ledger(variant_transactions(base, EXPANDED_OPTION))
    assert eager == {"rmw_modeled_storage_object_work": 2, "total_modeled_storage_object_work": 3, "write_modeled_storage_object_work": 1}
    assert expanded == {"read_modeled_storage_object_work": 2, "total_modeled_storage_object_work": 5, "write_modeled_storage_object_work": 3}
