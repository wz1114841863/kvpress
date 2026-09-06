"""Minimal policy-on Route-A attention substitution for a Qwen decode gate.

The backend is deliberately narrow: batch one, a selected layer/KV head set, and
q_len=1 decode. It never mutates the model cache. Prefill records original
KVzap decisions while delegating to the model's original dense attention;
selected decode query heads then read only Route-A hot/pending/packed state.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
import math
from typing import Any, Callable

import torch

from kvpress.route_a_attention import DenseSameMaskAttentionState, RouteAPackedAttentionState, dense_same_mask_attention
from kvpress.route_a_external_cold_storage import RouteAExternalColdStorageAdapter


MaskEvent = tuple[bool, float]
MaskEventLayers = dict[int, dict[tuple[int, int], MaskEvent]]


class RouteAExecutionDtypeGuardError(AssertionError):
    """Base class for bounded, serializable execution-dtype guard failures."""

    def __init__(self, details: dict[str, Any]) -> None:
        self.details = details
        super().__init__(f"Route-A execution-dtype guard failed: {details['guard_kind']}")


class RouteANumericalGuardError(RouteAExecutionDtypeGuardError):
    """A bounded, serializable execution-dtype ULP-guard failure."""

    def __init__(self, details: dict[str, Any]) -> None:
        self.details = details
        AssertionError.__init__(
            self,
            "Route-A executed-dtype output exceeds configured ULP limit: "
            f"layer={details['layer']}, kv_head={details['kv_head']}, "
            f"query_head={details['query_head']}, cache_position={details['cache_position']}, "
            f"observed_ulps={details['max_executed_dtype_ulps']}, "
            f"limit={details['executed_dtype_ulp_limit']}"
        )


class RouteAExecutionDtypeCloseGuardError(RouteAExecutionDtypeGuardError):
    """The cast output exceeds a hard executed-dtype numerical guard."""

    def __init__(self, details: dict[str, Any]) -> None:
        self.details = details
        AssertionError.__init__(
            self,
            "Route-A executed-dtype output exceeds configured tolerance envelope: "
            f"layer={details['layer']}, kv_head={details['kv_head']}, "
            f"query_head={details['query_head']}, cache_position={details['cache_position']}, "
            f"observed_ratio={details['max_tolerance_ratio']}",
        )


def compare_original_mask_events(dense_events: MaskEventLayers, route_events: MaskEventLayers, *, max_examples: int = 32) -> dict[str, Any]:
    """Compare online predictor decisions without serializing full score traces.

    Scores are retained in memory only for a small gate so an unequal digest can
    be located as concrete ``(layer, KV head, position)`` keep/drop events.
    The returned report contains a bounded difference sample, never K/V or
    token text.
    """
    report_layers = []
    for layer in sorted(set(dense_events) | set(route_events)):
        dense = dense_events.get(layer, {})
        route = route_events.get(layer, {})
        dense_keys, route_keys = set(dense), set(route)
        dense_only = sorted(dense_keys - route_keys)
        route_only = sorted(route_keys - dense_keys)
        keep_mismatches = [key for key in sorted(dense_keys & route_keys) if dense[key][0] != route[key][0]]
        examples = []
        for head, position in ([("dense_only", key) for key in dense_only] + [("route_only", key) for key in route_only] + [("keep_mismatch", key) for key in keep_mismatches])[:max_examples]:
            kind = head
            kv_head, cache_position = position
            example: dict[str, Any] = {"kind": kind, "layer": layer, "kv_head": kv_head, "cache_position": cache_position}
            if position in dense:
                example["dense"] = {"keep": dense[position][0], "score": dense[position][1]}
            if position in route:
                example["route_a"] = {"keep": route[position][0], "score": route[position][1]}
            examples.append(example)
        score_deltas = [abs(dense[key][1] - route[key][1]) for key in dense_keys & route_keys]
        report_layers.append({
            "layer": layer,
            "dense_decision_count": len(dense),
            "route_a_decision_count": len(route),
            "dense_only_event_count": len(dense_only),
            "route_a_only_event_count": len(route_only),
            "keep_mismatch_count": len(keep_mismatches),
            "max_score_abs_difference_on_common_events": max(score_deltas, default=0.0),
            "examples": examples,
        })
    matched = all(row["dense_only_event_count"] == row["route_a_only_event_count"] == row["keep_mismatch_count"] == 0 for row in report_layers)
    return {"matched": matched, "layers": report_layers}


class RouteAPolicyAttentionBackend(AbstractContextManager):
    """Attach selected real policy-on head-groups without fake-key masking.

    ``kv_head=None`` selects every KV head in the declared layer.  That is the
    first layer-complete gate; it leaves no dense attention group in that layer.
    """

    def __init__(self, model, predictor, *, layer: int, kv_head: int | None, threshold: float, window: int, page_tokens: int, admission_budget: int, rtol: float, atol: float, max_executed_dtype_ulps: float = 16.0, execution_dtype_ulp_mode: str = "enforce", execution_dtype_close_mode: str = "off", same_mask_numerical_guard_mode: str = "enforce", ulp_breach_sample_limit: int = 32, replay_mask_events: dict[tuple[int, int], MaskEvent] | None = None, component_measure=None) -> None:
        language_model = model.model.language_model if hasattr(model.model, "language_model") else model.model
        if not 0 <= layer < len(language_model.layers):
            raise ValueError("target layer is outside the model")
        if min(page_tokens, admission_budget, ulp_breach_sample_limit) <= 0 or window < 0 or max_executed_dtype_ulps <= 0:
            raise ValueError("invalid Route-A policy dimensions")
        if execution_dtype_ulp_mode not in {"enforce", "record_only"}:
            raise ValueError("execution_dtype_ulp_mode must be 'enforce' or 'record_only'")
        if execution_dtype_close_mode not in {"off", "scale_aware_enforce", "quantization_aware_enforce"}:
            raise ValueError("execution_dtype_close_mode must be 'off', 'scale_aware_enforce', or 'quantization_aware_enforce'")
        if same_mask_numerical_guard_mode not in {"enforce", "execution_only"}:
            raise ValueError("same_mask_numerical_guard_mode must be 'enforce' or 'execution_only'")
        if predictor is None and replay_mask_events is None:
            raise ValueError("an online predictor or explicit replay mask is required")
        self.model, self.predictor, self.layer, self.kv_head = model, predictor, layer, kv_head
        self.threshold, self.window, self.page_tokens, self.admission_budget = threshold, window, page_tokens, admission_budget
        self.rtol, self.atol = rtol, atol
        self.max_executed_dtype_ulps = max_executed_dtype_ulps
        self.execution_dtype_ulp_mode = execution_dtype_ulp_mode
        self.execution_dtype_close_mode = execution_dtype_close_mode
        self.same_mask_numerical_guard_mode = same_mask_numerical_guard_mode
        self.ulp_breach_sample_limit = ulp_breach_sample_limit
        self._ulp_breach_count = 0
        self._ulp_breach_max_observed: float | None = None
        self._ulp_breach_max_is_infinite = False
        self._ulp_breach_max_execution_abs_difference = 0.0
        self._ulp_breach_max_fp32_abs_difference = 0.0
        self._ulp_breach_samples: list[dict[str, Any]] = []
        self.module = language_model.layers[layer].self_attn
        self.state: RouteAPackedAttentionState | None = None
        self._scores: torch.Tensor | None = None
        self._score_start: int | None = None
        self._pre_hook = None
        self.comparisons: list[dict[str, float | int]] = []
        self.policy_decode_calls = 0
        self._mask_events: dict[tuple[int, int], MaskEvent] = {}
        self._replay_mask_events = None if replay_mask_events is None else dict(replay_mask_events)
        self._replay_seen: set[tuple[int, int]] = set()
        self._keep_mask: torch.Tensor | None = None
        self.component_measure = component_measure

    def _measure_component(self, name: str, operation):
        """Optionally label an operation without changing Route-A semantics."""
        return operation() if self.component_measure is None else self.component_measure(name, operation)

    @property
    def same_mask_numerical_guard_enforced(self) -> bool:
        return self.same_mask_numerical_guard_mode == "enforce"

    @property
    def uses_mask_replay(self) -> bool:
        return self._replay_mask_events is not None

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
            **self.state.mask_summary(),
            "heads": [
                {
                    "kv_head": head,
                    "comparison_count": len(rows[head]),
                    "max_packed_tokens": max((int(row["packed_tokens"]) for row in rows[head]), default=0),
                    "max_pending_tokens": max((int(row["pending_tokens"]) for row in rows[head]), default=0),
                    "max_packed_page_count": max((int(row["packed_page_count"]) for row in rows[head]), default=0),
                    "max_packed_full_page_count": max((int(row["packed_full_page_count"]) for row in rows[head]), default=0),
                    "max_packed_tail_tokens": max((int(row["packed_tail_tokens"]) for row in rows[head]), default=0),
                    "ever_retained_cold": any(int(row["packed_tokens"]) + int(row["pending_tokens"]) > 0 for row in rows[head]),
                    "ever_pending": any(int(row["pending_tokens"]) > 0 for row in rows[head]),
                    "ever_multi_page_packed": any(int(row["packed_page_count"]) >= 2 for row in rows[head]),
                    "ever_sealed_packed_page": any(int(row["packed_full_page_count"]) >= 1 for row in rows[head]),
                }
                for head in selected
            ],
        }

    def multi_token_comparison_summary(self) -> dict[str, Any]:
        """Return bounded selected-head diagnostics for a causal bridge.

        The rows contain scalar error summaries only.  Never serialize Q/K/V,
        attention matrices, or hidden-state tensors into a gate artifact.
        """
        rows = [row for row in self.comparisons if bool(row.get("multi_token_bridge", False))]
        return {
            "comparison_count": len(rows),
            "cache_positions": [int(row["cache_position"]) for row in rows],
            "max_attn_output_abs_difference": max((float(row["max_abs_difference"]) for row in rows), default=0.0),
            "max_attn_output_abs_difference_fp32": max((float(row["max_abs_difference_fp32"]) for row in rows), default=0.0),
            "max_executed_dtype_ulps": max((float(row["max_executed_dtype_ulps"]) for row in rows), default=0.0),
            "executed_dtype_ulp_limit": self.max_executed_dtype_ulps,
        }

    def execution_dtype_ulp_breach_summary(self) -> dict[str, Any]:
        """Summarize bounded diagnostic-only ULP breaches for this layer."""
        return {
            "mode": self.execution_dtype_ulp_mode,
            "execution_dtype_close_mode": self.execution_dtype_close_mode,
            "executed_dtype_ulp_limit": self.max_executed_dtype_ulps,
            "breach_count": self._ulp_breach_count,
            "sample_count": len(self._ulp_breach_samples),
            "sample_limit": self.ulp_breach_sample_limit,
            "max_observed_ulps": self._ulp_breach_max_observed,
            "max_observed_ulps_is_infinite": self._ulp_breach_max_is_infinite,
            "max_execution_dtype_abs_difference": self._ulp_breach_max_execution_abs_difference,
            "max_fp32_abs_difference": self._ulp_breach_max_fp32_abs_difference,
            "samples": self._ulp_breach_samples,
        }

    def __enter__(self):
        self.attach(initialize_predictor=True)
        return self

    def attach(self, *, initialize_predictor: bool) -> None:
        """Install hooks; a layer-set initializes the shared predictor once."""
        if initialize_predictor and not self.uses_mask_replay:
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
        if self._replay_mask_events is None:
            phase = "prefill" if hidden.shape[1] > 1 else "decode"
            score_operation = lambda: self.predictor.score(module, hidden, None, None, None, kwargs)
            scores = score_operation() if self.component_measure is None else self.component_measure(f"{phase}_predictor_score", score_operation)
            if scores.ndim != 3 or scores.shape[0] != 1 or scores.shape[-1] != hidden.shape[1]:
                raise AssertionError("KVzap predictor returned an incompatible score shape")
            decision_operation = lambda: scores[0] >= self.threshold
            decisions = decision_operation() if self.component_measure is None else self.component_measure(f"{phase}_predictor_mask_threshold", decision_operation)
            for head in range(scores.shape[1]):
                for offset in range(scores.shape[2]):
                    key = (head, start + offset)
                    if key in self._mask_events:
                        raise AssertionError("duplicate original-mask event for a layer/KV-head/position")
                    self._mask_events[key] = (bool(decisions[head, offset].item()), float(scores[0, head, offset].item()))
        else:
            heads_at_start = sorted(head for head, position in self._replay_mask_events if position == start)
            if not heads_at_start or heads_at_start != list(range(heads_at_start[-1] + 1)):
                raise AssertionError("replay mask lacks a contiguous KV-head set at the captured position")
            decisions = torch.empty((len(heads_at_start), hidden.shape[1]), dtype=torch.bool, device=hidden.device)
            for head in heads_at_start:
                for offset in range(hidden.shape[1]):
                    key = (head, start + offset)
                    event = self._replay_mask_events.get(key)
                    if event is None:
                        raise AssertionError(f"replay mask is missing layer {self.layer}, KV head {head}, position {start + offset}")
                    if key in self._replay_seen:
                        raise AssertionError("replay mask event was consumed more than once")
                    decisions[head, offset] = event[0]
                    self._replay_seen.add(key)
                    self._mask_events[key] = event
        self._keep_mask, self._score_start = decisions.unsqueeze(0), start

    def mask_events(self) -> dict[tuple[int, int], MaskEvent]:
        """Return a copy of gate-only predictor decision diagnostics."""
        return dict(self._mask_events)

    def assert_replay_complete(self) -> None:
        """Verify that replay consumed exactly one frozen decision per event."""
        if self._replay_mask_events is None:
            return
        missing = set(self._replay_mask_events) - self._replay_seen
        unexpected = self._replay_seen - set(self._replay_mask_events)
        if missing or unexpected:
            raise AssertionError(f"replay mask consumption mismatch: missing={len(missing)}, unexpected={len(unexpected)}")

    def replay_consumption_summary(self) -> dict[str, int | bool]:
        """Expose prefix consumption without weakening the complete-replay guard."""
        if self._replay_mask_events is None:
            return {"uses_replay": False, "events_consumed": 0, "events_total": 0, "complete": False}
        return {
            "uses_replay": True,
            "events_consumed": len(self._replay_seen),
            "events_total": len(self._replay_mask_events),
            "complete": self._replay_seen == set(self._replay_mask_events),
        }

    def _append_state(self, key: torch.Tensor, value: torch.Tensor, *, token_by_token: bool = False, after_token_append: Callable[[int, int], None] | None = None) -> None:
        if self._keep_mask is None or self._score_start is None:
            raise AssertionError("Route-A attention was called without a matching score capture")
        keep_mask, start = self._keep_mask, self._score_start
        q_len = keep_mask.shape[-1]
        if key.ndim != 4 or value.shape != key.shape or key.shape[0] != 1 or key.shape[1] != keep_mask.shape[1]:
            raise AssertionError("cache K/V does not match the captured KVzap score shape")
        if key.shape[2] < start + q_len:
            raise AssertionError("cache K/V does not cover newly scored positions")
        if self.state is None:
            self.selected_kv_heads(key.shape[1])
            self.state = self._new_state(heads=key.shape[1], head_dim=key.shape[-1])
        phase = "multi_token" if q_len > 1 else "decode"
        measure = None if self.component_measure is None else lambda name, operation: self.component_measure(f"{phase}_{name}", operation)
        if token_by_token:
            for offset in range(q_len):
                self.state.append(
                    key[0, :, start + offset:start + offset + 1],
                    value[0, :, start + offset:start + offset + 1],
                    keep_mask[0, :, offset:offset + 1],
                    start_position=start + offset,
                    component_measure=measure,
                )
                if after_token_append is not None:
                    after_token_append(offset, start + offset)
        else:
            self.state.append(key[0, :, start:start + q_len], value[0, :, start:start + q_len], keep_mask[0], start_position=start, component_measure=measure)
        self._keep_mask = self._score_start = None

    def _new_state(self, *, heads: int, head_dim: int) -> RouteAPackedAttentionState:
        return RouteAPackedAttentionState(heads=heads, head_dim=head_dim, window=self.window, page_tokens=self.page_tokens, admission_budget=self.admission_budget)

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

    @staticmethod
    def _finite_or_none(value: float) -> float | None:
        return value if math.isfinite(value) else None

    def _executed_dtype_failure_details(self, *, route: torch.Tensor, dense: torch.Tensor, route_fp32: torch.Tensor, dense_fp32: torch.Tensor, kv_head: int, query_head: int, cache_position: int) -> dict[str, Any]:
        """Capture scalar-only evidence for an execution-dtype ULP breach."""
        difference = (route - dense).abs()
        positive = torch.full_like(dense, float("inf"))
        negative = torch.full_like(dense, float("-inf"))
        ulp = torch.maximum((torch.nextafter(dense, positive) - dense).abs(), (dense - torch.nextafter(dense, negative)).abs())
        ratio = torch.where(ulp > 0, difference / ulp, torch.where(difference == 0, torch.zeros_like(difference), torch.full_like(difference, float("inf"))))
        flat_index = int(ratio.reshape(-1).argmax().item())
        component_index = list(torch.unravel_index(torch.tensor(flat_index, device=ratio.device), ratio.shape))
        index = tuple(int(item.item()) for item in component_index)
        observed_ulps = float(ratio[index].item())
        return {
            "layer": self.layer,
            "kv_head": kv_head,
            "query_head": query_head,
            "cache_position": cache_position,
            "execution_dtype": str(route.dtype),
            "output_shape": list(route.shape),
            "component_index": list(index),
            "max_executed_dtype_ulps": self._finite_or_none(observed_ulps),
            "max_executed_dtype_ulps_is_infinite": not math.isfinite(observed_ulps),
            "executed_dtype_ulp_limit": self.max_executed_dtype_ulps,
            "executed_dtype_abs_difference_at_max_ulp": self._finite_or_none(float(difference[index].item())),
            "executed_dtype_ulp_at_max": self._finite_or_none(float(ulp[index].item())),
            "route_value_at_max_ulp": self._finite_or_none(float(route[index].item())),
            "dense_value_at_max_ulp": self._finite_or_none(float(dense[index].item())),
            "max_fp32_abs_difference": self._finite_or_none(float((route_fp32 - dense_fp32).abs().max().item())),
            "route_fp32_value_at_max_ulp": self._finite_or_none(float(route_fp32[index].item())),
            "dense_fp32_value_at_max_ulp": self._finite_or_none(float(dense_fp32[index].item())),
        }

    def _handle_executed_dtype_ulp_breach(self, details: dict[str, Any]) -> None:
        """Either enforce the guard or retain scalar evidence in diagnostic mode."""
        self._ulp_breach_count += 1
        observed = details["max_executed_dtype_ulps"]
        if observed is None:
            self._ulp_breach_max_is_infinite = True
            self._ulp_breach_max_observed = None
        elif not self._ulp_breach_max_is_infinite and (self._ulp_breach_max_observed is None or observed > self._ulp_breach_max_observed):
            self._ulp_breach_max_observed = observed
        self._ulp_breach_max_execution_abs_difference = max(self._ulp_breach_max_execution_abs_difference, float(details["executed_dtype_abs_difference_at_max_ulp"] or 0.0))
        self._ulp_breach_max_fp32_abs_difference = max(self._ulp_breach_max_fp32_abs_difference, float(details["max_fp32_abs_difference"] or 0.0))
        if len(self._ulp_breach_samples) < self.ulp_breach_sample_limit:
            self._ulp_breach_samples.append(details)
        if self.execution_dtype_ulp_mode == "enforce":
            raise RouteANumericalGuardError(details)

    def _executed_dtype_close_failure_details(self, *, route: torch.Tensor, dense: torch.Tensor, route_fp32: torch.Tensor, dense_fp32: torch.Tensor, kv_head: int, query_head: int, cache_position: int) -> dict[str, Any]:
        """Return scalar context for a failed executed-dtype ``assert_close``."""
        difference = (route - dense).abs()
        tolerance = self.atol + self.rtol * dense.abs()
        ratio = difference / tolerance
        flat_index = int(ratio.reshape(-1).argmax().item())
        component_index = list(torch.unravel_index(torch.tensor(flat_index, device=ratio.device), ratio.shape))
        index = tuple(int(item.item()) for item in component_index)
        return {
            "guard_kind": "scale_aware_executed_dtype_close",
            "layer": self.layer,
            "kv_head": kv_head,
            "query_head": query_head,
            "cache_position": cache_position,
            "execution_dtype": str(route.dtype),
            "output_shape": list(route.shape),
            "component_index": list(index),
            "rtol": self.rtol,
            "atol": self.atol,
            "max_tolerance_ratio": self._finite_or_none(float(ratio[index].item())),
            "max_tolerance_ratio_is_infinite": not math.isfinite(float(ratio[index].item())),
            "executed_dtype_abs_difference_at_max_ratio": self._finite_or_none(float(difference[index].item())),
            "executed_dtype_allowed_difference_at_max_ratio": self._finite_or_none(float(tolerance[index].item())),
            "route_value_at_max_ratio": self._finite_or_none(float(route[index].item())),
            "dense_value_at_max_ratio": self._finite_or_none(float(dense[index].item())),
            "max_fp32_abs_difference": self._finite_or_none(float((route_fp32 - dense_fp32).abs().max().item())),
        }

    def _assert_executed_dtype_close(self, *, route: torch.Tensor, dense: torch.Tensor, route_fp32: torch.Tensor, dense_fp32: torch.Tensor, kv_head: int, query_head: int, cache_position: int) -> None:
        """Hard scale-aware guard for the value actually injected into Qwen."""
        if self.execution_dtype_close_mode == "off":
            return
        if self.execution_dtype_close_mode == "scale_aware_enforce":
            try:
                torch.testing.assert_close(route, dense, rtol=self.rtol, atol=self.atol)
            except AssertionError as error:
                raise RouteAExecutionDtypeCloseGuardError(
                    self._executed_dtype_close_failure_details(
                        route=route, dense=dense, route_fp32=route_fp32, dense_fp32=dense_fp32,
                        kv_head=kv_head, query_head=query_head, cache_position=cache_position,
                    )
                ) from error
            return
        if self.execution_dtype_close_mode != "quantization_aware_enforce":
            raise AssertionError("unreachable execution-dtype close mode")
        details = self._quantization_aware_executed_dtype_details(
            route=route, dense=dense, route_fp32=route_fp32, dense_fp32=dense_fp32,
            kv_head=kv_head, query_head=query_head, cache_position=cache_position,
        )
        if bool(details["all_components_within_envelope"]):
            return
        raise RouteAExecutionDtypeCloseGuardError(details)

    @staticmethod
    def _local_execution_dtype_ulp(values: torch.Tensor) -> torch.Tensor:
        """Conservative local spacing for a finite execution-dtype value."""
        positive = torch.full_like(values, float("inf"))
        negative = torch.full_like(values, float("-inf"))
        return torch.maximum(
            (torch.nextafter(values, positive) - values).abs(),
            (values - torch.nextafter(values, negative)).abs(),
        )

    def _quantization_aware_executed_dtype_details(self, *, route: torch.Tensor, dense: torch.Tensor, route_fp32: torch.Tensor, dense_fp32: torch.Tensor, kv_head: int, query_head: int, cache_position: int) -> dict[str, Any]:
        """Bound cast error by FP32 tolerance plus both local rounding steps.

        Route and dense FP32 paths are already hard-checked.  Casting each can
        round toward opposite neighboring execution-dtype values, so adding the
        two local ULP spacings is a conservative, explicit rounding envelope.
        """
        route_f32, dense_f32 = route.float(), dense.float()
        difference = (route_f32 - dense_f32).abs()
        route_ulp = self._local_execution_dtype_ulp(route).float()
        dense_ulp = self._local_execution_dtype_ulp(dense).float()
        fp32_tolerance = self.atol + self.rtol * dense_fp32.float().abs()
        allowed = fp32_tolerance + route_ulp + dense_ulp
        finite = torch.isfinite(route_f32) & torch.isfinite(dense_f32) & torch.isfinite(allowed)
        ratio = torch.where(finite, difference / allowed, torch.full_like(difference, float("inf")))
        flat_index = int(ratio.reshape(-1).argmax().item())
        component_index = list(torch.unravel_index(torch.tensor(flat_index, device=ratio.device), ratio.shape))
        index = tuple(int(item.item()) for item in component_index)
        observed_ratio = float(ratio[index].item())
        return {
            "guard_kind": "quantization_aware_executed_dtype_close",
            "layer": self.layer,
            "kv_head": kv_head,
            "query_head": query_head,
            "cache_position": cache_position,
            "execution_dtype": str(route.dtype),
            "output_shape": list(route.shape),
            "component_index": list(index),
            "rtol": self.rtol,
            "atol": self.atol,
            "max_tolerance_ratio": self._finite_or_none(observed_ratio),
            "max_tolerance_ratio_is_infinite": not math.isfinite(observed_ratio),
            "all_components_within_envelope": bool(torch.all(finite & (difference <= allowed)).item()),
            "executed_dtype_abs_difference_at_max_ratio": self._finite_or_none(float(difference[index].item())),
            "fp32_tolerance_at_max_ratio": self._finite_or_none(float(fp32_tolerance[index].item())),
            "route_local_ulp_at_max_ratio": self._finite_or_none(float(route_ulp[index].item())),
            "dense_local_ulp_at_max_ratio": self._finite_or_none(float(dense_ulp[index].item())),
            "executed_dtype_allowed_difference_at_max_ratio": self._finite_or_none(float(allowed[index].item())),
            "route_value_at_max_ratio": self._finite_or_none(float(route[index].item())),
            "dense_value_at_max_ratio": self._finite_or_none(float(dense[index].item())),
            "max_fp32_abs_difference": self._finite_or_none(float((route_fp32 - dense_fp32).abs().max().item())),
        }

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
                measure = None if self.component_measure is None else lambda name, operation: self.component_measure(f"decode_{name}", operation)
                route_fp32 = self.state.attention(q * scaling, head=mapped_kv_head, component_measure=measure)
                if self.same_mask_numerical_guard_enforced:
                    dense_fp32 = self._measure_component("decode_same_mask_dense_reference", lambda: dense_same_mask_attention(q * scaling, self.state.same_mask_records(mapped_kv_head)))
                    self._measure_component("decode_fp32_same_mask_guard", lambda: torch.testing.assert_close(route_fp32, dense_fp32, rtol=self.rtol, atol=self.atol))
                    route, dense = self._measure_component("decode_execution_dtype_cast", lambda: (route_fp32.to(dtype=q.dtype), dense_fp32.to(dtype=q.dtype)))
                    self._measure_component("decode_execution_dtype_close_guard", lambda: self._assert_executed_dtype_close(route=route, dense=dense, route_fp32=route_fp32, dense_fp32=dense_fp32, kv_head=mapped_kv_head, query_head=query_head, cache_position=int(key.shape[2] - 1)))
                    _cast_abs, cast_ulps = self._measure_component("decode_execution_dtype_ulp_diagnostic", lambda: self._cast_difference_in_ulps(route, dense))
                else:
                    route, dense, dense_fp32, cast_ulps = route_fp32.to(dtype=q.dtype), route_fp32.to(dtype=q.dtype), route_fp32, 0.0
                if self.same_mask_numerical_guard_enforced and cast_ulps > self.max_executed_dtype_ulps:
                    self._measure_component("decode_execution_dtype_ulp_breach_record", lambda: self._handle_executed_dtype_ulp_breach(
                        self._executed_dtype_failure_details(
                            route=route, dense=dense, route_fp32=route_fp32, dense_fp32=dense_fp32,
                            kv_head=mapped_kv_head, query_head=query_head,
                            cache_position=int(key.shape[2] - 1),
                        )
                    ))
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
            selected["max_abs_difference"] = self._measure_component("decode_scalar_comparison_summary", lambda: max(float((route - dense).abs().max().item()) for route, dense, _query_head, _route_fp32, _dense_fp32, _cast_ulps in rows)) if self.same_mask_numerical_guard_enforced else None
            selected["max_abs_difference_fp32"] = self._measure_component("decode_scalar_comparison_summary", lambda: max(float((route_fp32 - dense_fp32).abs().max().item()) for _route, _dense, _query_head, route_fp32, dense_fp32, _cast_ulps in rows)) if self.same_mask_numerical_guard_enforced else None
            selected["max_executed_dtype_ulps"] = self._measure_component("decode_scalar_comparison_summary", lambda: max(cast_ulps for _route, _dense, _query_head, _route_fp32, _dense_fp32, cast_ulps in rows)) if self.same_mask_numerical_guard_enforced else None
            selected["same_mask_numerical_guard_enforced"] = self.same_mask_numerical_guard_enforced
            selected["executed_dtype_ulp_limit"] = self.max_executed_dtype_ulps
            self.comparisons.append(selected)
        self.policy_decode_calls += 1
        return route_output, None


class DenseSameMaskAttentionBackend(RouteAPolicyAttentionBackend):
    """Policy-on dense KVzap control with no pending, admission, or pages.

    It scores the original KVzap mask online, preserves the regular hot window,
    and performs attention over hot plus all retained mature dense-cold K/V.
    This is intentionally separate from Route-A's internal debug reference.
    """

    def _new_state(self, *, heads: int, head_dim: int) -> DenseSameMaskAttentionState:
        return DenseSameMaskAttentionState(heads=heads, head_dim=head_dim, window=self.window)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.policy_multi_token_calls = 0
        self.policy_multi_token_tokens = 0

    def _has_prior_cold(self) -> bool:
        return self.state is not None and self.state.next_position > self.window

    def _multi_token_bridge(self, original: Callable[..., Any], module, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor, attention_mask: torch.Tensor | None, dropout: float, **kwargs: Any):
        """Causally substitute selected heads with the dense same-mask control.

        This is deliberately independent of packed Route-A storage.  It closes
        the former q_len>1 fallback, where this control delegated selected
        heads to native Full-KV attention and therefore was not a valid
        same-mask baseline for a multi-token question forward.
        """
        if self.state is None or self._keep_mask is None or self._score_start is None:
            raise AssertionError("multi-token same-mask bridge requires captured state")
        if query.shape[0] != 1 or key.ndim != 4 or value.shape != key.shape:
            raise AssertionError("multi-token same-mask bridge requires batch-one [B,H,T,D] K/V")
        heads, kv_heads, q_len = query.shape[1], key.shape[1], query.shape[2]
        if q_len <= 1 or heads % kv_heads:
            raise AssertionError("invalid multi-token same-mask GQA shape")
        if self._keep_mask.shape[-1] != q_len:
            raise AssertionError("captured mask length differs from multi-token query length")
        selected_heads = self.selected_kv_heads(kv_heads)
        groups = heads // kv_heads
        scaling = float(kwargs.get("scaling", getattr(module, "scaling", 1.0)))
        safe_key, safe_value = key.clone(), value.clone()
        for head in selected_heads:
            safe_key[0, head].zero_()
            safe_value[0, head].zero_()
        native_output, native_weights = original(module, query, safe_key, safe_value, attention_mask, dropout, **kwargs)
        expected_output_shape = (query.shape[0], q_len, heads, query.shape[-1])
        if tuple(native_output.shape) != expected_output_shape or not torch.isfinite(native_output).all():
            raise AssertionError("safe native same-mask multi-token attention returned an invalid output")
        dense_output = native_output.clone()
        per_position_rows: dict[int, dict[int, list[tuple[torch.Tensor, int]]]] = {}

        def append_and_replace(offset: int, position: int) -> None:
            if self.state is None:
                raise AssertionError("same-mask state disappeared during multi-token bridge")
            per_head: dict[int, list[tuple[torch.Tensor, int]]] = {head: [] for head in selected_heads}
            for query_head in range(heads):
                mapped = query_head // groups
                if mapped not in selected_heads:
                    continue
                q = query[0, query_head, offset]
                measure = None if self.component_measure is None else lambda name, operation: self.component_measure(f"multi_token_{name}", operation)
                dense_fp32 = self.state.attention(q * scaling, head=mapped, component_measure=measure)
                reference_fp32 = self._measure_component("multi_token_same_mask_dense_reference", lambda: dense_same_mask_attention(q * scaling, self.state.same_mask_records(mapped)))
                self._measure_component("multi_token_fp32_same_mask_guard", lambda: torch.testing.assert_close(dense_fp32, reference_fp32, rtol=self.rtol, atol=self.atol))
                dense = self._measure_component("multi_token_execution_dtype_cast", lambda: dense_fp32.to(dtype=q.dtype))
                dense_output[0, offset, query_head] = dense
                per_head[mapped].append((dense, query_head))
            if any(not rows for rows in per_head.values()):
                raise AssertionError("selected same-mask KV head had no multi-token query-head group")
            per_position_rows[position] = per_head

        self._append_state(key, value, token_by_token=True, after_token_append=append_and_replace)
        for position, by_head in sorted(per_position_rows.items()):
            for head, rows in by_head.items():
                selected = self.state.state_summary(head)
                selected.update({
                    "cache_position": position,
                    "layer": self.layer,
                    "kv_head": head,
                    "query_head_count": len(rows),
                    "max_abs_difference": 0.0,
                    "max_abs_difference_fp32": 0.0,
                    "max_executed_dtype_ulps": 0.0,
                    "executed_dtype_ulp_limit": self.max_executed_dtype_ulps,
                    "multi_token_bridge": True,
                })
                self.comparisons.append(selected)
        self.policy_multi_token_calls += 1
        self.policy_multi_token_tokens += q_len
        return dense_output, native_weights

    def attention(self, original: Callable[..., Any], module, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor, attention_mask: torch.Tensor | None, dropout: float, **kwargs: Any):
        if query.shape[2] > 1 and self._has_prior_cold():
            return self._multi_token_bridge(original, module, query, key, value, attention_mask, dropout, **kwargs)
        return super().attention(original, module, query, key, value, attention_mask, dropout, **kwargs)

    def coverage(self) -> dict[str, Any]:
        if self.state is None:
            return {"selected_kv_heads": [], "heads": []}
        selected = self.selected_kv_heads(self.state.heads)
        rows = {head: [row for row in self.comparisons if int(row["kv_head"]) == head] for head in selected}
        return {
            "selected_kv_heads": list(selected),
            **self.state.mask_summary(),
            "heads": [
                {
                    "kv_head": head,
                    "comparison_count": len(rows[head]),
                    "max_dense_cold_tokens": max((int(row["dense_cold_tokens"]) for row in rows[head]), default=0),
                    "ever_retained_cold": any(int(row["dense_cold_tokens"]) > 0 for row in rows[head]),
                }
                for head in selected
            ],
        }


class RouteAColdOwnershipAttentionBackend(RouteAPolicyAttentionBackend):
    """Route-A gate that poisons selected mature native-cache K/V slots.

    This is a semantic ownership guard, not a physical cache allocator. The
    native ``DynamicCache`` tensor retains its shape and allocation, but its
    selected mature-cold cells are overwritten with NaN after their K/V was
    appended to Route-A state. A later selected-head dense-cache read would
    therefore be observable as NaN rather than silently supplying cold K/V.
    ``kv_head=None`` selects and protects every KV head in this layer.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.native_cold_guard_checks = 0
        self.native_cold_prior_read_guard_checks = 0
        self.native_cold_poison_writes = 0
        self.policy_multi_token_calls = 0
        self.policy_multi_token_tokens = 0

    def _cold_end(self) -> int:
        if self.state is None:
            return 0
        return max(0, self.state.next_position - self.window)

    def _assert_prior_native_cold_is_poisoned(self, key: torch.Tensor, value: torch.Tensor) -> None:
        cold_end = self._cold_end()
        if cold_end == 0:
            return
        if key.ndim != 4 or value.shape != key.shape or key.shape[2] < cold_end:
            raise AssertionError("native cache does not retain the expected selected cold range")
        if not key.is_floating_point():
            raise AssertionError("cold-ownership gate requires floating-point K/V")
        for head in self.selected_kv_heads(key.shape[1]):
            if not torch.isnan(key[0, head, :cold_end]).all() or not torch.isnan(value[0, head, :cold_end]).all():
                raise AssertionError("selected mature cold K/V remained readable in the native cache")
        self.native_cold_guard_checks += 1

    def _poison_selected_native_cold(self, key: torch.Tensor, value: torch.Tensor) -> None:
        cold_end = self._cold_end()
        if cold_end == 0:
            return
        if key.ndim != 4 or value.shape != key.shape or key.shape[2] < cold_end:
            raise AssertionError("native cache cannot cover Route-A mature cold positions")
        for head in self.selected_kv_heads(key.shape[1]):
            key[0, head, :cold_end].fill_(float("nan"))
            value[0, head, :cold_end].fill_(float("nan"))
        self.native_cold_poison_writes += 1
        self._assert_prior_native_cold_is_poisoned(key, value)

    def ownership_summary(self) -> dict[str, Any]:
        if self.state is None:
            return {"selected_kv_heads": [], "native_cold_slots_physically_freed": False}
        cold_end = self._cold_end()
        heads = self.selected_kv_heads(self.state.heads)
        element_bytes = next((record.key.element_size() for head in heads for source in self.state.records(head).values() for record in source), None)
        if element_bytes is None:
            element_bytes = 0
        bytes_per_head = cold_end * self.state.head_dim * 2 * int(element_bytes)
        return {
            "selected_kv_heads": list(heads),
            "native_selected_cold_slot_tokens_per_head": cold_end,
            "native_selected_cold_slot_logical_bytes_per_head": bytes_per_head,
            "native_selected_cold_values_poisoned": self.native_cold_poison_writes > 0,
            "native_selected_cold_guard_checks": self.native_cold_guard_checks,
            "native_selected_cold_prior_read_guard_checks": self.native_cold_prior_read_guard_checks,
            "policy_multi_token_calls": self.policy_multi_token_calls,
            "policy_multi_token_tokens": self.policy_multi_token_tokens,
            "native_cold_slots_physically_freed": False,
        }

    def assert_ownership_guard_complete(self) -> None:
        if self.state is None or self._cold_end() == 0:
            raise AssertionError("cold-ownership gate never reached mature selected cold state")
        if self.native_cold_poison_writes == 0 or self.native_cold_prior_read_guard_checks == 0:
            raise AssertionError("cold-ownership gate did not poison and re-check native selected cold K/V")

    def _multi_token_bridge(self, original: Callable[..., Any], module, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor, attention_mask: torch.Tensor | None, dropout: float, **kwargs: Any):
        """Replace selected heads causally while native attention serves others.

        ``key`` already contains the whole multi-token query chunk.  Route-A
        state is therefore advanced one token at a time before each selected
        query is evaluated, preventing a query from seeing future K/V. Native
        attention receives zero placeholders for every selected KV head and its
        selected outputs are overwritten, so it cannot consume poisoned cold
        values while still computing unselected heads efficiently.
        """
        if self.state is None or self._keep_mask is None or self._score_start is None:
            raise AssertionError("multi-token ownership bridge requires captured Route-A state")
        if query.shape[0] != 1 or key.ndim != 4 or value.shape != key.shape:
            raise AssertionError("multi-token ownership bridge requires batch-one [B,H,T,D] K/V")
        heads, kv_heads, q_len = query.shape[1], key.shape[1], query.shape[2]
        if q_len <= 1 or heads % kv_heads:
            raise AssertionError("invalid multi-token Route-A GQA shape")
        if self._keep_mask.shape[-1] != q_len:
            raise AssertionError("captured mask length differs from multi-token query length")
        selected_heads = self.selected_kv_heads(kv_heads)
        groups = heads // kv_heads
        scaling = float(kwargs.get("scaling", getattr(module, "scaling", 1.0)))
        safe_key, safe_value = key.clone(), value.clone()
        for head in selected_heads:
            safe_key[0, head].zero_()
            safe_value[0, head].zero_()
        native_output, native_weights = original(module, query, safe_key, safe_value, attention_mask, dropout, **kwargs)
        if not torch.isfinite(native_output).all():
            raise AssertionError("safe native multi-token attention produced a non-finite output")
        expected_output_shape = (query.shape[0], q_len, heads, query.shape[-1])
        if tuple(native_output.shape) != expected_output_shape:
            raise AssertionError(
                "safe native multi-token attention returned unexpected layout: "
                f"got={tuple(native_output.shape)}, expected [B,T,H,D]={expected_output_shape}"
            )
        route_output = native_output.clone()
        per_position_rows: dict[int, dict[int, list[tuple[torch.Tensor, torch.Tensor, int, torch.Tensor, torch.Tensor, float]]]] = {}

        def append_and_replace(offset: int, position: int) -> None:
            if self.state is None:
                raise AssertionError("Route-A state disappeared during multi-token bridge")
            per_head: dict[int, list[tuple[torch.Tensor, torch.Tensor, int, torch.Tensor, torch.Tensor, float]]] = {head: [] for head in selected_heads}
            for query_head in range(heads):
                mapped = query_head // groups
                if mapped not in selected_heads:
                    continue
                q = query[0, query_head, offset]
                measure = None if self.component_measure is None else lambda name, operation: self.component_measure(f"multi_token_{name}", operation)
                route_fp32 = self.state.attention(q * scaling, head=mapped, component_measure=measure)
                if self.same_mask_numerical_guard_enforced:
                    dense_fp32 = self._measure_component("decode_same_mask_dense_reference", lambda: dense_same_mask_attention(q * scaling, self.state.same_mask_records(mapped)))
                    self._measure_component("decode_fp32_same_mask_guard", lambda: torch.testing.assert_close(route_fp32, dense_fp32, rtol=self.rtol, atol=self.atol))
                    route, dense = self._measure_component("decode_execution_dtype_cast", lambda: (route_fp32.to(dtype=q.dtype), dense_fp32.to(dtype=q.dtype)))
                    self._measure_component("decode_execution_dtype_close_guard", lambda: self._assert_executed_dtype_close(route=route, dense=dense, route_fp32=route_fp32, dense_fp32=dense_fp32, kv_head=mapped, query_head=query_head, cache_position=position))
                    _cast_abs, cast_ulps = self._measure_component("decode_execution_dtype_ulp_diagnostic", lambda: self._cast_difference_in_ulps(route, dense))
                else:
                    route, dense, dense_fp32, cast_ulps = route_fp32.to(dtype=q.dtype), route_fp32.to(dtype=q.dtype), route_fp32, 0.0
                if self.same_mask_numerical_guard_enforced and cast_ulps > self.max_executed_dtype_ulps:
                    self._measure_component("decode_execution_dtype_ulp_breach_record", lambda: self._handle_executed_dtype_ulp_breach(
                        self._executed_dtype_failure_details(
                            route=route, dense=dense, route_fp32=route_fp32, dense_fp32=dense_fp32,
                            kv_head=mapped, query_head=query_head, cache_position=position,
                        )
                    ))
                # Qwen attention-interface outputs use [B, T, H, D], whereas
                # its query input is [B, H, T, D].  Keeping this conversion
                # explicit prevents a multi-token selected-head result from
                # being written into the wrong token/head location.
                route_output[0, offset, query_head] = route
                per_head[mapped].append((route, dense, query_head, route_fp32, dense_fp32, cast_ulps))
            if any(not rows for rows in per_head.values()):
                raise AssertionError("selected Route-A KV head had no multi-token query-head group")
            per_position_rows[position] = per_head

        self._append_state(key, value, token_by_token=True, after_token_append=append_and_replace)
        for position, by_head in sorted(per_position_rows.items()):
            for head, rows in by_head.items():
                selected = self.state.state_summary(head)
                selected.update({
                    "cache_position": position,
                    "layer": self.layer,
                    "kv_head": head,
                    "query_head_count": len(rows),
                    "max_abs_difference": self._measure_component("decode_scalar_comparison_summary", lambda: max(float((route - dense).abs().max().item()) for route, dense, _query_head, _route_fp32, _dense_fp32, _cast_ulps in rows)) if self.same_mask_numerical_guard_enforced else None,
                    "max_abs_difference_fp32": self._measure_component("decode_scalar_comparison_summary", lambda: max(float((route_fp32 - dense_fp32).abs().max().item()) for _route, _dense, _query_head, route_fp32, dense_fp32, _cast_ulps in rows)) if self.same_mask_numerical_guard_enforced else None,
                    "max_executed_dtype_ulps": self._measure_component("decode_scalar_comparison_summary", lambda: max(cast_ulps for _route, _dense, _query_head, _route_fp32, _dense_fp32, cast_ulps in rows)) if self.same_mask_numerical_guard_enforced else None,
                    "executed_dtype_ulp_limit": self.max_executed_dtype_ulps,
                    "same_mask_numerical_guard_enforced": self.same_mask_numerical_guard_enforced,
                    "multi_token_bridge": True,
                })
                self.comparisons.append(selected)
        self.policy_multi_token_calls += 1
        self.policy_multi_token_tokens += q_len
        if not torch.isfinite(route_output).all():
            raise AssertionError("multi-token Route-A bridge produced a non-finite output")
        return route_output, native_weights

    def attention(self, original: Callable[..., Any], module, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor, attention_mask: torch.Tensor | None, dropout: float, **kwargs: Any):
        had_prior_cold = self._cold_end() > 0
        self._assert_prior_native_cold_is_poisoned(key, value)
        if had_prior_cold:
            self.native_cold_prior_read_guard_checks += 1
        result = self._multi_token_bridge(original, module, query, key, value, attention_mask, dropout, **kwargs) if query.shape[2] > 1 and had_prior_cold else super().attention(original, module, query, key, value, attention_mask, dropout, **kwargs)
        self._poison_selected_native_cold(key, value)
        if query.shape[2] == 1 and (not isinstance(result, tuple) or not torch.isfinite(result[0]).all()):
            raise AssertionError("selected ownership Route-A attention produced a non-finite decode output")
        return result


