import pytest
import torch

from kvpress.route_a_attention import dense_same_mask_attention
from kvpress.route_a_external_cold_storage import RouteAExternalColdStorageAdapter
from kvpress.route_a_storage_contract import assert_storage_contract_state


def adapter(*, budget: int) -> RouteAExternalColdStorageAdapter:
    return RouteAExternalColdStorageAdapter(heads=2, head_dim=2, window=2, page_tokens=2, admission_budget=budget, selected_kv_heads=(1,))


def append_segments(result: RouteAExternalColdStorageAdapter) -> tuple[torch.Tensor, torch.Tensor]:
    keys = torch.arange(28, dtype=torch.float32).reshape(2, 7, 2)
    values = keys + 100
    keep = torch.tensor([[True, False, True, True, False, True, True], [False, True, True, False, True, True, False]])
    result.append(keys[:, :4], values[:, :4], keep[:, :4], start_position=0)
    result.append(keys[:, 4:], values[:, 4:], keep[:, 4:], start_position=4)
    return keys, values


def test_external_adapter_preserves_logical_length_and_materializes_only_selected_hot():
    result = adapter(budget=1)
    keys, values = append_segments(result)
    assert result.logical_cache_tokens == 7
    assert tuple(result.selected_native_hot_keys.shape) == (1, 2, 2)
    assert torch.equal(result.selected_native_hot_keys[0], keys[1, -2:])
    assert torch.equal(result.selected_native_hot_values[0], values[1, -2:])
    summary = result.ownership_summary()
    assert summary["adapter_selected_native_cold_tensor_tokens"] == 0
    assert summary["adapter_selected_cold_tensors_absent"]
    assert not summary["transformers_dynamic_cache_substitution"]
    assert_storage_contract_state(summary, require_pending=True)


def test_external_adapter_packed_attention_matches_same_mask_dense_with_full_tail_multipage():
    result = adapter(budget=512)
    append_segments(result)
    summary = result.ownership_summary()
    assert_storage_contract_state(summary, require_multi_page=True, require_full_page=True, require_tail=True)
    query = torch.tensor([0.25, -0.5])
    torch.testing.assert_close(result.state.attention(query, head=1), dense_same_mask_attention(query, result.state.same_mask_records(1)), rtol=1e-6, atol=1e-6)


def test_real_dynamic_cache_truncation_changes_its_logical_length_and_cannot_be_used_as_adapter():
    transformers = pytest.importorskip("transformers")
    cache = transformers.DynamicCache()
    keys = torch.randn(1, 2, 7, 4)
    values = torch.randn(1, 2, 7, 4)
    cache.update(keys, values, 0)
    assert cache.get_seq_length(0) == 7
    layer = cache.layers[0]
    layer.keys = layer.keys[..., -2:, :]
    layer.values = layer.values[..., -2:, :]
    assert cache.get_seq_length(0) == 2


def test_external_adapter_rejects_noncontiguous_append():
    result = adapter(budget=1)
    keys = torch.zeros(2, 1, 2)
    with pytest.raises(AssertionError, match="position"):
        result.append(keys, keys, torch.ones(2, 1, dtype=torch.bool), start_position=1)
