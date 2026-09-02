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

    def __init__(self, model, predictor, *, layer: int, kv_head: int | None, threshold: float, window: int, page_tokens: int, admission_budget: int, rtol: float, atol: float, max_executed_dtype_ulps: float = 16.0) -> None:
        language_model = model.model.language_model if hasattr(model.model, "language_model") else model.model
        if not 0 <= layer < len(language_model.layers):
            raise ValueError("target layer is outside the model")
        if min(page_tokens, admission_budget) <= 0 or window < 0 or max_executed_dtype_ulps <= 0:
            raise ValueError("invalid Route-A policy dimensions")
        self.model, self.predictor, self.layer, self.kv_head = model, predictor, layer, kv_head
        self.threshold, self.window, self.page_tokens, self.admission_budget = threshold, window, page_tokens, admission_budget
        self.rtol, self.atol = rtol, atol
        self.max_executed_dtype_ulps = max_executed_dtype_ulps
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

    def coverage(self) -> dict[str, Any]:
        """Summarize per-head cold/pending coverage without inferring a mask.

        A selected KV head can legitimately have no retained mature cold token
        under the original mask. It is still substituted and numerically
        checked, but cannot be required to exercise pending staging.
        """
        if self.state is None:
            return {"selected_kv_heads": [], "heads": []}
        selected = self.selected_kv_heads(self.state.heads)
        rows = {head: [row for row in self.comparisons if int(row["kv_head"]) == head] for head in selected}
        return {
            "selected_kv_heads": list(selected),
            "heads": [
                {
                    "kv_head": head,
                    "comparison_count": len(rows[head]),
                    "max_packed_tokens": max((int(row["packed_tokens"]) for row in rows[head]), default=0),
                    "max_pending_tokens": max((int(row["pending_tokens"]) for row in rows[head]), default=0),
                    "ever_retained_cold": any(int(row["packed_tokens"]) + int(row["pending_tokens"]) > 0 for row in rows[head]),
                    "ever_pending": any(int(row["pending_tokens"]) > 0 for row in rows[head]),
                }
                for head in selected
            ],
        }

    def __enter__(self):
        self.attach(initialize_predictor=True)
        return self

    def attach(self, *, initialize_predictor: bool) -> None:
        """Install hooks; a layer-set initializes the shared predictor once."""
        if initialize_predictor:
            self.predictor.post_init_from_model(self.model)
        if self._pre_hook is not None:
            raise RuntimeError("Route-A backend is already attached")
        self._pre_hook = self.module.register_forward_pre_hook(self._capture_scores, with_kwargs=True)
        if hasattr(self.module, "route_a_backend"):
            raise RuntimeError("attention module already has a Route-A backend")
        self.module.route_a_backend = self

    def __exit__(self, exc_type, exc_value, traceback):
        self.detach()
        return None

    def detach(self) -> None:
        if self._pre_hook is not None:
            self._pre_hook.remove()
        self._pre_hook = None
        if getattr(self.module, "route_a_backend", None) is self:
            delattr(self.module, "route_a_backend")

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

    @staticmethod
    def _cast_difference_in_ulps(route: torch.Tensor, dense: torch.Tensor) -> tuple[float, float]:
        """Return max absolute difference and its maximum number of output ULPs.

        The two paths reduce in a different order. Their FP32 results are the
        semantic comparison; after casting to the model execution dtype, an
        adjacent representable value is expected in isolated reductions. The
        caller owns the explicitly recorded execution-dtype diagnostic limit;
        FP32 remains the semantic numerical guard.
        """
        difference = (route - dense).abs()
        if not route.is_floating_point():
            return float(difference.max().item()), 0.0
        positive = torch.full_like(dense, float("inf"))
        negative = torch.full_like(dense, float("-inf"))
        ulp = torch.maximum((torch.nextafter(dense, positive) - dense).abs(), (dense - torch.nextafter(dense, negative)).abs())
        ratio = torch.where(ulp > 0, difference / ulp, torch.where(difference == 0, torch.zeros_like(difference), torch.full_like(difference, float("inf"))))
        return float(difference.max().item()), float(ratio.max().item())

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
        per_head: dict[int, list[tuple[torch.Tensor, torch.Tensor, int, torch.Tensor, torch.Tensor, float]]] = {head: [] for head in selected_heads}
        for query_head in range(heads):
            mapped_kv_head = query_head // groups
            q = query[0, query_head, 0]
            if mapped_kv_head in selected_heads:
                route_fp32 = self.state.attention(q * scaling, head=mapped_kv_head)
                dense_fp32 = dense_same_mask_attention(q * scaling, self.state.same_mask_records(mapped_kv_head))
                torch.testing.assert_close(route_fp32, dense_fp32, rtol=self.rtol, atol=self.atol)
                route, dense = route_fp32.to(dtype=q.dtype), dense_fp32.to(dtype=q.dtype)
                _cast_abs, cast_ulps = self._cast_difference_in_ulps(route, dense)
                if cast_ulps > self.max_executed_dtype_ulps:
                    raise AssertionError(
                        "Route-A executed-dtype output differs from same-mask dense reference by "
                        f"{cast_ulps:.3f} ULPs, exceeding configured limit {self.max_executed_dtype_ulps:.3f}"
                    )
                output.append(route)
                per_head[mapped_kv_head].append((route, dense, query_head, route_fp32, dense_fp32, cast_ulps))
            else:
                output.append(self._dense_one(q, key[0, mapped_kv_head], value[0, mapped_kv_head], attention_mask, scaling))
        if any(not rows for rows in per_head.values()):
            raise AssertionError("selected Route-A KV head had no query-head group")
        route_output = torch.stack(output).unsqueeze(0).unsqueeze(2)
        for head, rows in per_head.items():
            selected = self.state.state_summary(head)
            selected["cache_position"] = key.shape[2] - 1
            selected["layer"] = self.layer
            selected["kv_head"] = head
            selected["query_head_count"] = len(rows)
            selected["max_abs_difference"] = max(float((route - dense).abs().max().item()) for route, dense, _query_head, _route_fp32, _dense_fp32, _cast_ulps in rows)
            selected["max_abs_difference_fp32"] = max(float((route_fp32 - dense_fp32).abs().max().item()) for _route, _dense, _query_head, route_fp32, dense_fp32, _cast_ulps in rows)
            selected["max_executed_dtype_ulps"] = max(cast_ulps for _route, _dense, _query_head, _route_fp32, _dense_fp32, cast_ulps in rows)
            selected["executed_dtype_ulp_limit"] = self.max_executed_dtype_ulps
            self.comparisons.append(selected)
        self.policy_decode_calls += 1
        return route_output, None


