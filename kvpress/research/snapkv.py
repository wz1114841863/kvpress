"""Static SnapKV terminal-prefill selection to packed-page accounting.

This is not native SnapKV decode behavior or a measured memory system.
"""
from __future__ import annotations

from typing import Any
import numpy as np
from kvpress.route_a_frontend_contract import FrontendDecision, SNAPKV_FRONTEND_NAME, SNAPKV_TERMINAL_EPOCH
from kvpress.research.packing import PackedKVSimulator, percentile, safe_divide

def decisions_to_final_drop(decisions: list[FrontendDecision]) -> tuple[np.ndarray, np.ndarray, int, int, int]:
    """Recover an explicit [layer, KV-head, position] final drop mask once."""
    if not decisions:
        raise ValueError("P1 cannot map an empty terminal decision stream")
    if {item.frontend_name for item in decisions} != {SNAPKV_FRONTEND_NAME}:
        raise ValueError("P1 accepts only the SnapKV frontend stream")
    if {item.decision_epoch for item in decisions} != {SNAPKV_TERMINAL_EPOCH}:
        raise ValueError("P1 accepts only SnapKV terminal prefill decisions")
    calls = {item.model_call_index for item in decisions}
    layers = sorted({item.layer for item in decisions})
    heads = sorted({item.kv_head for item in decisions})
    lengths = {item.sequence_length for item in decisions}
    if calls != {0} or layers != list(range(len(layers))) or heads != list(range(len(heads))) or len(lengths) != 1:
        raise ValueError("P1 requires one contiguous P0 model call with contiguous layer/KV-head IDs and one sequence length")
    sequence_length = lengths.pop()
    final_drop = np.ones((len(layers), len(heads), sequence_length), dtype=np.bool_)
    valid = np.zeros_like(final_drop, dtype=np.bool_)
    for item in decisions:
        if valid[item.layer, item.kv_head, item.original_position]:
            raise ValueError("P1 terminal stream contains a duplicate layer/KV-head/position")
        final_drop[item.layer, item.kv_head, item.original_position] = not item.keep
        valid[item.layer, item.kv_head, item.original_position] = True
    if not valid.all():
        raise ValueError("P1 terminal stream does not cover every declared identity")
    return final_drop, valid, len(layers), len(heads), sequence_length

def replay_p1(
    *,
    decisions: list[FrontendDecision],
    request_id: str,
    resident_window: int,
    page_tokens: int,
    kv_bytes_per_token: int,
    metadata_bytes_per_page: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Map the P0 terminal set into fixed hot and append-only cold pages."""
    final_drop, valid, layer_count, head_count, sequence_length = decisions_to_final_drop(decisions)
    simulator = PackedKVSimulator(page_tokens, kv_bytes_per_token, metadata_bytes_per_page)
    state = simulator.replay(final_drop, valid, resident_window)
    hot = state["hot_slots"]
    cold_kept = state["cold_logical_kept_slots"]
    cold_allocated = state["cold_allocated_slots"]
    tail_waste = state["tail_waste_slots"]
    pages = state["cold_page_count"]
    logical_total = int(valid.sum())
    logical_kept = int(((~final_drop) & valid).sum())
    terminal_drop = logical_total - logical_kept
    ideal_slots = int((hot + cold_kept).sum())
    physical_slots = int((hot + cold_allocated).sum())
    page_values = pages.reshape(-1)
    request_row = {
        "request_id": request_id,
        "frontend_name": SNAPKV_FRONTEND_NAME,
        "decision_epoch": SNAPKV_TERMINAL_EPOCH,
        "page_tokens": page_tokens,
        "resident_window": resident_window,
        "logical_total_slots": logical_total,
        "logical_kept_slots": logical_kept,
        "terminal_drop_slots": terminal_drop,
        "hot_slots": int(hot.sum()),
        "cold_logical_kept_slots": int(cold_kept.sum()),
        "cold_allocated_slots": int(cold_allocated.sum()),
        "tail_waste_slots": int(tail_waste.sum()),
        "cold_page_count": int(pages.sum()),
        "metadata_bytes_declared": int(pages.sum()) * metadata_bytes_per_page,
        "full_kv_declared_bytes": logical_total * kv_bytes_per_token,
        "ideal_packed_declared_bytes": ideal_slots * kv_bytes_per_token,
        "physical_packed_declared_bytes": physical_slots * kv_bytes_per_token,
        "total_declared_bytes_including_metadata": physical_slots * kv_bytes_per_token + int(pages.sum()) * metadata_bytes_per_page,
        "ideal_packed_slots": ideal_slots,
        "physical_allocated_slots": physical_slots,
        "full_to_ideal_packed_factor": safe_divide(logical_total, ideal_slots),
        "full_to_physical_packed_factor": safe_divide(logical_total, physical_slots),
        "tail_fragmentation_fraction": safe_divide(int(tail_waste.sum()), int(cold_allocated.sum())),
        "physical_over_ideal_slot_fraction": safe_divide(physical_slots - ideal_slots, ideal_slots),
        "head_page_count_p50": percentile(page_values, 50),
        "head_page_count_p95": percentile(page_values, 95),
        "head_page_count_p99": percentile(page_values, 99),
        "head_page_count_max": int(page_values.max()),
    }
    head_rows = []
    for layer in range(layer_count):
        for kv_head in range(head_count):
            head_hot = int(hot[layer, kv_head])
            head_cold_kept = int(cold_kept[layer, kv_head])
            head_cold_allocated = int(cold_allocated[layer, kv_head])
            head_tail = int(tail_waste[layer, kv_head])
            head_logical = sequence_length
            head_kept = head_hot + head_cold_kept
            head_rows.append(
                {
                    "request_id": request_id,
                    "page_tokens": page_tokens,
                    "resident_window": resident_window,
                    "layer": layer,
                    "kv_head": kv_head,
                    "logical_total_slots": head_logical,
                    "logical_kept_slots": head_kept,
                    "terminal_drop_slots": head_logical - head_kept,
                    "hot_slots": head_hot,
                    "cold_logical_kept_slots": head_cold_kept,
                    "cold_allocated_slots": head_cold_allocated,
                    "tail_waste_slots": head_tail,
                    "cold_page_count": int(pages[layer, kv_head]),
                    "tail_page_valid_slots": int(state["tail_page_valid_slots"][layer, kv_head]),
                    "metadata_bytes_declared": int(pages[layer, kv_head]) * metadata_bytes_per_page,
                    "full_kv_declared_bytes": head_logical * kv_bytes_per_token,
                    "ideal_packed_declared_bytes": head_kept * kv_bytes_per_token,
                    "physical_packed_declared_bytes": (head_hot + head_cold_allocated) * kv_bytes_per_token,
                    "tail_fragmentation_fraction": safe_divide(head_tail, head_cold_allocated),
                }
            )
    return request_row, head_rows
