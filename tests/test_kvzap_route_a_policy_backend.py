from types import SimpleNamespace

import torch
from transformers import DynamicCache

from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackend, DenseSameMaskAttentionBackendSet, RouteAColdOwnershipAttentionBackend, RouteAColdOwnershipAttentionBackendSet, RouteAPolicyAttentionBackend, RouteAPolicyAttentionBackendSet, compare_original_mask_events


def fake_model(layer_count=1):
    return SimpleNamespace(model=SimpleNamespace(layers=[SimpleNamespace(self_attn=SimpleNamespace()) for _ in range(layer_count)]))


def test_selected_decode_group_uses_route_state_without_calling_original_and_reads_pending():
    backend = RouteAPolicyAttentionBackend(fake_model(), object(), layer=0, kv_head=0, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    module = SimpleNamespace(scaling=1.0)
    keys = torch.tensor([[[[1., 0.], [0., 1.], [2., 0.], [0., 2.]]]])
    values = keys + 10
    backend._keep_mask, backend._score_start = torch.ones(1, 1, 3, dtype=torch.bool), 0
    original_calls = []
    def original(*args, **kwargs):
        original_calls.append(True)
        return torch.zeros(1, 2, 3, 2), None
    # Prefill records the state but deliberately delegates its multi-token attention.
    backend.attention(original, module, torch.ones(1, 2, 3, 2), keys[:, :, :3], values[:, :, :3], None, 0.0, scaling=1.0)
    assert original_calls == [True]
    backend._keep_mask, backend._score_start = torch.ones(1, 1, 1, dtype=torch.bool), 3
    def forbidden_original(*args, **kwargs):
        raise AssertionError("selected fast path called the original dense attention")
    output, weights = backend.attention(forbidden_original, module, torch.tensor([[[[1., 0.]], [[0., 1.]]]]), keys, values, None, 0.0, scaling=1.0)
    assert weights is None
    assert output.shape == (1, 2, 1, 2)
    assert backend.policy_decode_calls == 1
    assert backend.comparisons[0]["pending_tokens"] > 0
    assert backend.comparisons[0]["packed_tokens"] > 0


def test_cold_ownership_backend_poisoning_prevents_selected_native_cold_read():
    backend = RouteAColdOwnershipAttentionBackend(fake_model(), object(), layer=0, kv_head=0, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    module = SimpleNamespace(scaling=1.0)
    keys = torch.arange(8, dtype=torch.float32).reshape(1, 1, 4, 2)
    values = keys + 10
    backend._keep_mask, backend._score_start = torch.ones(1, 1, 3, dtype=torch.bool), 0
    backend.attention(lambda *_args, **_kwargs: (torch.zeros(1, 2, 3, 2), None), module, torch.ones(1, 2, 3, 2), keys[:, :, :3], values[:, :, :3], None, 0.0, scaling=1.0)
    assert torch.isnan(keys[0, 0, :2]).all()
    assert torch.isnan(values[0, 0, :2]).all()
    assert torch.isfinite(keys[0, 0, 2:]).all()

    backend._keep_mask, backend._score_start = torch.ones(1, 1, 1, dtype=torch.bool), 3
    output, _weights = backend.attention(lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("selected owner path called dense attention")), module, torch.tensor([[[[1., 0.]], [[0., 1.]]]]), keys, values, None, 0.0, scaling=1.0)
    assert torch.isfinite(output).all()
    assert torch.isnan(keys[0, 0, :3]).all()
    backend.assert_ownership_guard_complete()
    summary = backend.ownership_summary()
    assert summary["native_selected_cold_values_poisoned"]
    assert summary["native_selected_cold_guard_checks"] >= 2
    assert summary["native_selected_cold_prior_read_guard_checks"] >= 1
    assert summary["native_selected_cold_slot_tokens_per_head"] == 3
    assert summary["native_cold_slots_physically_freed"] is False


def test_cold_ownership_backend_all_heads_replaces_every_gqa_group_with_safe_native_placeholders():
    backend = RouteAColdOwnershipAttentionBackend(fake_model(), object(), layer=0, kv_head=None, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    module = SimpleNamespace(scaling=1.0)
    keys = torch.arange(20, dtype=torch.float32).reshape(1, 2, 5, 2)
    values = keys + 10
    backend._keep_mask, backend._score_start = torch.ones(1, 2, 3, dtype=torch.bool), 0
    backend.attention(lambda *_args, **_kwargs: (torch.zeros(1, 3, 4, 2), None), module, torch.ones(1, 4, 3, 2), keys[:, :, :3], values[:, :, :3], None, 0.0, scaling=1.0)
    assert torch.isnan(keys[0, :, :2]).all()
    backend._keep_mask, backend._score_start = torch.ones(1, 2, 2, dtype=torch.bool), 3
    seen_safe_placeholder = []

    def original(_module, _query, safe_key, safe_value, _mask, _dropout, **_kwargs):
        seen_safe_placeholder.append(True)
        assert torch.equal(safe_key[0], torch.zeros_like(safe_key[0]))
        assert torch.equal(safe_value[0], torch.zeros_like(safe_value[0]))
        return torch.full((1, 2, 4, 2), 7.0), None

    query = torch.tensor([[[[1., 0.], [0., 1.]], [[0., 1.], [1., 0.]], [[1., 1.], [1., -1.]], [[-1., 1.], [1., 1.]]]])
    output, _weights = backend.attention(original, module, query, keys, values, None, 0.0, scaling=1.0)
    assert seen_safe_placeholder == [True]
    assert output.shape == (1, 2, 4, 2)
    assert torch.isfinite(output).all()
    assert not torch.equal(output, torch.full_like(output, 7.0))
    rows = [row for row in backend.comparisons if row.get("multi_token_bridge")]
    assert {(row["kv_head"], row["cache_position"]) for row in rows} == {(head, position) for head in (0, 1) for position in (3, 4)}
    assert torch.isnan(keys[0, :, :4]).all()
    assert backend.ownership_summary()["selected_kv_heads"] == [0, 1]
    backend.assert_ownership_guard_complete()


def test_cold_ownership_poison_persists_in_dynamic_cache_between_decode_updates():
    backend = RouteAColdOwnershipAttentionBackend(fake_model(), object(), layer=0, kv_head=0, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    module = SimpleNamespace(scaling=1.0)
    cache = DynamicCache()
    keys = torch.arange(6, dtype=torch.float32).reshape(1, 1, 3, 2)
    values = keys + 10
    cached_keys, cached_values = cache.update(keys, values, 0)
    backend._keep_mask, backend._score_start = torch.ones(1, 1, 3, dtype=torch.bool), 0
    backend.attention(lambda *_args, **_kwargs: (torch.zeros(1, 2, 3, 2), None), module, torch.ones(1, 2, 3, 2), cached_keys, cached_values, None, 0.0, scaling=1.0)
    assert torch.isnan(cache.layers[0].keys[0, 0, :2]).all()
    next_key = torch.tensor([[[[9.0, 10.0]]]])
    cached_keys, cached_values = cache.update(next_key, next_key + 10, 0)
    backend._keep_mask, backend._score_start = torch.ones(1, 1, 1, dtype=torch.bool), 3
    output, _weights = backend.attention(lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("selected ownership path called dense attention")), module, torch.tensor([[[[1., 0.]], [[0., 1.]]]]), cached_keys, cached_values, None, 0.0, scaling=1.0)
    assert torch.isfinite(output).all()
    assert torch.isnan(cache.layers[0].keys[0, 0, :3]).all()
    backend.assert_ownership_guard_complete()


def test_cold_ownership_multi_token_bridge_replaces_selected_heads_causally_with_safe_native_placeholders():
    backend = RouteAColdOwnershipAttentionBackend(fake_model(), object(), layer=0, kv_head=0, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    module = SimpleNamespace(scaling=1.0)
    keys = torch.arange(10, dtype=torch.float32).reshape(1, 1, 5, 2)
    values = keys + 10
    backend._keep_mask, backend._score_start = torch.ones(1, 1, 3, dtype=torch.bool), 0
    # Native Qwen output is [B,T,H,D].  Use H=4 and T=2 below so a mistaken
    # [B,H,T,D] write cannot be hidden by equal dimensions.
    backend.attention(lambda *_args, **_kwargs: (torch.zeros(1, 3, 4, 2), None), module, torch.ones(1, 4, 3, 2), keys[:, :, :3], values[:, :, :3], None, 0.0, scaling=1.0)
    assert torch.isnan(keys[0, 0, :2]).all()
    backend._keep_mask, backend._score_start = torch.ones(1, 1, 2, dtype=torch.bool), 3
    seen_safe_placeholder = []

    def original(_module, _query, safe_key, safe_value, _mask, _dropout, **_kwargs):
        seen_safe_placeholder.append(True)
        assert torch.isfinite(safe_key).all() and torch.isfinite(safe_value).all()
        assert torch.equal(safe_key[0, 0], torch.zeros_like(safe_key[0, 0]))
        return torch.full((1, 2, 4, 2), 7.0), None

    query = torch.tensor([[[[1., 0.], [0., 1.]], [[0., 1.], [1., 0.]], [[1., 1.], [1., -1.]], [[-1., 1.], [1., 1.]]]])
    output, _weights = backend.attention(original, module, query, keys, values, None, 0.0, scaling=1.0)
    assert seen_safe_placeholder == [True]
    assert output.shape == (1, 2, 4, 2)
    assert torch.isfinite(output).all()
    assert not torch.equal(output, torch.full_like(output, 7.0))
    assert backend.policy_multi_token_calls == 1
    assert backend.policy_multi_token_tokens == 2
    rows = [row for row in backend.comparisons if row.get("multi_token_bridge")]
    assert [row["cache_position"] for row in rows] == [3, 4]
    assert torch.isnan(keys[0, 0, :4]).all()
    backend.assert_ownership_guard_complete()


def test_dense_same_mask_multi_token_bridge_does_not_fall_back_to_full_kv_selected_heads():
    backend = DenseSameMaskAttentionBackend(fake_model(), object(), layer=0, kv_head=0, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    module = SimpleNamespace(scaling=1.0)
    keys = torch.arange(10, dtype=torch.float32).reshape(1, 1, 5, 2)
    values = keys + 10
    backend._keep_mask, backend._score_start = torch.ones(1, 1, 3, dtype=torch.bool), 0
    backend.attention(lambda *_args, **_kwargs: (torch.zeros(1, 3, 4, 2), None), module, torch.ones(1, 4, 3, 2), keys[:, :, :3], values[:, :, :3], None, 0.0, scaling=1.0)
    backend._keep_mask, backend._score_start = torch.ones(1, 1, 2, dtype=torch.bool), 3
    native_calls = []

    def original(_module, _query, safe_key, safe_value, _mask, _dropout, **_kwargs):
        native_calls.append(True)
        assert torch.equal(safe_key[0, 0], torch.zeros_like(safe_key[0, 0]))
        assert torch.equal(safe_value[0, 0], torch.zeros_like(safe_value[0, 0]))
        return torch.full((1, 2, 4, 2), 7.0), None

    query = torch.tensor([[[[1., 0.], [0., 1.]], [[0., 1.], [1., 0.]], [[1., 1.], [1., -1.]], [[-1., 1.], [1., 1.]]]])
    output, _weights = backend.attention(original, module, query, keys, values, None, 0.0, scaling=1.0)
    assert native_calls == [True]
    assert output.shape == (1, 2, 4, 2)
    assert not torch.equal(output, torch.full_like(output, 7.0))
    assert backend.policy_multi_token_calls == 1
    assert backend.policy_multi_token_tokens == 2
    assert backend.multi_token_comparison_summary()["comparison_count"] == 2
    assert backend.multi_token_comparison_summary()["max_attn_output_abs_difference"] == 0.0


def test_all_kv_heads_replace_the_full_layer_without_calling_original_on_decode():
    backend = RouteAPolicyAttentionBackend(fake_model(), object(), layer=0, kv_head=None, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    module = SimpleNamespace(scaling=1.0)
    keys = torch.arange(16, dtype=torch.float32).reshape(1, 2, 4, 2)
    backend._keep_mask, backend._score_start = torch.ones(1, 2, 3, dtype=torch.bool), 0
    backend.attention(lambda *_args, **_kwargs: (torch.zeros(1, 4, 3, 2), None), module, torch.ones(1, 4, 3, 2), keys[:, :, :3], keys[:, :, :3], None, 0.0, scaling=1.0)
    backend._keep_mask, backend._score_start = torch.ones(1, 2, 1, dtype=torch.bool), 3
    output, _weights = backend.attention(lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("all-head fast path called original attention")), module, torch.ones(1, 4, 1, 2), keys, keys, None, 0.0, scaling=1.0)
    assert output.shape == (1, 4, 1, 2)
    assert {row["kv_head"] for row in backend.comparisons} == {0, 1}
    assert all(row["pending_tokens"] > 0 for row in backend.comparisons)
    coverage = backend.coverage()
    assert coverage["original_mask_decision_count"] == 8
    assert len(coverage["original_mask_sha256"]) == 64
    assert {key: value for key, value in coverage.items() if key not in {"original_mask_decision_count", "original_mask_sha256"}} == {"selected_kv_heads": [0, 1], "heads": [{"kv_head": 0, "comparison_count": 1, "max_packed_tokens": 1, "max_pending_tokens": 2, "max_packed_page_count": 1, "max_packed_full_page_count": 0, "max_packed_tail_tokens": 1, "ever_retained_cold": True, "ever_pending": True, "ever_multi_page_packed": False, "ever_sealed_packed_page": False}, {"kv_head": 1, "comparison_count": 1, "max_packed_tokens": 1, "max_pending_tokens": 2, "max_packed_page_count": 1, "max_packed_full_page_count": 0, "max_packed_tail_tokens": 1, "ever_retained_cold": True, "ever_pending": True, "ever_multi_page_packed": False, "ever_sealed_packed_page": False}]}


def test_executed_dtype_ulp_diagnostic_is_measured_independently_of_fp32_guard():
    dense = torch.tensor([0.015625], dtype=torch.float16)
    one_ulp = torch.nextafter(dense, torch.full_like(dense, float("inf")))
    two_ulps = torch.nextafter(one_ulp, torch.full_like(one_ulp, float("inf")))
    _difference, one_ratio = RouteAPolicyAttentionBackend._cast_difference_in_ulps(one_ulp, dense)
    _difference, two_ratio = RouteAPolicyAttentionBackend._cast_difference_in_ulps(two_ulps, dense)
    assert one_ratio == 1.0
    assert two_ratio == 2.0


def test_executed_dtype_ulp_limit_is_explicit_and_validated():
    backend = RouteAPolicyAttentionBackend(fake_model(), object(), layer=0, kv_head=0, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6, max_executed_dtype_ulps=16.0)
    assert backend.max_executed_dtype_ulps == 16.0
    try:
        RouteAPolicyAttentionBackend(fake_model(), object(), layer=0, kv_head=0, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6, max_executed_dtype_ulps=0.0)
    except ValueError as error:
        assert "invalid Route-A policy dimensions" in str(error)
    else:
        raise AssertionError("non-positive execution-dtype ULP limit was accepted")


def test_backend_set_keeps_independent_layer_state_and_aggregates_coverage():
    backend_set = RouteAPolicyAttentionBackendSet(fake_model(2), object(), layers=(0, 1), kv_head=None, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    keys = torch.arange(16, dtype=torch.float32).reshape(1, 2, 4, 2)
    for layer, backend in backend_set.backends.items():
        module = SimpleNamespace(scaling=1.0)
        backend._keep_mask, backend._score_start = torch.ones(1, 2, 3, dtype=torch.bool), 0
        backend.attention(lambda *_args, **_kwargs: (torch.zeros(1, 4, 3, 2), None), module, torch.ones(1, 4, 3, 2), keys[:, :, :3], keys[:, :, :3], None, 0.0, scaling=1.0)
        backend._keep_mask, backend._score_start = torch.ones(1, 2, 1, dtype=torch.bool), 3
        backend.attention(lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("route layer called original attention")), module, torch.ones(1, 4, 1, 2), keys, keys, None, 0.0, scaling=1.0)
        assert backend.policy_decode_calls == 1
    assert backend_set.policy_decode_calls == {0: 1, 1: 1}
    assert len(backend_set.comparisons) == 4
    assert [row["layer"] for row in backend_set.coverage()["layers"]] == [0, 1]


def test_cold_ownership_backend_set_builds_one_guarded_backend_per_layer():
    backend_set = RouteAColdOwnershipAttentionBackendSet(fake_model(2), object(), layers=(0, 1), kv_head=None, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    assert list(backend_set.backends) == [0, 1]
    assert all(isinstance(item, RouteAColdOwnershipAttentionBackend) for item in backend_set.backends.values())
    assert [row["layer"] for row in backend_set.ownership_summary()["layers"]] == [0, 1]


def test_dense_same_mask_backend_has_no_route_a_pending_or_packed_state():
    backend = DenseSameMaskAttentionBackend(fake_model(), object(), layer=0, kv_head=None, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    keys = torch.arange(16, dtype=torch.float32).reshape(1, 2, 4, 2)
    module = SimpleNamespace(scaling=1.0)
    backend._keep_mask, backend._score_start = torch.ones(1, 2, 3, dtype=torch.bool), 0
    backend.attention(lambda *_args, **_kwargs: (torch.zeros(1, 4, 3, 2), None), module, torch.ones(1, 4, 3, 2), keys[:, :, :3], keys[:, :, :3], None, 0.0, scaling=1.0)
    backend._keep_mask, backend._score_start = torch.ones(1, 2, 1, dtype=torch.bool), 3
    backend.attention(lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("dense same-mask path called original attention")), module, torch.ones(1, 4, 1, 2), keys, keys, None, 0.0, scaling=1.0)
    assert all("dense_cold_tokens" in row for row in backend.comparisons)
    assert all("pending_tokens" not in row and "packed_tokens" not in row for row in backend.comparisons)
    assert backend.coverage()["original_mask_decision_count"] == 8
    backend_set = DenseSameMaskAttentionBackendSet(fake_model(2), object(), layers=(0, 1), kv_head=None, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    assert all(isinstance(item, DenseSameMaskAttentionBackend) for item in backend_set.backends.values())


def test_online_mask_drift_report_locates_keep_flip_and_event_coverage_gap():
    dense = {0: {(0, 10): (True, -3.99), (1, 10): (False, -4.01)}, 1: {(0, 11): (True, -3.5)}}
    route = {0: {(0, 10): (False, -4.001), (1, 10): (False, -4.02), (2, 10): (True, -3.0)}}
    report = compare_original_mask_events(dense, route, max_examples=4)
    assert not report["matched"]
    layer0, layer1 = report["layers"]
    assert layer0["keep_mismatch_count"] == 1
    assert layer0["route_a_only_event_count"] == 1
    assert layer1["dense_only_event_count"] == 1
    keep_flip = next(row for row in layer0["examples"] if row["kind"] == "keep_mismatch")
    assert keep_flip == {"kind": "keep_mismatch", "layer": 0, "kv_head": 0, "cache_position": 10, "dense": {"keep": True, "score": -3.99}, "route_a": {"keep": False, "score": -4.001}}


def test_replay_mask_bypasses_predictor_and_consumes_every_frozen_event_once():
    replay = {(0, 0): (True, -3.9), (0, 1): (False, -4.1), (0, 2): (True, -3.8)}
    backend = RouteAPolicyAttentionBackend(fake_model(), None, layer=0, kv_head=0, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6, replay_mask_events=replay)
    hidden = torch.zeros(1, 3, 2)
    backend._capture_scores(SimpleNamespace(), (), {"hidden_states": hidden, "cache_position": torch.arange(3)})
    assert backend.uses_mask_replay
    assert torch.equal(backend._keep_mask, torch.tensor([[[True, False, True]]]))
    keys = torch.arange(6, dtype=torch.float32).reshape(1, 1, 3, 2)
    backend._append_state(keys, keys)
    assert backend.mask_events() == replay
    backend.assert_replay_complete()


def test_online_predictor_component_labels_are_separate_from_replay_components():
    class Predictor:
        def score(self, _module, hidden, *_args):
            return torch.zeros(1, 1, hidden.shape[1])

    names = []

    def measure(name, operation):
        names.append(name)
        return operation()

    backend = RouteAPolicyAttentionBackend(fake_model(), Predictor(), layer=0, kv_head=0, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6, component_measure=measure)
    backend._capture_scores(SimpleNamespace(), (), {"hidden_states": torch.zeros(1, 2, 4), "cache_position": torch.arange(2)})
    assert names == ["prefill_predictor_score", "prefill_predictor_mask_threshold"]
