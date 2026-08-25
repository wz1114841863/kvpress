"""Read-only KVzap decode-lifecycle observation and packed-page accounting.

This module deliberately has no dependency on DMSPress.  It observes attention
inputs, runs the fixed KVzap predictor, and simulates the *declared* Route-A
hot/cold lifecycle.  It never edits a model cache, attention output, mask, or
fake-key state.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import deque
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

import numpy as np
import torch


LIFECYCLE_COLUMNS = (
    "request_id", "model_call", "phase", "layer", "kv_head", "score_start", "q_len", "cache_tokens_after",
    "hot_tokens_before", "matured_tokens", "cold_admitted_tokens", "cold_dropped_tokens",
    "cold_page_allocations", "cold_page_seals", "tail_valid_count", "hot_to_cold_read_bytes",
    "cold_write_bytes", "metadata_update_bytes", "cold_logical_tokens", "cold_allocated_slots", "cold_page_count",
)
FINAL_COLUMNS = (
    "request_id", "layer", "kv_head", "cold_logical_tokens", "cold_allocated_slots", "cold_page_count",
    "tail_valid_count", "cold_page_allocations", "cold_page_seals",
)


def language_model_layers(model):
    language_model = model.model.language_model if hasattr(model.model, "language_model") else model.model
    return language_model.layers


@dataclass
class PackedColdPageState:
    page_tokens: int
    logical_tokens: int = 0
    page_count: int = 0
    tail_valid_count: int = 0
    allocation_count: int = 0
    seal_count: int = 0

    def append(self, count: int) -> tuple[int, int]:
        """Append retained tokens, returning (new page allocations, new seals)."""
        if count < 0:
            raise ValueError("admission count must be non-negative")
        allocations = seals = 0
        remaining = count
        while remaining:
            if self.page_count == 0 or self.tail_valid_count == self.page_tokens:
                self.page_count += 1
                self.allocation_count += 1
                allocations += 1
                self.tail_valid_count = 0
            added = min(self.page_tokens - self.tail_valid_count, remaining)
            self.tail_valid_count += added
            self.logical_tokens += added
            remaining -= added
            if self.tail_valid_count == self.page_tokens:
                self.seal_count += 1
                seals += 1
        return allocations, seals

    @property
    def allocated_slots(self) -> int:
        return self.page_count * self.page_tokens


class LifecycleSimulator:
    """Simulate Route-A maturity from predictor scores for one L/H score stream."""

    def __init__(self, layers: int, heads: int, window: int, page_tokens: int, kv_bytes_per_token: int, metadata_bytes_per_page: int):
        if min(layers, heads, page_tokens, kv_bytes_per_token) <= 0 or window < 0 or metadata_bytes_per_page < 0:
            raise ValueError("invalid lifecycle dimensions or byte assumptions")
        self.layers, self.heads, self.window = layers, heads, window
        self.kv_bytes_per_token = kv_bytes_per_token
        self.metadata_bytes_per_page = metadata_bytes_per_page
        self._hot: dict[int, deque[tuple[int, np.ndarray]]] = {layer: deque() for layer in range(layers)}
        self._next_position = [0] * layers
        self.pages = [[PackedColdPageState(page_tokens) for _ in range(heads)] for _ in range(layers)]

    def observe(self, layer: int, score_start: int, scores: np.ndarray, threshold: float, model_call: int, phase: str) -> list[dict[str, Any]]:
        if not 0 <= layer < self.layers or scores.ndim != 2 or scores.shape[0] != self.heads:
            raise ValueError("lifecycle scores must be [KV-head, token] for a valid layer")
        if score_start != self._next_position[layer]:
            raise AssertionError(f"Layer {layer} score positions are not contiguous: expected {self._next_position[layer]}, got {score_start}")
        q_len = scores.shape[1]
        hot_before = len(self._hot[layer])
        dropped = np.zeros(self.heads, dtype=np.int64)
        admitted = np.zeros(self.heads, dtype=np.int64)
        allocations = np.zeros(self.heads, dtype=np.int64)
        seals = np.zeros(self.heads, dtype=np.int64)
        matured_tokens = 0
        for offset in range(q_len):
            self._hot[layer].append((score_start + offset, scores[:, offset]))
            if len(self._hot[layer]) > self.window:
                _, matured_scores = self._hot[layer].popleft()
                matured_tokens += 1
                keep = matured_scores >= threshold
                for head in range(self.heads):
                    if keep[head]:
                        admitted[head] += 1
                        new_pages, new_seals = self.pages[layer][head].append(1)
                        allocations[head] += new_pages
                        seals[head] += new_seals
                    else:
                        dropped[head] += 1
        self._next_position[layer] += q_len
        cache_tokens_after = self._next_position[layer]
        rows = []
        for head in range(self.heads):
            state = self.pages[layer][head]
            rows.append({
                "model_call": model_call, "phase": phase, "layer": layer, "kv_head": head,
                "score_start": score_start, "q_len": q_len, "cache_tokens_after": cache_tokens_after,
                "hot_tokens_before": hot_before, "matured_tokens": matured_tokens,
                "cold_admitted_tokens": int(admitted[head]), "cold_dropped_tokens": int(dropped[head]),
                "cold_page_allocations": int(allocations[head]), "cold_page_seals": int(seals[head]),
                "tail_valid_count": state.tail_valid_count,
                "hot_to_cold_read_bytes": matured_tokens * self.kv_bytes_per_token,
                "cold_write_bytes": int(admitted[head]) * self.kv_bytes_per_token,
                "metadata_update_bytes": int(allocations[head]) * self.metadata_bytes_per_page,
                "cold_logical_tokens": state.logical_tokens, "cold_allocated_slots": state.allocated_slots,
                "cold_page_count": state.page_count,
            })
        return rows

    def final_rows(self) -> list[dict[str, Any]]:
        rows = []
        for layer, states in enumerate(self.pages):
            for head, state in enumerate(states):
                rows.append({"layer": layer, "kv_head": head, "cold_logical_tokens": state.logical_tokens, "cold_allocated_slots": state.allocated_slots, "cold_page_count": state.page_count, "tail_valid_count": state.tail_valid_count, "cold_page_allocations": state.allocation_count, "cold_page_seals": state.seal_count})
        return rows


class ReadOnlyKVzapLifecycleObserver(AbstractContextManager):
    """Forward-hook observer that does not alter model or cache state."""

    def __init__(self, model, predictor, *, request_id: str, threshold: float, window: int, page_tokens: int, kv_bytes_per_token: int, metadata_bytes_per_page: int, record_events: bool, admission_sink: Any | None = None):
        self.model, self.predictor, self.request_id = model, predictor, request_id
        self.threshold, self.record_events = threshold, record_events
        self.admission_sink = admission_sink
        layers = len(language_model_layers(model))
        self.simulator: LifecycleSimulator | None = None
        self._dimensions = (layers, window, page_tokens, kv_bytes_per_token, metadata_bytes_per_page)
        self._hooks = []
        self._layer_calls: dict[int, int] = {}
        self.events: list[dict[str, Any]] = []
        self.original_score_dtypes: set[str] = set()
        self._digest = hashlib.sha256()
        self._phase_summary: dict[str, dict[str, int]] = {}

    def _hook(self, module, _inputs, kwargs, _output) -> None:
        layer = int(module.layer_idx)
        hidden = kwargs.get("hidden_states")
        positions = kwargs.get("cache_position")
        if hidden is None or hidden.ndim != 3 or hidden.shape[0] != 1:
            raise AssertionError(f"Layer {layer} must expose [1,T,hidden] hidden_states")
        if positions is None:
            raise AssertionError(f"Layer {layer} does not expose cache_position required for lifecycle observation")
        flat_positions = positions.detach().reshape(-1)
        if flat_positions.numel() != hidden.shape[1]:
            raise AssertionError(f"Layer {layer} cache_position length does not match hidden-state q_len")
        score_start = int(flat_positions[0].item())
        expected = torch.arange(score_start, score_start + hidden.shape[1], device=flat_positions.device, dtype=flat_positions.dtype)
        if not torch.equal(flat_positions, expected):
            raise AssertionError(f"Layer {layer} cache_position is not contiguous")
        scores = self.predictor.score(module, hidden, None, None, None, kwargs)
        if scores.ndim != 3 or scores.shape[0] != 1 or scores.shape[1] <= 0 or scores.shape[-1] != hidden.shape[1]:
            raise AssertionError(f"Layer {layer} predictor shape {tuple(scores.shape)} is incompatible with hidden states")
        if self.simulator is None:
            layers, window, page_tokens, kv_bytes, metadata_bytes = self._dimensions
            self.simulator = LifecycleSimulator(layers, scores.shape[1], window, page_tokens, kv_bytes, metadata_bytes)
        if scores.shape[1] != self.simulator.heads:
            raise AssertionError("KV-head count changed within lifecycle observation")
        self.original_score_dtypes.add(str(scores.dtype))
        model_call = self._layer_calls.get(layer, 0)
        self._layer_calls[layer] = model_call + 1
        # KVPress first forwards the context and then the complete question;
        # the latter may itself be one token, so phase must use call order
        # rather than q_len alone.  Later one-token calls are greedy decode.
        phase = "context_prefill" if model_call == 0 else (
            "prompt_query" if model_call == 1 else "decode"
        )
        rows = self.simulator.observe(layer, score_start, scores[0].detach().to(device="cpu", dtype=torch.float32).numpy(), self.threshold, model_call, phase)
        if self.admission_sink is not None:
            # The sink may only read cache tensors and allocate its own shadow
            # storage. It is deliberately called after normal attention/cache
            # update and receives no mutable model output.
            self.admission_sink.observe(
                layer=layer, score_start=score_start, scores=scores[0].detach(),
                threshold=self.threshold, model_call=model_call, phase=phase,
                kwargs=kwargs, lifecycle_rows=rows,
            )
        summary = self._phase_summary.setdefault(phase, {
            "model_call_count": 0,
            "query_tokens": 0,
            "matured_layer_head_slots": 0,
            "cold_admitted_tokens": 0,
            "cold_dropped_tokens": 0,
            "cold_page_allocations": 0,
            "cold_page_seals": 0,
            "hot_to_cold_read_bytes": 0,
            "cold_write_bytes": 0,
            "metadata_update_bytes": 0,
        })
        # Query tokens and calls are request-level quantities, so count layer 0
        # once.  All remaining fields are explicit aggregate L/H work.
        if layer == 0:
            summary["model_call_count"] += 1
            summary["query_tokens"] += int(hidden.shape[1])
        for row in rows:
            for field in (
                "matured_tokens", "cold_admitted_tokens", "cold_dropped_tokens",
                "cold_page_allocations", "cold_page_seals", "hot_to_cold_read_bytes",
                "cold_write_bytes", "metadata_update_bytes",
            ):
                target = "matured_layer_head_slots" if field == "matured_tokens" else field
                summary[target] += int(row[field])
        for row in rows:
            encoded = json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
            self._digest.update(encoded)
            if self.record_events:
                self.events.append({"request_id": self.request_id, **row})

    def __enter__(self):
        self.predictor.post_init_from_model(self.model)
        for layer in language_model_layers(self.model):
            self._hooks.append(layer.self_attn.register_forward_hook(self._hook, with_kwargs=True))
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool | None:
        for hook in self._hooks:
            hook.remove()
        self._hooks.clear()
        return None

    @property
    def lifecycle_digest(self) -> str:
        return self._digest.hexdigest()

    def final_rows(self) -> list[dict[str, Any]]:
        if self.simulator is None:
            raise RuntimeError("No lifecycle events were observed")
        return [{"request_id": self.request_id, **row} for row in self.simulator.final_rows()]

    def summary(self) -> dict[str, Any]:
        """Return request-level counters without exposing model/cache internals.

        ``pipeline_generated_token_ids_observed`` follows KVPress's fixed
        greedy loop: the first prompt/question forward produces one token and
        every q_len=1 decode forward produces one additional token.  It is not
        a tokenizer re-encoding of the decoded answer string.
        """
        phases = {phase: dict(values) for phase, values in self._phase_summary.items()}
        decode_calls = phases.get("decode", {}).get("model_call_count", 0)
        return {
            "phase_summary": phases,
            "decode_model_call_count": decode_calls,
            "pipeline_generated_token_ids_observed": 1 + decode_calls,
        }

    def write(self, output_dir: Path) -> dict[str, Path]:
        if not self.record_events:
            raise RuntimeError("Only a recording observer can write lifecycle events")
        if not self.events:
            raise RuntimeError("No lifecycle events were recorded")
        output_dir.mkdir(parents=True, exist_ok=False)
        events = output_dir / "lifecycle_events.csv"
        final = output_dir / "lifecycle_final_state.csv"
        self._write_csv(events, self.events, LIFECYCLE_COLUMNS)
        self._write_csv(final, self.final_rows(), FINAL_COLUMNS)
        return {"events": events, "final_state": final}

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(columns))
            writer.writeheader()
            writer.writerows(rows)
