"""Read-only, calibratable Route-A3.5 KV admission shadow storage.

The Full-KV model cache remains authoritative. This module only reads the
already-updated DynamicCache from an attention post-hook and writes separately
allocated packed K/V pages. It is a reference implementation for calibration,
not a sparse-attention backend or an allocator/HBM measurement.
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch


TASK_COLUMNS = (
    "request_id", "model_call", "phase", "layer", "kv_head", "matured_tokens", "admitted_tokens", "dropped_tokens", "source_kv_bytes", "packed_kv_bytes", "position_metadata_bytes", "new_page_allocations", "cold_logical_tokens", "cold_allocated_slots", "cold_page_count", "tail_valid_count", "host_submit_us", "device_elapsed_ms",
)
BATCH_COLUMNS = (
    "request_id", "model_call", "phase", "layer", "member_head_count", "active_head_count", "matured_layer_head_slots", "admitted_tokens", "dropped_tokens", "source_kv_bytes", "packed_kv_bytes", "position_metadata_bytes", "new_page_allocations", "cold_logical_tokens", "cold_allocated_slots", "cold_page_count", "host_submit_us", "device_elapsed_ms",
)
FINAL_COLUMNS = (
    "request_id", "layer", "kv_head", "cold_logical_tokens", "cold_allocated_slots", "cold_page_count", "tail_valid_count", "cold_page_allocations", "packed_kv_bytes", "position_metadata_bytes", "key_sum", "value_sum", "position_sum",
)


@dataclass
class _HeadPages:
    page_tokens: int
    head_dim: int
    dtype: torch.dtype
    device: torch.device
    keys: list[torch.Tensor] = field(default_factory=list)
    values: list[torch.Tensor] = field(default_factory=list)
    positions: list[torch.Tensor] = field(default_factory=list)
    logical_tokens: int = 0
    tail_valid_count: int = 0
    allocation_count: int = 0

    @property
    def allocated_slots(self) -> int:
        return len(self.keys) * self.page_tokens

    def append(self, keys: torch.Tensor, values: torch.Tensor, positions: torch.Tensor) -> int:
        if keys.ndim != 2 or values.shape != keys.shape or positions.ndim != 1 or positions.numel() != keys.shape[0]:
            raise ValueError("shadow admission payload shapes disagree")
        offset, allocations = 0, 0
        while offset < keys.shape[0]:
            if not self.keys or self.tail_valid_count == self.page_tokens:
                self.keys.append(torch.empty((self.page_tokens, self.head_dim), dtype=self.dtype, device=self.device))
                self.values.append(torch.empty((self.page_tokens, self.head_dim), dtype=self.dtype, device=self.device))
                self.positions.append(torch.full((self.page_tokens,), -1, dtype=torch.int64, device=self.device))
                self.tail_valid_count = 0
                self.allocation_count += 1
                allocations += 1
            count = min(self.page_tokens - self.tail_valid_count, keys.shape[0] - offset)
            target = slice(self.tail_valid_count, self.tail_valid_count + count)
            self.keys[-1][target].copy_(keys[offset:offset + count])
            self.values[-1][target].copy_(values[offset:offset + count])
            self.positions[-1][target].copy_(positions[offset:offset + count])
            self.tail_valid_count += count
            self.logical_tokens += count
            offset += count
        return allocations

    def fingerprint(self) -> tuple[float, float, int]:
        if not self.keys:
            return 0.0, 0.0, 0
        key_sum = value_sum = 0.0
        position_sum = 0
        remaining = self.logical_tokens
        for key, value, position in zip(self.keys, self.values, self.positions, strict=True):
            count = min(self.page_tokens, remaining)
            if count <= 0:
                break
            key_sum += float(key[:count].float().sum().item())
            value_sum += float(value[:count].float().sum().item())
            position_sum += int(position[:count].sum().item())
            remaining -= count
        return key_sum, value_sum, position_sum


class PackedKVAdmissionShadow:
    """Append-only, per-layer/head packed K/V pages fed by a read-only hook."""

    def __init__(self, *, request_id: str, layers: int, heads: int, window: int, page_tokens: int, expected_kv_bytes_per_token: int, record_tasks: bool):
        if min(layers, heads, page_tokens, expected_kv_bytes_per_token) <= 0 or window < 0:
            raise ValueError("invalid A3.5 shadow dimensions")
        self.request_id, self.layers, self.heads = request_id, layers, heads
        self.window, self.page_tokens = window, page_tokens
        self.expected_kv_bytes_per_token, self.record_tasks = expected_kv_bytes_per_token, record_tasks
        self._hot: dict[int, deque[tuple[int, torch.Tensor]]] = {layer: deque() for layer in range(layers)}
        self._next_position = [0] * layers
        self._pages: dict[tuple[int, int], _HeadPages] = {}
        self._tasks: list[dict[str, Any]] = []
        self._digest = hashlib.sha256()
        self._pending_events: list[tuple[dict[str, Any], torch.cuda.Event, torch.cuda.Event]] = []
        self._finalized = False

    def _state(self, layer: int, head: int, key: torch.Tensor) -> _HeadPages:
        identity = (layer, head)
        if identity not in self._pages:
            self._pages[identity] = _HeadPages(self.page_tokens, key.shape[-1], key.dtype, key.device)
        return self._pages[identity]

    @staticmethod
    def _cache_tensors(kwargs: dict[str, Any], layer: int) -> tuple[torch.Tensor, torch.Tensor]:
        cache = kwargs.get("past_key_values")
        if cache is None or not hasattr(cache, "layers") or layer >= len(cache.layers):
            raise AssertionError("A3.5 shadow requires readable DynamicCache layers in attention kwargs")
        keys, values = cache.layers[layer].keys, cache.layers[layer].values
        if keys is None or values is None or keys.ndim != 4 or values.shape != keys.shape or keys.shape[0] != 1:
            raise AssertionError("A3.5 shadow requires cache K/V tensors shaped [1, KV-head, token, head-dim]")
        return keys, values

    def observe(self, *, layer: int, score_start: int, scores: torch.Tensor, threshold: float, model_call: int, phase: str, kwargs: dict[str, Any], lifecycle_rows: list[dict[str, Any]]) -> None:
        if self._finalized or scores.ndim != 2 or scores.shape[0] != self.heads or score_start != self._next_position[layer]:
            raise AssertionError("invalid or non-contiguous A3.5 shadow observation")
        keys, values = self._cache_tensors(kwargs, layer)
        if keys.shape[1] != self.heads or keys.shape[2] < score_start + scores.shape[1]:
            raise AssertionError("cache dimensions do not cover observed score positions")
        kv_bytes = 2 * keys.shape[-1] * keys.element_size()
        if kv_bytes != self.expected_kv_bytes_per_token:
            raise AssertionError(f"cache K+V bytes/token {kv_bytes} disagrees with declared {self.expected_kv_bytes_per_token}")
        decisions = (scores >= threshold).detach().to(device="cpu", dtype=torch.bool)
        matured: list[tuple[int, torch.Tensor]] = []
        for offset in range(scores.shape[1]):
            self._hot[layer].append((score_start + offset, decisions[:, offset]))
            if len(self._hot[layer]) > self.window:
                matured.append(self._hot[layer].popleft())
        self._next_position[layer] += scores.shape[1]
        positions = torch.tensor([position for position, _keep in matured], dtype=torch.long, device=keys.device)
        for head, lifecycle_row in enumerate(lifecycle_rows):
            if int(lifecycle_row["layer"]) != layer or int(lifecycle_row["kv_head"]) != head:
                raise AssertionError("lifecycle row ordering disagrees with shadow layer/head")
            keep = torch.tensor([bool(mask[head]) for _position, mask in matured], dtype=torch.bool, device=keys.device)
            selected_positions = positions[keep]
            expected_admitted = int(lifecycle_row["cold_admitted_tokens"])
            if selected_positions.numel() != expected_admitted:
                raise AssertionError("shadow keep decisions disagree with LifecycleSimulator admission counts")
            started = time.perf_counter_ns()
            start_event = end_event = None
            if keys.is_cuda:
                start_event, end_event = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
                start_event.record()
            allocations = 0
            state = self._state(layer, head, keys)
            if selected_positions.numel():
                gathered_keys = keys[0, head].index_select(0, selected_positions)
                gathered_values = values[0, head].index_select(0, selected_positions)
                allocations = state.append(gathered_keys, gathered_values, selected_positions)
            if end_event is not None:
                end_event.record()
            task = {
                "request_id": self.request_id, "model_call": model_call, "phase": phase, "layer": layer, "kv_head": head,
                "matured_tokens": len(matured), "admitted_tokens": int(selected_positions.numel()), "dropped_tokens": len(matured) - int(selected_positions.numel()),
                "source_kv_bytes": len(matured) * kv_bytes, "packed_kv_bytes": int(selected_positions.numel()) * kv_bytes,
                "position_metadata_bytes": int(selected_positions.numel()) * 8, "new_page_allocations": allocations,
                "cold_logical_tokens": state.logical_tokens, "cold_allocated_slots": state.allocated_slots,
                "cold_page_count": len(state.keys), "tail_valid_count": state.tail_valid_count,
                "host_submit_us": (time.perf_counter_ns() - started) / 1000.0, "device_elapsed_ms": "not_available",
            }
            semantic = {key: value for key, value in task.items() if key not in {"host_submit_us", "device_elapsed_ms"}}
            self._digest.update(json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode())
            if start_event is not None and end_event is not None:
                self._pending_events.append((task, start_event, end_event))
            if self.record_tasks:
                self._tasks.append(task)

    @property
    def semantic_digest(self) -> str:
        return self._digest.hexdigest()

    def finalize(self) -> None:
        if self._finalized:
            return
        if self._pending_events:
            torch.cuda.synchronize()
            for task, start, end in self._pending_events:
                task["device_elapsed_ms"] = start.elapsed_time(end)
        self._finalized = True

    def final_rows(self) -> list[dict[str, Any]]:
        self.finalize()
        rows = []
        for layer in range(self.layers):
            for head in range(self.heads):
                state = self._pages.get((layer, head))
                if state is None:
                    continue
                key_sum, value_sum, position_sum = state.fingerprint()
                rows.append({"request_id": self.request_id, "layer": layer, "kv_head": head, "cold_logical_tokens": state.logical_tokens, "cold_allocated_slots": state.allocated_slots, "cold_page_count": len(state.keys), "tail_valid_count": state.tail_valid_count, "cold_page_allocations": state.allocation_count, "packed_kv_bytes": state.logical_tokens * 2 * state.head_dim * torch.empty((), dtype=state.dtype).element_size(), "position_metadata_bytes": state.logical_tokens * 8, "key_sum": key_sum, "value_sum": value_sum, "position_sum": position_sum})
        return rows

    def summary(self) -> dict[str, Any]:
        self.finalize()
        rows = self.final_rows()
        return {"semantic_digest": self.semantic_digest, "task_count": len(self._tasks) if self.record_tasks else self.layers * self.heads * max(self._next_position), "admitted_tokens": sum(int(row["cold_logical_tokens"]) for row in rows), "allocated_slots": sum(int(row["cold_allocated_slots"]) for row in rows), "page_count": sum(int(row["cold_page_count"]) for row in rows)}

    def write(self, output_dir: Path) -> dict[str, Path]:
        self.finalize()
        if not self.record_tasks:
            raise RuntimeError("Only a recording A3.5 shadow can write calibration tasks")
        task_path, final_path = output_dir / "admission_shadow_tasks.csv", output_dir / "admission_shadow_final_state.csv"
        for path, rows, columns in ((task_path, self._tasks, TASK_COLUMNS), (final_path, self.final_rows(), FINAL_COLUMNS)):
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(columns))
                writer.writeheader()
                writer.writerows(rows)
        return {"tasks": task_path, "final_state": final_path}


class LayerBatchAdmissionShadow(PackedKVAdmissionShadow):
    """Reference submission batching over all KV heads of one layer/call.

    The batch is timed as one envelope but the current reference still invokes
    per-head gather/page writes internally. Therefore it measures the benefit
    of changing submission granularity, not a fused gather kernel.
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self._head_tasks: list[dict[str, Any]] = []

    def observe(self, *, layer: int, score_start: int, scores: torch.Tensor, threshold: float, model_call: int, phase: str, kwargs: dict[str, Any], lifecycle_rows: list[dict[str, Any]]) -> None:
        if self._finalized or scores.ndim != 2 or scores.shape[0] != self.heads or score_start != self._next_position[layer]:
            raise AssertionError("invalid or non-contiguous A3.5b shadow observation")
        keys, values = self._cache_tensors(kwargs, layer)
        if keys.shape[1] != self.heads or keys.shape[2] < score_start + scores.shape[1]:
            raise AssertionError("cache dimensions do not cover observed score positions")
        kv_bytes = 2 * keys.shape[-1] * keys.element_size()
        if kv_bytes != self.expected_kv_bytes_per_token:
            raise AssertionError(f"cache K+V bytes/token {kv_bytes} disagrees with declared {self.expected_kv_bytes_per_token}")
        decisions = (scores >= threshold).detach().to(device="cpu", dtype=torch.bool)
        matured: list[tuple[int, torch.Tensor]] = []
        for offset in range(scores.shape[1]):
            self._hot[layer].append((score_start + offset, decisions[:, offset]))
            if len(self._hot[layer]) > self.window:
                matured.append(self._hot[layer].popleft())
        self._next_position[layer] += scores.shape[1]
        positions = torch.tensor([position for position, _keep in matured], dtype=torch.long, device=keys.device)
        started = time.perf_counter_ns()
        start_event = end_event = None
        if keys.is_cuda:
            start_event, end_event = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
            start_event.record()
        head_tasks: list[dict[str, Any]] = []
        for head, lifecycle_row in enumerate(lifecycle_rows):
            if int(lifecycle_row["layer"]) != layer or int(lifecycle_row["kv_head"]) != head:
                raise AssertionError("lifecycle row ordering disagrees with shadow layer/head")
            keep = torch.tensor([bool(mask[head]) for _position, mask in matured], dtype=torch.bool, device=keys.device)
            selected_positions = positions[keep]
            if selected_positions.numel() != int(lifecycle_row["cold_admitted_tokens"]):
                raise AssertionError("shadow keep decisions disagree with LifecycleSimulator admission counts")
            state = self._state(layer, head, keys)
            allocations = 0
            if selected_positions.numel():
                allocations = state.append(keys[0, head].index_select(0, selected_positions), values[0, head].index_select(0, selected_positions), selected_positions)
            task = {"request_id": self.request_id, "model_call": model_call, "phase": phase, "layer": layer, "kv_head": head, "matured_tokens": len(matured), "admitted_tokens": int(selected_positions.numel()), "dropped_tokens": len(matured) - int(selected_positions.numel()), "source_kv_bytes": len(matured) * kv_bytes, "packed_kv_bytes": int(selected_positions.numel()) * kv_bytes, "position_metadata_bytes": int(selected_positions.numel()) * 8, "new_page_allocations": allocations, "cold_logical_tokens": state.logical_tokens, "cold_allocated_slots": state.allocated_slots, "cold_page_count": len(state.keys), "tail_valid_count": state.tail_valid_count, "host_submit_us": "batched_envelope", "device_elapsed_ms": "batched_envelope"}
            semantic = {key: value for key, value in task.items() if key not in {"host_submit_us", "device_elapsed_ms"}}
            self._digest.update(json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode())
            head_tasks.append(task)
        if end_event is not None:
            end_event.record()
        batch = {"request_id": self.request_id, "model_call": model_call, "phase": phase, "layer": layer, "member_head_count": self.heads, "active_head_count": sum(int(task["admitted_tokens"]) > 0 for task in head_tasks), "matured_layer_head_slots": sum(int(task["matured_tokens"]) for task in head_tasks), "admitted_tokens": sum(int(task["admitted_tokens"]) for task in head_tasks), "dropped_tokens": sum(int(task["dropped_tokens"]) for task in head_tasks), "source_kv_bytes": sum(int(task["source_kv_bytes"]) for task in head_tasks), "packed_kv_bytes": sum(int(task["packed_kv_bytes"]) for task in head_tasks), "position_metadata_bytes": sum(int(task["position_metadata_bytes"]) for task in head_tasks), "new_page_allocations": sum(int(task["new_page_allocations"]) for task in head_tasks), "cold_logical_tokens": sum(int(task["cold_logical_tokens"]) for task in head_tasks), "cold_allocated_slots": sum(int(task["cold_allocated_slots"]) for task in head_tasks), "cold_page_count": sum(int(task["cold_page_count"]) for task in head_tasks), "host_submit_us": (time.perf_counter_ns() - started) / 1000.0, "device_elapsed_ms": "not_available"}
        if start_event is not None and end_event is not None:
            self._pending_events.append((batch, start_event, end_event))
        if self.record_tasks:
            self._tasks.append(batch)
            self._head_tasks.extend(head_tasks)

    def write(self, output_dir: Path) -> dict[str, Path]:
        self.finalize()
        if not self.record_tasks:
            raise RuntimeError("Only a recording A3.5b shadow can write calibration tasks")
        batch_path = output_dir / "admission_shadow_batch_tasks.csv"
        head_path = output_dir / "admission_shadow_head_tasks.csv"
        final_path = output_dir / "admission_shadow_final_state.csv"
        for path, rows, columns in ((batch_path, self._tasks, BATCH_COLUMNS), (head_path, self._head_tasks, TASK_COLUMNS), (final_path, self.final_rows(), FINAL_COLUMNS)):
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(columns))
                writer.writeheader()
                writer.writerows(rows)
        return {"batch_tasks": batch_path, "head_tasks": head_path, "final_state": final_path}