class RouteAQwenExternalColdStorageAttentionBackend(RouteAColdOwnershipAttentionBackend):
    """Qwen-hook integration of the explicit external selected-head store.

    This is intentionally *not* a ``DynamicCache`` subclass.  Qwen continues
    to provide the normal logical ``cache_position`` and its native cache is
    poisoned as an ownership guard; the selected mature K/V read path is the
    external adapter's pending/packed state.  It is the narrow bridge needed
    before a future cache-interface replacement, not physical cache release.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.external_cold_storage: RouteAExternalColdStorageAdapter | None = None
        self.external_storage_append_calls = 0

    def _append_state(self, key: torch.Tensor, value: torch.Tensor, *, token_by_token: bool = False, after_token_append: Callable[[int, int], None] | None = None) -> None:
        """Append only newly created K/V into an external logical-position store."""
        if self._keep_mask is None or self._score_start is None:
            raise AssertionError("Route-A attention was called without a matching score capture")
        keep_mask, start = self._keep_mask, self._score_start
        q_len = keep_mask.shape[-1]
        if key.ndim != 4 or value.shape != key.shape or key.shape[0] != 1 or key.shape[1] != keep_mask.shape[1]:
            raise AssertionError("cache K/V does not match the captured KVzap score shape")
        if key.shape[2] < start + q_len:
            raise AssertionError("Qwen cache K/V does not cover newly scored positions")
        if self.external_cold_storage is None:
            selected = self.selected_kv_heads(key.shape[1])
            self.external_cold_storage = RouteAExternalColdStorageAdapter(
                heads=key.shape[1], head_dim=key.shape[-1], window=self.window,
                page_tokens=self.page_tokens, admission_budget=self.admission_budget,
                selected_kv_heads=selected,
            )
            self.state = self.external_cold_storage.state
        elif self.state is not self.external_cold_storage.state:
            raise AssertionError("external cold-storage adapter lost Route-A state ownership")

        def append_one(offset: int) -> None:
            if self.external_cold_storage is None:
                raise AssertionError("external cold-storage adapter disappeared")
            position = start + offset
            self._measure_component("route_a_external_cache_append", lambda: self.external_cold_storage.append(
                key[0, :, position:position + 1], value[0, :, position:position + 1],
                keep_mask[0, :, offset:offset + 1], start_position=position,
                component_measure=self.component_measure,
            ))
            self.external_storage_append_calls += 1
            if after_token_append is not None:
                after_token_append(offset, position)

        if token_by_token:
            # The causal bridge must expose each newly appended token to its
            # corresponding query, exactly as the existing ownership backend.
            for offset in range(q_len):
                append_one(offset)
        else:
            # A normal Qwen prefill is one admission epoch.  Splitting it into
            # token calls would incorrectly spend ``admission_budget`` once per
            # token and silently drain pending staging, changing Route-A policy
            # semantics relative to the same-mask control.
            if after_token_append is not None:
                raise AssertionError("non-causal external adapter append cannot have per-token callback")
            self._measure_component("route_a_external_cache_append", lambda: self.external_cold_storage.append(
                key[0, :, start:start + q_len], value[0, :, start:start + q_len],
                keep_mask[0], start_position=start,
                component_measure=self.component_measure,
            ))
            self.external_storage_append_calls += 1
        self._keep_mask = self._score_start = None

    def external_storage_summary(self) -> dict[str, Any]:
        if self.external_cold_storage is None:
            return {
                "qwen_external_cold_storage_interface_active": False,
                "transformers_dynamic_cache_substitution": False,
                "adapter_append_calls": 0,
            }
        summary = self.external_cold_storage.ownership_summary()
        summary.update({
            "qwen_external_cold_storage_interface_active": True,
            "adapter_append_calls": self.external_storage_append_calls,
            "qwen_logical_cache_position_tokens": self.external_cold_storage.logical_cache_tokens,
        })
        return summary

    def ownership_summary(self) -> dict[str, Any]:
        summary = super().ownership_summary()
        summary["external_cold_storage"] = self.external_storage_summary()
        return summary

    def assert_external_storage_interface_complete(self) -> None:
        self.assert_ownership_guard_complete()
        if self.external_cold_storage is None:
            raise AssertionError("Qwen external cold-storage interface was never initialized")
        self.external_cold_storage.assert_storage_contract()
        summary = self.external_storage_summary()
        if not summary["qwen_external_cold_storage_interface_active"]:
            raise AssertionError("Qwen external cold-storage interface was not active")
        if summary["adapter_selected_native_cold_tensor_tokens"] != 0:
            raise AssertionError("Qwen external adapter retained selected mature cold tensors")
        if summary["qwen_logical_cache_position_tokens"] != self.state.next_position:
            raise AssertionError("Qwen logical cache position differs from external Route-A state")


class RouteAPolicyAttentionBackendSet(AbstractContextManager):
    """Atomically attach Route-A policy backends to multiple model layers.

    Every member has independent hot/pending/page state but shares the one
    frozen predictor instance.  This avoids duplicating predictor weights while
    retaining per-layer original-mask decisions and numerical guards.
    """

    backend_class = RouteAPolicyAttentionBackend

    def __init__(self, model, predictor, *, layers: tuple[int, ...], kv_head: int | None, threshold: float, window: int, page_tokens: int, admission_budget: int, rtol: float, atol: float, max_executed_dtype_ulps: float = 16.0, execution_dtype_ulp_mode: str = "enforce", execution_dtype_close_mode: str = "off", same_mask_numerical_guard_mode: str = "enforce", ulp_breach_sample_limit: int = 32, replay_mask_events: MaskEventLayers | None = None, component_measure=None) -> None:
        if not layers or len(set(layers)) != len(layers) or any(layer < 0 for layer in layers):
            raise ValueError("layers must be unique non-negative indices")
        if replay_mask_events is not None and set(replay_mask_events) != set(layers):
            raise ValueError("replay mask layers must exactly match selected layers")
        self.model, self.predictor, self.layers = model, predictor, tuple(layers)
        self.backends = {
            layer: self.backend_class(model, predictor, layer=layer, kv_head=kv_head, threshold=threshold, window=window, page_tokens=page_tokens, admission_budget=admission_budget, rtol=rtol, atol=atol, max_executed_dtype_ulps=max_executed_dtype_ulps, execution_dtype_ulp_mode=execution_dtype_ulp_mode, execution_dtype_close_mode=execution_dtype_close_mode, same_mask_numerical_guard_mode=same_mask_numerical_guard_mode, ulp_breach_sample_limit=ulp_breach_sample_limit, replay_mask_events=None if replay_mask_events is None else replay_mask_events[layer], component_measure=component_measure)
            for layer in self.layers
        }

    def __enter__(self):
        if any(not backend.uses_mask_replay for backend in self.backends.values()):
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

    def mask_events(self) -> MaskEventLayers:
        return {layer: backend.mask_events() for layer, backend in self.backends.items()}

    def assert_replay_complete(self) -> None:
        for backend in self.backends.values():
            backend.assert_replay_complete()

    def execution_dtype_ulp_breach_summary(self) -> dict[str, Any]:
        return {"layers": [{"layer": layer, **backend.execution_dtype_ulp_breach_summary()} for layer, backend in self.backends.items()]}


class DenseSameMaskAttentionBackendSet(RouteAPolicyAttentionBackendSet):
    """Multi-layer set for the independent online same-mask dense control."""

    backend_class = DenseSameMaskAttentionBackend


class RouteAColdOwnershipAttentionBackendSet(RouteAPolicyAttentionBackendSet):
    """Multi-layer Route-A set with per-layer native-cold ownership guards.

    The set deliberately retains an independent ownership state and poison/read
    audit for every selected layer.  It does not free native cache allocation;
    callers must report that boundary explicitly.
    """

    backend_class = RouteAColdOwnershipAttentionBackend

    def assert_ownership_guard_complete(self) -> None:
        for backend in self.backends.values():
            backend.assert_ownership_guard_complete()

    def ownership_summary(self) -> dict[str, Any]:
        return {
            "layers": [
                {"layer": layer, **backend.ownership_summary()}
                for layer, backend in self.backends.items()
            ]
        }


class RouteAQwenExternalColdStorageAttentionBackendSet(RouteAColdOwnershipAttentionBackendSet):
    """Multi-layer Qwen external-cold interface with one Route-A state per layer."""

    backend_class = RouteAQwenExternalColdStorageAttentionBackend

    def assert_external_storage_interface_complete(self) -> None:
        for backend in self.backends.values():
            backend.assert_external_storage_interface_complete()

    def external_adapters_by_layer(self) -> dict[int, RouteAExternalColdStorageAdapter | None]:
        return {
            layer: backend.external_cold_storage
            for layer, backend in self.backends.items()
        }
