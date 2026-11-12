"""Reusable lifecycle state and offline replay of observed decisions.

These state transitions and byte counts are a software model, not hardware
admission, memory allocation, or HBM observations.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

import numpy as np


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


def replay(events: list[dict[str, str]], *, page_tokens: int, metadata_bytes_per_page: int, kv_bytes_per_token: int, window: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return event/final/summary rows from page-size-independent admissions."""
    if page_tokens <= 0:
        raise ValueError("page_tokens must be positive")
    grouped: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
    for row in events:
        grouped[(int(row["layer"]), int(row["kv_head"]))].append(row)
    event_rows: list[dict[str, Any]] = []
    final_rows: list[dict[str, Any]] = []
    total_matured = total_admitted = total_dropped = total_allocations = total_seals = 0
    final_cache_tokens: set[int] = set()
    request_ids = {row["request_id"] for row in events}
    if len(request_ids) != 1:
        raise ValueError("A lifecycle replay input must contain exactly one request_id")
    request_id = next(iter(request_ids))
    for (layer, head), rows in sorted(grouped.items()):
        rows.sort(key=lambda row: int(row["model_call"]))
        state = PackedColdPageState(page_tokens)
        for row in rows:
            admitted = int(row["cold_admitted_tokens"])
            allocations, seals = state.append(admitted)
            matured, dropped = int(row["matured_tokens"]), int(row["cold_dropped_tokens"])
            total_matured += matured
            total_admitted += admitted
            total_dropped += dropped
            total_allocations += allocations
            total_seals += seals
            event_rows.append({
                "request_id": request_id, "page_tokens": page_tokens, "model_call": int(row["model_call"]),
                "phase": row["phase"], "layer": layer, "kv_head": head, "score_start": int(row["score_start"]),
                "q_len": int(row["q_len"]), "cache_tokens_after": int(row["cache_tokens_after"]),
                "matured_tokens": matured, "cold_admitted_tokens": admitted, "cold_dropped_tokens": dropped,
                "cold_page_allocations": allocations, "cold_page_seals": seals, "tail_valid_count": state.tail_valid_count,
                "cold_logical_tokens": state.logical_tokens, "cold_allocated_slots": state.allocated_slots,
                "tail_waste_slots": state.allocated_slots - state.logical_tokens,
                "metadata_update_bytes": allocations * metadata_bytes_per_page,
            })
        final_cache_tokens.add(int(rows[-1]["cache_tokens_after"]))
        final_rows.append({
            "request_id": request_id, "page_tokens": page_tokens, "layer": layer, "kv_head": head,
            "cold_logical_tokens": state.logical_tokens, "cold_allocated_slots": state.allocated_slots,
            "cold_page_count": state.page_count, "tail_valid_count": state.tail_valid_count,
            "tail_waste_slots": state.allocated_slots - state.logical_tokens,
            "cold_page_allocations": state.allocation_count, "cold_page_seals": state.seal_count,
        })
    if len(final_cache_tokens) != 1:
        raise ValueError("Layer/head final cache lengths disagree")
    cold_logical = sum(int(row["cold_logical_tokens"]) for row in final_rows)
    cold_allocated = sum(int(row["cold_allocated_slots"]) for row in final_rows)
    cold_pages = sum(int(row["cold_page_count"]) for row in final_rows)
    heads = len(final_rows)
    full_slots = next(iter(final_cache_tokens)) * heads
    hot_slots = min(window, next(iter(final_cache_tokens))) * heads
    ideal_slots = hot_slots + cold_logical
    physical_slots = hot_slots + cold_allocated
    summary = {
        "request_id": request_id, "page_tokens": page_tokens, "layer_heads": heads,
        "final_cache_tokens": next(iter(final_cache_tokens)), "full_kv_slots": full_slots,
        "hot_regular_slots": hot_slots, "cold_logical_tokens": cold_logical,
        "cold_allocated_slots": cold_allocated, "cold_page_count": cold_pages,
        "tail_waste_slots": cold_allocated - cold_logical,
        "fragmentation_fraction": (cold_allocated - cold_logical) / cold_allocated if cold_allocated else 0.0,
        "metadata_bytes": cold_pages * metadata_bytes_per_page, "ideal_packed_kv_slots": ideal_slots,
        "physical_packed_kv_slots": physical_slots,
        "ideal_capacity_compression": full_slots / ideal_slots if ideal_slots else 0.0,
        "physical_capacity_compression": full_slots / physical_slots if physical_slots else 0.0,
        "declared_hot_to_cold_read_bytes": sum(int(row["matured_tokens"]) for row in event_rows) * kv_bytes_per_token,
        "declared_cold_write_bytes": total_admitted * kv_bytes_per_token,
        "declared_metadata_update_bytes": total_allocations * metadata_bytes_per_page,
        "_total_dropped": total_dropped, "_total_seals": total_seals,
    }
    if total_matured != total_admitted + total_dropped:
        raise AssertionError("Replay admission conservation failed")
    return event_rows, final_rows, summary


def replay_page_sizes(
    events: list[dict[str, str]], *, page_sizes: list[int],
    metadata_bytes_per_page: int, kv_bytes_per_token: int, window: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Replay the same observed lifecycle for each requested page geometry."""
    all_events: list[dict[str, Any]] = []
    all_final: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for page in page_sizes:
        event_rows, final_rows, summary = replay(
            events, page_tokens=page, metadata_bytes_per_page=metadata_bytes_per_page,
            kv_bytes_per_token=kv_bytes_per_token, window=window,
        )
        all_events.extend(event_rows)
        all_final.extend(final_rows)
        summaries.append({key: value for key, value in summary.items() if not key.startswith("_")})
    return all_events, all_final, summaries
