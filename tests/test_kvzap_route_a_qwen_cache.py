from types import SimpleNamespace

import torch

from kvpress.route_a_external_cold_storage import RouteAExternalColdStorageAdapter
from kvpress.route_a_qwen_cache import RouteAQwenSingleLayerExternalColdCache
from kvpress.route_a_policy_backend import RouteAQwenExternalColdStorageAttentionBackend


def test_qwen_external_cold_cache_keeps_only_unselected_persistent_kv_and_logical_length():
    cache = RouteAQwenSingleLayerExternalColdCache(target_layer=0, selected_kv_head=1)
    key = torch.arange(24, dtype=torch.float32).reshape(1, 2, 6, 2)
    value = key + 100
    view_key, view_value = cache.update(key, value, 0, {"cache_position": torch.arange(6)})
    layer = cache.layers[0]
    assert cache.get_seq_length() == 6
    assert tuple(layer.unselected_keys.shape) == (1, 1, 6, 2)
    assert torch.equal(layer.unselected_keys[:, 0], key[:, 0])
    assert torch.equal(view_key, key)
    assert torch.equal(view_value, value)

    next_key = torch.full((1, 2, 2, 2), 9.0)
    view_key, _view_value = cache.update(next_key, next_key + 100, 0, {"cache_position": torch.arange(6, 8)})
    assert cache.get_seq_length() == 8
    assert torch.isnan(view_key[:, 1, :6]).all()
    assert torch.equal(view_key[:, 1, 6:], next_key[:, 1])
    assert tuple(layer.unselected_keys.shape) == (1, 1, 8, 2)


def test_qwen_external_cold_cache_contract_binds_selected_hot_to_route_a_adapter():
    cache = RouteAQwenSingleLayerExternalColdCache(target_layer=0, selected_kv_head=1)
    adapter = RouteAExternalColdStorageAdapter(heads=2, head_dim=2, window=2, page_tokens=2, admission_budget=1, selected_kv_heads=(1,))
    key = torch.arange(28, dtype=torch.float32).reshape(2, 7, 2)
    keep = torch.ones(2, 7, dtype=torch.bool)
    _view_key, _view_value = cache.update(key.unsqueeze(0), (key + 100).unsqueeze(0), 0, {"cache_position": torch.arange(7)})
    adapter.append(key, key + 100, keep, start_position=0)
    cache.assert_target_storage_contract(adapter=adapter)
    summary = cache.target_storage_summary(adapter=adapter)
    assert summary["persistent_selected_native_cold_tensor_tokens"] == 0
    assert summary["persistent_selected_native_hot_tokens"] == 2
    assert summary["persistent_unselected_kv_tokens"] == 7


def test_qwen_external_cold_cache_rejects_noncontiguous_qwen_positions_and_nonzero_target_layer():
    cache = RouteAQwenSingleLayerExternalColdCache(target_layer=0, selected_kv_head=0)
    key = torch.zeros(1, 2, 1, 2)
    try:
        cache.update(key, key, 0, {"cache_position": torch.tensor([1])})
    except AssertionError as error:
        assert "contiguous" in str(error)
    else:
        raise AssertionError("noncontiguous position unexpectedly accepted")
    try:
        RouteAQwenSingleLayerExternalColdCache(target_layer=1, selected_kv_head=0)
    except ValueError as error:
        assert "layer 0" in str(error)
    else:
        raise AssertionError("nonzero target layer unexpectedly accepted")


def test_qwen_cache_attention_view_drives_external_backend_without_persistent_selected_cold():
    model = SimpleNamespace(model=SimpleNamespace(layers=[SimpleNamespace(self_attn=SimpleNamespace())]))
    backend = RouteAQwenExternalColdStorageAttentionBackend(model, object(), layer=0, kv_head=0, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    module = SimpleNamespace(scaling=1.0)
    cache = RouteAQwenSingleLayerExternalColdCache(target_layer=0, selected_kv_head=0)
    key = torch.arange(6, dtype=torch.float32).reshape(1, 1, 3, 2)
    view_key, view_value = cache.update(key, key + 10, 0, {"cache_position": torch.arange(3)})
    backend._keep_mask, backend._score_start = torch.ones(1, 1, 3, dtype=torch.bool), 0
    backend.attention(lambda *_args, **_kwargs: (torch.zeros(1, 3, 2, 2), None), module, torch.ones(1, 2, 3, 2), view_key, view_value, None, 0.0, scaling=1.0)
    next_key = torch.tensor([[[[9.0, 10.0]]]])
    view_key, view_value = cache.update(next_key, next_key + 10, 0, {"cache_position": torch.tensor([3])})
    backend._keep_mask, backend._score_start = torch.ones(1, 1, 1, dtype=torch.bool), 3
    output, _weights = backend.attention(lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("selected external path called original attention")), module, torch.tensor([[[[1., 0.]], [[0., 1.]]]]), view_key, view_value, None, 0.0, scaling=1.0)
    assert torch.isfinite(output).all()
    backend.assert_external_storage_interface_complete()
    cache.assert_target_storage_contract(adapter=backend.external_cold_storage)
