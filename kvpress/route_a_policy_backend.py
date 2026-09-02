"""Minimal policy-on Route-A attention substitution for a Qwen decode gate.

The backend is deliberately narrow: batch one, a selected layer/KV head set, and
q_len=1 decode. It never mutates the model cache. Prefill records original
KVzap decisions while delegating to the model's original dense attention;
selected decode query heads then read only Route-A hot/pending/packed state.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Callable

import torch

from kvpress.route_a_attention import RouteAPackedAttentionState, dense_same_mask_attention


class RouteAPolicyAttentionBackend(AbstractContextManager):
    """Attach selected real policy-on head-groups without fake-key masking.

    ``kv_head=None`` selects every KV head in the declared layer.  That is the
    first layer-complete gate; it leaves no dense attention group in that layer.
    """

    def __init__(self, model, predictor, *, layer: int, kv_head: int | None, threshold: float, window: int, page_tokens: int, admission_budget: int, rtol: float, atol: float) -> None:
        language_model = model.model.language_model if hasattr(model.model, "language_model") else model.model
        if not 0 <= layer < len(language_model.layers):
            raise ValueError("target layer is outside the model")
        if min(page_tokens, admission_budget) <= 0 or window < 0:
            raise ValueError("invalid Route-A policy dimensions")
        self.model, self.predictor, self.layer, self.kv_head = model, predictor, layer, kv_head
        self.threshold, self.window, self.page_tokens, self.admission_budget = threshold, window, page_tokens, admission_budget
        self.rtol, self.atol = rtol, atol
        self.module = language_model.layers[layer].self_attn
        self.state: RouteAPackedAttentionState | None = None
        self._scores: torch.Tensor | None = None
        self._score_start: int | None = None
        self._pre_hook = None
        self.comparisons: list[dict[str, float | int]] = []
        self.policy_decode_calls = 0

    def selected_kv_heads(self, kv_head_count: int) -> tuple[int, ...]:
        if self.kv_head is None:
            return tuple(range(kv_head_count))
        if not 0 <= self.kv_head < kv_head_count:
            raise ValueError("target KV head is outside the model")
        return (self.kv_head,)

    def __enter__(self):
        self.predictor.post_init_from_model(self.model)
        self._pre_hook = self.module.register_forward_pre_hook(self._capture_scores, with_kwargs=True)
        if hasattr(self.module, "route_a_backend"):
            raise RuntimeError("attention module already has a Route-A backend")
        self.module.route_a_backend = self
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._pre_hook is not None:
            self._pre_hook.remove()
        self._pre_hook = None
        if getattr(self.module, "route_a_backend", None) is self:
            delattr(self.module, "route_a_backend")
        return None

    def _capture_scores(self, module, _inputs, kwargs) -> None:
        hidden = kwargs.get("hidden_states")
        positions = kwargs.get("cache_position")
        if hidden is None or positions is None or hidden.ndim != 3 or hidden.shape[0] != 1:
            raise AssertionError("Route-A backend requires [1,T,hidden] and cache positions")
        positions = positions.detach().reshape(-1)
        if positions.numel() != hidden.shape[1]:
            raise AssertionError("cache position count differs from query length")
        start = int(positions[0].item())
        expected = torch.arange(start, start + hidden.shape[1], device=positions.device, dtype=positions.dtype)
        if not torch.equal(positions, expected):
            raise AssertionError("Route-A backend requires contiguous cache positions")
        scores = self.predictor.score(module, hidden, None, None, None, kwargs)
        if scores.ndim != 3 or scores.shape[0] != 1 or scores.shape[-1] != hidden.shape[1]:
            raise AssertionError("KVzap predictor returned an incompatible score shape")
        self._scores, self._score_start = scores.detach(), start

    def _append_state(self, key: torch.Tensor, value: torch.Tensor) -> None:
        if self._scores is None or self._score_start is None:
            raise AssertionError("Route-A attention was called without a matching score capture")
        scores, start = self._scores, self._score_start
        q_len = scores.shape[-1]
        if key.ndim != 4 or value.shape != key.shape or key.shape[0] != 1 or key.shape[1] != scores.shape[1]:
            raise AssertionError("cache K/V does not match the captured KVzap score shape")
        if key.shape[2] < start + q_len:
            raise AssertionError("cache K/V does not cover newly scored positions")
        if self.state is None:
            self.selected_kv_heads(key.shape[1])
            self.state = RouteAPackedAttentionState(heads=key.shape[1], head_dim=key.shape[-1], window=self.window, page_tokens=self.page_tokens, admission_budget=self.admission_budget)
        self.state.append(key[0, :, start:start + q_len], value[0, :, start:start + q_len], scores[0] >= self.threshold, start_position=start)
        self._scores = self._score_start = None

    @staticmethod
    def _dense_one(query: torch.Tensor, key: torch.Tensor, value: torch.Tensor, attention_mask: torch.Tensor | None, scaling: float) -> torch.Tensor:
        logits = (key.float() @ query.float()) * scaling
        if attention_mask is not None:
            mask = attention_mask
            if mask.ndim == 4:
                mask = mask[0, 0, -1]
            elif mask.ndim != 1:
                raise AssertionError("unsupported attention mask shape for Route-A decode gate")
            if mask.dtype == torch.bool:
                logits = logits.masked_fill(~mask.to(device=logits.device), float("-inf"))
            else:
                logits = logits + mask.to(device=logits.device, dtype=logits.dtype)
        weights = torch.softmax(logits, dim=-1)
        return (weights[:, None] * value.float()).sum(dim=0).to(dtype=query.dtype)

    def attention(self, original: Callable[..., Any], module, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor, attention_mask: torch.Tensor | None, dropout: float, **kwargs: Any):
        """Called by the global attention wrapper after Qwen updates its cache."""
        self._append_state(key, value)
        if query.shape[0] != 1 or query.shape[2] != 1:
            return original(module, query, key, value, attention_mask, dropout, **kwargs)
        if self.state is None:
            raise AssertionError("Route-A state is unavailable after decode append")
        heads, kv_heads = query.shape[1], key.shape[1]
        if heads % kv_heads:
            raise AssertionError("query heads are not divisible by KV heads")
        groups = heads // kv_heads
        selected_heads = self.selected_kv_heads(kv_heads)
        scaling = float(kwargs.get("scaling", getattr(module, "scaling", 1.0)))
        output = []
        per_head: dict[int, list[tuple[torch.Tensor, torch.Tensor, int]]] = {head: [] for head in selected_heads}
        for query_head in range(heads):
            mapped_kv_head = query_head // groups
            q = query[0, query_head, 0]
            if mapped_kv_head in selected_heads:
                route = self.state.attention(q * scaling, head=mapped_kv_head).to(dtype=q.dtype)
                dense = dense_same_mask_attention(q * scaling, self.state.same_mask_records(mapped_kv_head)).to(dtype=q.dtype)
                torch.testing.assert_close(route, dense, rtol=self.rtol, atol=self.atol)
                output.append(route)
                per_head[mapped_kv_head].append((route, dense, query_head))
            else:
                output.append(self._dense_one(q, key[0, mapped_kv_head], value[0, mapped_kv_head], attention_mask, scaling))
        if any(not rows for rows in per_head.values()):
            raise AssertionError("selected Route-A KV head had no query-head group")
        route_output = torch.stack(output).unsqueeze(0).unsqueeze(2)
        for head, rows in per_head.items():
            selected = self.state.state_summary(head)
            selected["cache_position"] = key.shape[2] - 1
            selected["kv_head"] = head
            selected["query_head_count"] = len(rows)
            selected["max_abs_difference"] = max(float((route - dense).abs().max().item()) for route, dense, _query_head in rows)
            self.comparisons.append(selected)
        self.policy_decode_calls += 1
        return route_output, None
