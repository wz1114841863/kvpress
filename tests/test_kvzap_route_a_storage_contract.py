import pytest
import torch

from kvpress.route_a_attention import RouteAPackedAttentionState
from kvpress.route_a_storage_contract import assert_storage_contract_state, selected_storage_ownership_contract


def state(*, budget: int) -> RouteAPackedAttentionState:
    result = RouteAPackedAttentionState(heads=2, head_dim=2, window=2, page_tokens=2, admission_budget=budget)
    keys = torch.arange(28, dtype=torch.float32).reshape(2, 7, 2)
    keep = torch.tensor([[True, False, True, True, False, True, True], [False, True, True, False, True, True, False]])
    result.append(keys, keys + 100, keep, start_position=0)
    return result


def test_contract_preserves_logical_length_and_partitions_mature_selected_cold():
    contract = selected_storage_ownership_contract(state(budget=1))
    assert contract["logical_cache_tokens"] == 7
    assert contract["selected_attention_owns_mature_cold"]
    assert [row["native_mature_cold_tokens_releasable"] for row in contract["heads"]] == [5, 5]
    assert [row["native_hot_tokens_required"] for row in contract["heads"]] == [2, 2]
    assert all(not row["native_selected_cold_slots_physically_freed"] for row in contract["heads"])
    assert_storage_contract_state(contract, require_pending=True)


def test_contract_covers_full_page_tail_and_multi_page_when_admission_drains():
    contract = selected_storage_ownership_contract(state(budget=512))
    assert_storage_contract_state(contract, require_multi_page=True, require_full_page=True, require_tail=True)
    assert all(row["route_a_pending_tokens"] == 0 for row in contract["heads"])


def test_contract_rejects_wrong_native_logical_length_and_missing_required_state():
    with pytest.raises(AssertionError, match="logical cache length"):
        selected_storage_ownership_contract(state(budget=1), native_logical_tokens=6)
    with pytest.raises(AssertionError, match="multi-page"):
        assert_storage_contract_state(selected_storage_ownership_contract(state(budget=1)), require_multi_page=True)