class RouteAPolicyAttentionBackendSet(AbstractContextManager):
    """Atomically attach Route-A policy backends to multiple model layers.

    Every member has independent hot/pending/page state but shares the one
    frozen predictor instance.  This avoids duplicating predictor weights while
    retaining per-layer original-mask decisions and numerical guards.
    """

    def __init__(self, model, predictor, *, layers: tuple[int, ...], kv_head: int | None, threshold: float, window: int, page_tokens: int, admission_budget: int, rtol: float, atol: float, max_executed_dtype_ulps: float = 16.0) -> None:
        if not layers or len(set(layers)) != len(layers) or any(layer < 0 for layer in layers):
            raise ValueError("layers must be unique non-negative indices")
        self.model, self.predictor, self.layers = model, predictor, tuple(layers)
        self.backends = {
            layer: RouteAPolicyAttentionBackend(model, predictor, layer=layer, kv_head=kv_head, threshold=threshold, window=window, page_tokens=page_tokens, admission_budget=admission_budget, rtol=rtol, atol=atol, max_executed_dtype_ulps=max_executed_dtype_ulps)
            for layer in self.layers
        }

    def __enter__(self):
        self.predictor.post_init_from_model(self.model)
        attached: list[RouteAPolicyAttentionBackend] = []
        try:
            for backend in self.backends.values():
                backend.attach(initialize_predictor=False)
                attached.append(backend)
        except BaseException:
            for backend in reversed(attached):
                backend.detach()
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        for backend in reversed(tuple(self.backends.values())):
            backend.detach()
        return None

    @property
    def comparisons(self) -> list[dict[str, float | int]]:
        return [row for backend in self.backends.values() for row in backend.comparisons]

    @property
    def policy_decode_calls(self) -> dict[int, int]:
        return {layer: backend.policy_decode_calls for layer, backend in self.backends.items()}

    def coverage(self) -> dict[str, Any]:
        return {"layers": [{"layer": layer, **backend.coverage()} for layer, backend in self.backends.items()]}
