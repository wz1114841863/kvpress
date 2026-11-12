"""Offline Route-A traffic and amortization over lifecycle replay rows.

The bytes and cycles are declared accounting models, not measurements.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def task_cycles(slots: int, page_count: int, *, kv_bytes: int, bandwidth: float, throughput: float, ops_per_token: float, metadata_lookup_bytes: int, metadata_lookup_cycles: float) -> float:
    if slots < 0 or page_count < 0:
        raise ValueError("slots/page count must be non-negative")
    bytes_cost = (slots * kv_bytes + page_count * metadata_lookup_bytes) / bandwidth
    compute_cost = slots * ops_per_token / throughput
    return max(bytes_cost, compute_cost) + page_count * metadata_lookup_cycles


def layer_cycles(tasks: list[tuple[int, float]], *, pe_count: int, policy: str, head_dispatch_cycles: float) -> float:
    """One layer barrier with static affinity or whole-head LPT scheduling."""
    loads = [0.0] * pe_count
    if policy == "static_head":
        for head, cycles in tasks:
            loads[head % pe_count] += cycles
    elif policy == "length_aware_head":
        for _head, cycles in sorted(tasks, key=lambda item: (-item[1], item[0])):
            pe = min(range(pe_count), key=lambda index: loads[index])
            loads[pe] += cycles + head_dispatch_cycles
    else:
        raise ValueError(f"Unsupported scheduler policy: {policy}")
    return max(loads, default=0.0)


def attention_cycles(rows: list[dict[str, str]], *, kind: str, page_tokens: int, window: int, kv_bytes: int, bandwidth: float, throughput: float, ops_per_token: float, metadata_lookup_bytes: int, metadata_lookup_cycles: float, pe_count: int, policy: str, head_dispatch_cycles: float) -> float:
    by_layer: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for row in rows:
        cache = int(row["cache_tokens_after"])
        hot = min(window, cache)
        if kind == "full":
            slots, pages = cache, 0
        elif kind == "ideal":
            slots, pages = hot + int(row["cold_logical_tokens"]), 0
        elif kind == "physical":
            slots, pages = hot + int(row["cold_allocated_slots"]), int(row["cold_allocated_slots"]) // page_tokens
        else:
            raise ValueError(f"Unknown attention kind: {kind}")
        by_layer[int(row["layer"])].append((int(row["kv_head"]), task_cycles(slots, pages, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=metadata_lookup_bytes, metadata_lookup_cycles=metadata_lookup_cycles)))
    return sum(layer_cycles(tasks, pe_count=pe_count, policy=policy, head_dispatch_cycles=head_dispatch_cycles) for _, tasks in sorted(by_layer.items()))


def policy_variants(oracle_min_decode_steps: list[int], deferred_admission_decode_steps: list[int]) -> list[dict[str, Any]]:
    """Describe fixed baselines plus optional, separately-labelled policy cases."""
    variants = [
        {"id": "full_kv", "baseline": "full_kv", "policy_kind": "fixed", "threshold": "", "attention": "full", "scheduler": "static_head"},
        {"id": "ideal_packed_kvzap", "baseline": "ideal_packed_kvzap", "policy_kind": "fixed", "threshold": "", "attention": "ideal", "scheduler": "static_head"},
        {"id": "packed_static_head", "baseline": "packed_static_head", "policy_kind": "fixed", "threshold": "", "attention": "physical", "scheduler": "static_head"},
        {"id": "packed_length_aware_head", "baseline": "packed_length_aware_head", "policy_kind": "fixed", "threshold": "", "attention": "physical", "scheduler": "length_aware_head"},
    ]
    for threshold in oracle_min_decode_steps:
        variants.extend([
            {"id": f"packed_oracle_static_head:{threshold}", "baseline": "packed_oracle_static_head", "policy_kind": "oracle_horizon_gate", "threshold": threshold, "attention": "physical", "scheduler": "static_head"},
            {"id": f"packed_oracle_length_aware_head:{threshold}", "baseline": "packed_oracle_length_aware_head", "policy_kind": "oracle_horizon_gate", "threshold": threshold, "attention": "physical", "scheduler": "length_aware_head"},
        ])
    for threshold in deferred_admission_decode_steps:
        variants.extend([
            {"id": f"packed_deferred_static_head:{threshold}", "baseline": "packed_deferred_static_head", "policy_kind": "deferred_observed_steps", "threshold": threshold, "attention": "physical", "scheduler": "static_head"},
            {"id": f"packed_deferred_length_aware_head:{threshold}", "baseline": "packed_deferred_length_aware_head", "policy_kind": "deferred_observed_steps", "threshold": threshold, "attention": "physical", "scheduler": "length_aware_head"},
        ])
    return variants


def policy_active(policy_kind: str, threshold: int | str, *, decode_step: int, decode_steps: int) -> bool:
    """Whether a physical packed path serves this observed decode attention call."""
    if policy_kind == "fixed":
        return True
    if policy_kind == "oracle_horizon_gate":
        return decode_steps >= int(threshold)
    if policy_kind == "deferred_observed_steps":
        return decode_step > int(threshold)
    raise ValueError(f"Unsupported policy kind: {policy_kind}")


def policy_activation_step(policy_kind: str, threshold: int | str, *, decode_steps: int) -> int | str:
    if policy_kind == "fixed":
        return 1
    if policy_kind == "oracle_horizon_gate":
        return 1 if decode_steps >= int(threshold) else "not_activated"
    if policy_kind == "deferred_observed_steps":
        step = int(threshold) + 1
        return step if step <= decode_steps else "not_activated"
    raise ValueError(f"Unsupported policy kind: {policy_kind}")


def simulate(source: list[dict[str, str]], replay: dict[tuple[int, int, int], dict[str, str]], manifest: dict[str, Any], *, workload: str, page_tokens: int, bandwidth: float, throughput: float, ops_per_token: float, pe_count: int, metadata_lookup_bytes: int, metadata_lookup_cycles: float, head_dispatch_cycles: float, scheduler_queue_bytes_per_head: int, oracle_min_decode_steps: list[int], deferred_admission_decode_steps: list[int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kv_bytes, window = int(manifest["kv_bytes_per_layer_head_token"]), int(manifest["sliding_window"])
    request_id = str(manifest["request_id"])
    by_call: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in source:
        by_call[int(row["model_call"])].append(row)
    decode_calls = sorted(call for call, rows in by_call.items() if rows[0]["phase"] == "decode")
    if not decode_calls:
        raise ValueError("A3 requires at least one observed decode model call")
    upfront = 0
    for call, rows in by_call.items():
        if call >= decode_calls[0]:
            continue
        for row in rows:
            key = (call, int(row["layer"]), int(row["kv_head"]))
            upfront += int(row["hot_to_cold_read_bytes"]) + int(row["cold_write_bytes"]) + int(replay[key]["metadata_update_bytes"])
    variants = policy_variants(oracle_min_decode_steps, deferred_admission_decode_steps)
    cumulative_bytes = {variant["id"]: 0.0 for variant in variants}
    cumulative_cycles = {variant["id"]: 0.0 for variant in variants}
    break_even: dict[str, tuple[int, int] | None] = {variant["id"]: None for variant in variants if variant["baseline"] != "full_kv"}
    step_rows: list[dict[str, Any]] = []
    decode_admission_history: list[int] = []
    for index, call in enumerate(decode_calls, start=1):
        rows = by_call[call]
        page_rows = [replay[(call, int(row["layer"]), int(row["kv_head"]))] for row in rows]
        full_read = sum(int(row["cache_tokens_after"]) * kv_bytes for row in rows)
        ideal_read = sum((min(window, int(row["cache_tokens_after"])) + int(page["cold_logical_tokens"])) * kv_bytes for row, page in zip(rows, page_rows))
        physical_read = sum((min(window, int(row["cache_tokens_after"])) + int(page["cold_allocated_slots"])) * kv_bytes for row, page in zip(rows, page_rows))
        metadata_read = sum((int(page["cold_allocated_slots"]) // page_tokens) * metadata_lookup_bytes for page in page_rows)
        decode_admission = sum(int(row["hot_to_cold_read_bytes"]) + int(row["cold_write_bytes"]) + int(page["metadata_update_bytes"]) for row, page in zip(rows, page_rows))
        fixed_admission = decode_admission + (upfront if index == 1 else 0)
        decode_admission_history.append(decode_admission)
        head_count = len(rows)
        queue_bytes = scheduler_queue_bytes_per_head * head_count
        full_cycles = attention_cycles(page_rows, kind="full", page_tokens=page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=0, metadata_lookup_cycles=0.0, pe_count=pe_count, policy="static_head", head_dispatch_cycles=0.0)
        ideal_cycles = attention_cycles(page_rows, kind="ideal", page_tokens=page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=0, metadata_lookup_cycles=0.0, pe_count=pe_count, policy="static_head", head_dispatch_cycles=0.0)
        static_cycles = attention_cycles(page_rows, kind="physical", page_tokens=page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=metadata_lookup_bytes, metadata_lookup_cycles=metadata_lookup_cycles, pe_count=pe_count, policy="static_head", head_dispatch_cycles=0.0)
        selected_cycles = attention_cycles(page_rows, kind="physical", page_tokens=page_tokens, window=window, kv_bytes=kv_bytes, bandwidth=bandwidth, throughput=throughput, ops_per_token=ops_per_token, metadata_lookup_bytes=metadata_lookup_bytes, metadata_lookup_cycles=metadata_lookup_cycles, pe_count=pe_count, policy="length_aware_head", head_dispatch_cycles=head_dispatch_cycles)
        for variant in variants:
            baseline, kind, threshold = variant["baseline"], variant["policy_kind"], variant["threshold"]
            if baseline == "full_kv":
                active, attention, admission_bytes, scheduler_bytes = False, "full", 0, 0
            elif baseline == "ideal_packed_kvzap":
                active, attention, admission_bytes, scheduler_bytes = True, "ideal", 0, 0
            else:
                active = policy_active(kind, threshold, decode_step=index, decode_steps=len(decode_calls))
                attention = "physical" if active else "full"
                if not active:
                    admission_bytes = 0
                elif kind == "deferred_observed_steps" and index == int(threshold) + 1:
                    admission_bytes = upfront + sum(decode_admission_history)
                else:
                    admission_bytes = fixed_admission
                scheduler_bytes = queue_bytes if active and variant["scheduler"] == "length_aware_head" else 0
            attention_value = full_cycles if attention == "full" else ideal_cycles if attention == "ideal" else static_cycles if variant["scheduler"] == "static_head" else selected_cycles
            total_bytes = (full_read if attention == "full" else ideal_read if attention == "ideal" else physical_read) + (metadata_read if attention == "physical" else 0) + admission_bytes + scheduler_bytes
            total_cycles = attention_value + admission_bytes / bandwidth + scheduler_bytes / bandwidth
            variant_id = variant["id"]
            cumulative_bytes[variant_id] += total_bytes
            cumulative_cycles[variant_id] += total_cycles
            if baseline != "full_kv" and break_even[variant_id] is None and cumulative_bytes[variant_id] < cumulative_bytes["full_kv"]:
                break_even[variant_id] = (index, call)
            activation = policy_activation_step(kind, threshold, decode_steps=len(decode_calls)) if baseline not in ("full_kv", "ideal_packed_kvzap") else ""
            step_rows.append({
                "workload": workload, "request_id": request_id, "page_tokens": page_tokens, "bandwidth_bytes_per_cycle": bandwidth, "pe_count": pe_count, "head_dispatch_cycles": head_dispatch_cycles, "scheduler_queue_bytes_per_head": scheduler_queue_bytes_per_head, "baseline": baseline, "policy_kind": kind, "policy_threshold_decode_steps": threshold, "policy_activation_decode_step": activation,
                "model_call": call, "decode_step": index, "cache_tokens_after": int(rows[0]["cache_tokens_after"]),
                "full_read_bytes": full_read, "ideal_packed_read_bytes": ideal_read, "physical_packed_read_bytes": physical_read,
                "metadata_lookup_bytes": metadata_read if attention == "physical" else 0,
                "upfront_admission_bytes": upfront if admission_bytes and index == 1 and kind != "deferred_observed_steps" else (upfront if admission_bytes and kind == "deferred_observed_steps" and index == int(threshold) + 1 else 0),
                "decode_admission_bytes": admission_bytes - (upfront if admission_bytes and ((index == 1 and kind != "deferred_observed_steps") or (kind == "deferred_observed_steps" and index == int(threshold) + 1)) else 0),
                "scheduler_queue_bytes": scheduler_bytes, "step_total_bytes": total_bytes,
                "cumulative_total_bytes": cumulative_bytes[variant_id], "cumulative_full_kv_bytes": cumulative_bytes["full_kv"],
                "cumulative_net_bytes_saved": cumulative_bytes["full_kv"] - cumulative_bytes[variant_id],
                "attention_cycles": attention_value,
                "admission_cycles": admission_bytes / bandwidth,
                "scheduler_cycles": (selected_cycles - static_cycles) + queue_bytes / bandwidth if attention == "physical" and variant["scheduler"] == "length_aware_head" else 0.0,
                "step_total_cycles": total_cycles, "cumulative_total_cycles": cumulative_cycles[variant_id],
            })
    summaries = []
    for variant in variants:
        baseline, kind, threshold, variant_id = variant["baseline"], variant["policy_kind"], variant["threshold"], variant["id"]
        full_b, full_c = cumulative_bytes["full_kv"], cumulative_cycles["full_kv"]
        point = break_even.get(variant_id)
        summaries.append({"workload": workload, "request_id": request_id, "page_tokens": page_tokens, "bandwidth_bytes_per_cycle": bandwidth, "pe_count": pe_count, "head_dispatch_cycles": head_dispatch_cycles, "scheduler_queue_bytes_per_head": scheduler_queue_bytes_per_head, "baseline": baseline, "policy_kind": kind, "policy_threshold_decode_steps": threshold, "policy_activation_decode_step": policy_activation_step(kind, threshold, decode_steps=len(decode_calls)) if baseline not in ("full_kv", "ideal_packed_kvzap") else "", "decode_steps": len(decode_calls), "full_kv_cumulative_bytes": full_b, "baseline_cumulative_bytes": cumulative_bytes[variant_id], "net_bytes_saved": full_b - cumulative_bytes[variant_id], "net_bytes_saved_fraction": (full_b - cumulative_bytes[variant_id]) / full_b if full_b else math.nan, "break_even_decode_step": point[0] if point else "not_reached", "break_even_model_call": point[1] if point else "not_reached", "full_kv_cumulative_cycles": full_c, "baseline_cumulative_cycles": cumulative_cycles[variant_id], "net_cycles_saved": full_c - cumulative_cycles[variant_id], "net_cycles_saved_fraction": (full_c - cumulative_cycles[variant_id]) / full_c if full_c else math.nan, "scheduler_cycle_source": "A1_policy_constants_plus_A2_single_request_step_model" if variant["scheduler"] == "length_aware_head" else "A3_single_request_step_model"})
    return step_rows, summaries
