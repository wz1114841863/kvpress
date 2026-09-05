import sys
from types import SimpleNamespace

import torch

from kvpress.route_a_external_cold_storage import RouteAExternalColdStorageAdapter
from kvpress.route_a_qwen_cache import RouteAQwenMultiLayerExternalColdCache, RouteAQwenSingleLayerExternalColdCache
from kvpress.route_a_policy_backend import RouteAQwenExternalColdStorageAttentionBackend, RouteAQwenExternalColdStorageAttentionBackendSet
from tools.run_kvzap_route_a4142_qwen_multilayer_allhead_native_storage_gate import aggregate_full_multi_tail_page_coverage, parse_args, resolve_scope_layers


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


def test_qwen_external_cold_cache_supports_all_selected_kv_heads_without_dense_persistent_heads():
    cache = RouteAQwenSingleLayerExternalColdCache(target_layer=0, selected_kv_heads=(0, 1))
    adapter = RouteAExternalColdStorageAdapter(heads=2, head_dim=2, window=2, page_tokens=2, admission_budget=1, selected_kv_heads=(0, 1))
    key = torch.arange(28, dtype=torch.float32).reshape(2, 7, 2)
    keep = torch.ones(2, 7, dtype=torch.bool)
    _view_key, _view_value = cache.update(key.unsqueeze(0), (key + 100).unsqueeze(0), 0, {"cache_position": torch.arange(7)})
    adapter.append(key, key + 100, keep, start_position=0)
    cache.assert_target_storage_contract(adapter=adapter)
    summary = cache.target_storage_summary(adapter=adapter)
    assert summary["selected_kv_heads"] == [0, 1]
    assert summary["persistent_unselected_kv_heads"] == 0
    assert tuple(cache.layers[0].unselected_keys.shape) == (1, 0, 7, 2)


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


def test_qwen_cache_all_head_view_drives_all_gqa_groups_without_persistent_dense_heads():
    model = SimpleNamespace(model=SimpleNamespace(layers=[SimpleNamespace(self_attn=SimpleNamespace())]))
    backend = RouteAQwenExternalColdStorageAttentionBackend(model, object(), layer=0, kv_head=None, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    module = SimpleNamespace(scaling=1.0)
    cache = RouteAQwenSingleLayerExternalColdCache(target_layer=0, selected_kv_heads=(0, 1))
    key = torch.arange(12, dtype=torch.float32).reshape(1, 2, 3, 2)
    view_key, view_value = cache.update(key, key + 10, 0, {"cache_position": torch.arange(3)})
    backend._keep_mask, backend._score_start = torch.ones(1, 2, 3, dtype=torch.bool), 0
    backend.attention(lambda *_args, **_kwargs: (torch.zeros(1, 3, 4, 2), None), module, torch.ones(1, 4, 3, 2), view_key, view_value, None, 0.0, scaling=1.0)
    next_key = torch.full((1, 2, 1, 2), 9.0)
    view_key, view_value = cache.update(next_key, next_key + 10, 0, {"cache_position": torch.tensor([3])})
    backend._keep_mask, backend._score_start = torch.ones(1, 2, 1, dtype=torch.bool), 3
    output, _weights = backend.attention(lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("all-head selected path called original attention")), module, torch.ones(1, 4, 1, 2), view_key, view_value, None, 0.0, scaling=1.0)
    assert torch.isfinite(output).all()
    backend.assert_external_storage_interface_complete()
    cache.assert_target_storage_contract(adapter=backend.external_cold_storage)
    assert cache.target_storage_summary(adapter=backend.external_cold_storage)["persistent_unselected_kv_heads"] == 0


def test_qwen_multilayer_cache_keeps_independent_all_head_contracts():
    layers = (0, 18, 35)
    cache = RouteAQwenMultiLayerExternalColdCache(selected_kv_heads_by_layer={layer: (0, 1) for layer in layers})
    adapters = {
        layer: RouteAExternalColdStorageAdapter(heads=2, head_dim=2, window=2, page_tokens=2, admission_budget=1, selected_kv_heads=(0, 1))
        for layer in layers
    }
    key = torch.arange(20, dtype=torch.float32).reshape(2, 5, 2)
    keep = torch.ones(2, 5, dtype=torch.bool)
    for layer in layers:
        view_key, _view_value = cache.update(key.unsqueeze(0), (key + 100).unsqueeze(0), layer, {"cache_position": torch.arange(5)})
        adapters[layer].append(key, key + 100, keep, start_position=0)
        assert torch.equal(view_key, key.unsqueeze(0))
    cache.assert_target_storage_contracts(adapters_by_layer=adapters)
    summaries = cache.target_storage_summaries(adapters_by_layer=adapters)
    assert [row["layer"] for row in summaries["layers"]] == list(layers)
    assert all(row["persistent_unselected_kv_heads"] == 0 for row in summaries["layers"])
    assert all(row["persistent_selected_native_cold_tensor_tokens"] == 0 for row in summaries["layers"])


def test_qwen_multilayer_backend_set_has_independent_external_adapter_slots():
    model = SimpleNamespace(model=SimpleNamespace(layers=[SimpleNamespace(self_attn=SimpleNamespace()) for _ in range(36)]))
    backend_set = RouteAQwenExternalColdStorageAttentionBackendSet(
        model, object(), layers=(0, 18, 35), kv_head=None, threshold=0.0,
        window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6,
    )
    assert set(backend_set.backends) == {0, 18, 35}
    assert backend_set.external_adapters_by_layer() == {0: None, 18: None, 35: None}


def test_qwen_multilayer_page_state_needs_one_complete_layer_head_witness():
    coverage = {"layers": [
        {"layer": 0, "heads": [{"kv_head": 6, "ever_sealed_packed_page": True, "ever_multi_page_packed": True, "max_packed_tail_tokens": 63}]},
        {"layer": 18, "heads": [{"kv_head": 3, "ever_sealed_packed_page": True, "ever_multi_page_packed": True, "max_packed_tail_tokens": 0}]},
    ]}
    assert aggregate_full_multi_tail_page_coverage(coverage) == {
        "requires_single_layer_head_full_multi_tail": True,
        "witnesses": [{"layer": 0, "kv_head": 6}],
        "covered": True,
    }


def test_qwen_alllayer_scope_requires_literal_all_and_resolves_every_layer():
    assert resolve_scope_layers(["all"], scope="all_layers", layer_count=36) == tuple(range(36))
    try:
        resolve_scope_layers(["0", "18", "35"], scope="all_layers", layer_count=36)
    except ValueError as error:
        assert "literal" in str(error)
    else:
        raise AssertionError("all-layer scope accepted an explicit subset")


def test_qwen_multilayer_runner_exposes_record_only_quantization_aware_contract(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "gate.py", "--admission-budget", "1", "--replay-source-dir", "source", "--output-dir", "fresh",
    ])
    args = parse_args(default_execution_dtype_ulp_mode="record_only", default_execution_dtype_close_mode="quantization_aware_enforce")
    assert args.execution_dtype_ulp_mode == "record_only"
    assert args.execution_dtype_close_mode == "quantization_aware_enforce"
    assert args.ulp_breach_sample_limit == 32
