from types import SimpleNamespace

import torch

from kvpress.route_a_policy_backend import RouteAPolicyAttentionBackend


def fake_model():
    return SimpleNamespace(model=SimpleNamespace(layers=[SimpleNamespace(self_attn=SimpleNamespace())]))


def test_selected_decode_group_uses_route_state_without_calling_original_and_reads_pending():
    backend = RouteAPolicyAttentionBackend(fake_model(), None, layer=0, kv_head=0, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    module = SimpleNamespace(scaling=1.0)
    keys = torch.tensor([[[[1., 0.], [0., 1.], [2., 0.], [0., 2.]]]])
    values = keys + 10
    backend._scores, backend._score_start = torch.ones(1, 1, 3), 0
    original_calls = []
    def original(*args, **kwargs):
        original_calls.append(True)
        return torch.zeros(1, 2, 3, 2), None
    # Prefill records the state but deliberately delegates its multi-token attention.
    backend.attention(original, module, torch.ones(1, 2, 3, 2), keys[:, :, :3], values[:, :, :3], None, 0.0, scaling=1.0)
    assert original_calls == [True]
    backend._scores, backend._score_start = torch.ones(1, 1, 1), 3
    def forbidden_original(*args, **kwargs):
        raise AssertionError("selected fast path called the original dense attention")
    output, weights = backend.attention(forbidden_original, module, torch.tensor([[[[1., 0.]], [[0., 1.]]]]), keys, values, None, 0.0, scaling=1.0)
    assert weights is None
    assert output.shape == (1, 2, 1, 2)
    assert backend.policy_decode_calls == 1
    assert backend.comparisons[0]["pending_tokens"] > 0
    assert backend.comparisons[0]["packed_tokens"] > 0


def test_all_kv_heads_replace_the_full_layer_without_calling_original_on_decode():
    backend = RouteAPolicyAttentionBackend(fake_model(), None, layer=0, kv_head=None, threshold=0.0, window=1, page_tokens=2, admission_budget=1, rtol=1e-5, atol=1e-6)
    module = SimpleNamespace(scaling=1.0)
    keys = torch.arange(16, dtype=torch.float32).reshape(1, 2, 4, 2)
    backend._scores, backend._score_start = torch.ones(1, 2, 3), 0
    backend.attention(lambda *_args, **_kwargs: (torch.zeros(1, 4, 3, 2), None), module, torch.ones(1, 4, 3, 2), keys[:, :, :3], keys[:, :, :3], None, 0.0, scaling=1.0)
    backend._scores, backend._score_start = torch.ones(1, 2, 1), 3
    output, _weights = backend.attention(lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("all-head fast path called original attention")), module, torch.ones(1, 4, 1, 2), keys, keys, None, 0.0, scaling=1.0)
    assert output.shape == (1, 4, 1, 2)
    assert {row["kv_head"] for row in backend.comparisons} == {0, 1}
    assert all(row["pending_tokens"] > 0 for row in backend.comparisons)
