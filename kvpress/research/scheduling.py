"""Offline scheduling of packed-page work using declared cost assumptions.

Simulated batches and cycles are a model, not measured hardware behavior.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from typing import Any

import numpy as np


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else math.nan


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values), q, method="higher")) if values else math.nan


def coefficient_of_variation(values: list[float]) -> float:
    array = np.asarray(values, dtype=np.float64)
    return float(array.std() / array.mean()) if array.size and array.mean() else math.nan


class PageCostModel:
    """Declared roofline-like service cost for one attention segment."""

    def __init__(self, kv_bytes_per_token: float, bandwidth: float, throughput: float, ops_per_token: float, metadata_cycles: float) -> None:
        if min(kv_bytes_per_token, bandwidth, throughput, ops_per_token) <= 0 or metadata_cycles < 0:
            raise ValueError("cost-model quantities must be positive except metadata cycles, which may be zero")
        self.kv_bytes_per_token = kv_bytes_per_token
        self.bandwidth = bandwidth
        self.throughput = throughput
        self.ops_per_token = ops_per_token
        self.metadata_cycles = metadata_cycles

    def segment_cycles(self, slots: int, has_page_metadata: bool) -> float:
        core = max(slots * self.kv_bytes_per_token / self.bandwidth, slots * self.ops_per_token / self.throughput)
        return core + (self.metadata_cycles if has_page_metadata else 0.0)


def infer_kv_bytes_per_token(rows: list[dict[str, str]]) -> int:
    candidates = set()
    for row in rows:
        hot = int(row["hot_slots"])
        cold = int(row["cold_allocated_slots"])
        if hot:
            candidates.add(int(row["hot_kv_bytes"]) // hot)
        if cold:
            candidates.add(int(row["cold_kv_bytes"]) // cold)
    if len(candidates) != 1 or 0 in candidates:
        raise ValueError(f"Could not infer one consistent kv_bytes_per_token from A0 rows: {sorted(candidates)}")
    return candidates.pop()


def make_batches(trace_ids: list[str], batch_size: int, drop_incomplete: bool) -> list[list[str]]:
    batches = [trace_ids[start : start + batch_size] for start in range(0, len(trace_ids), batch_size)]
    return [batch for batch in batches if len(batch) == batch_size or not drop_incomplete]


def build_head_tasks(rows: list[dict[str, str]], trace_ids: list[str], layer: int, page_tokens: int, cost: PageCostModel) -> list[dict[str, Any]]:
    by_trace_head = {(row["trace_id"], int(row["kv_head"])): row for row in rows if int(row["layer"]) == layer}
    heads = sorted({int(row["kv_head"]) for row in rows})
    tasks: list[dict[str, Any]] = []
    for request_slot, trace_id in enumerate(trace_ids):
        for kv_head in heads:
            row = by_trace_head.get((trace_id, kv_head))
            if row is None:
                raise ValueError(f"Missing A0 row for trace={trace_id}, layer={layer}, kv_head={kv_head}")
            hot_slots, pages = int(row["hot_slots"]), int(row["cold_page_count"])
            useful = cost.segment_cycles(hot_slots, False) + pages * cost.segment_cycles(page_tokens, True)
            tasks.append({"trace_id": trace_id, "kv_head": kv_head, "owner": request_slot * len(heads) + kv_head, "useful": useful, "hot_slots": hot_slots, "pages": pages})
    return tasks


def schedule_static(tasks: list[dict[str, Any]], pe_count: int) -> tuple[list[float], dict[str, float], float, int]:
    loads = [0.0] * pe_count
    request_finish: dict[str, float] = defaultdict(float)
    for task in tasks:
        owner = int(task["owner"]) % pe_count
        loads[owner] += float(task["useful"])
        request_finish[task["trace_id"]] = max(request_finish[task["trace_id"]], loads[owner])
    return loads, dict(request_finish), 0.0, len(tasks)


def schedule_lpt(tasks: list[dict[str, Any]], pe_count: int, dispatch_cycles: float) -> tuple[list[float], dict[str, float], float, int]:
    loads = [0.0] * pe_count
    request_finish: dict[str, float] = defaultdict(float)
    for task in sorted(tasks, key=lambda row: (-float(row["useful"]), str(row["trace_id"]), int(row["kv_head"]))):
        pe = min(range(pe_count), key=lambda index: loads[index])
        loads[pe] += float(task["useful"]) + dispatch_cycles
        request_finish[task["trace_id"]] = max(request_finish[task["trace_id"]], loads[pe])
    return loads, dict(request_finish), len(tasks) * dispatch_cycles, len(tasks)


def build_dynamic_tasks(head_tasks: list[dict[str, Any]], page_tokens: int, cost: PageCostModel) -> tuple[list[dict[str, Any]], float]:
    tasks: list[dict[str, Any]] = []
    merge_segments = 0
    for head in head_tasks:
        segments = 0
        if int(head["hot_slots"]):
            tasks.append({"trace_id": head["trace_id"], "kv_head": head["kv_head"], "useful": cost.segment_cycles(int(head["hot_slots"]), False)})
            segments += 1
        for _ in range(int(head["pages"])):
            tasks.append({"trace_id": head["trace_id"], "kv_head": head["kv_head"], "useful": cost.segment_cycles(page_tokens, True)})
            segments += 1
        merge_segments += max(segments - 1, 0)
    return tasks, float(merge_segments)


def layer_result(batch_id: str, batch: list[str], page_tokens: int, pe_count: int, layer: int, policy: str, head_tasks: list[dict[str, Any]], cost: PageCostModel, args: argparse.Namespace) -> dict[str, Any]:
    useful = sum(float(task["useful"]) for task in head_tasks)
    if policy == "static_head":
        loads, finishes, dispatch, queue_depth = schedule_static(head_tasks, pe_count)
        dynamic_count, merge = len(head_tasks), 0.0
    elif policy == "length_aware_head":
        loads, finishes, dispatch, queue_depth = schedule_lpt(head_tasks, pe_count, args.head_dispatch_cycles)
        dynamic_count, merge = len(head_tasks), 0.0
    elif policy == "dynamic_page":
        dynamic_tasks, extra_segments = build_dynamic_tasks(head_tasks, page_tokens, cost)
        loads, finishes, dispatch, queue_depth = schedule_lpt(dynamic_tasks, pe_count, args.dynamic_dispatch_cycles)
        dynamic_count, merge = len(dynamic_tasks), extra_segments * args.merge_cycles_per_extra_segment
    else:
        raise ValueError(f"Unknown policy: {policy}")
    finishes = [finishes.get(trace_id, 0.0) for trace_id in batch]
    pe_makespan = max(loads, default=0.0)
    idle = pe_count * pe_makespan - useful - dispatch
    return {
        "batch_id": batch_id, "batch_size_requested": args.batch_size_requested, "batch_size_actual": len(batch), "request_ids": json.dumps(batch),
        "page_tokens": page_tokens, "pe_count": pe_count, "policy": policy, "layer": layer,
        "head_task_count": len(head_tasks), "dynamic_task_count": dynamic_count, "queue_depth_max": queue_depth,
        "useful_cycles": useful, "dispatch_cycles": dispatch, "merge_serial_cycles": merge,
        "pe_makespan_cycles": pe_makespan, "modeled_layer_cycles": pe_makespan + merge, "idle_pe_cycles": idle,
        "utilization_useful": safe_divide(useful, pe_count * pe_makespan), "utilization_with_dispatch": safe_divide(useful + dispatch, pe_count * pe_makespan),
        "request_local_finish_p50": percentile(finishes, 50), "request_local_finish_p95": percentile(finishes, 95), "request_local_finish_max": max(finishes, default=math.nan),
        "_request_finish": finishes, "_request_useful": [sum(float(task["useful"]) for task in head_tasks if task["trace_id"] == trace_id) for trace_id in batch],
    }


def batch_result(layer_rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = layer_rows[0]
    request_finish = [sum(row["_request_finish"][index] for row in layer_rows) for index in range(len(json.loads(first["request_ids"])))]
    request_useful = [sum(row["_request_useful"][index] for row in layer_rows) for index in range(len(request_finish))]
    useful, dispatch, pe_makespan, merge, idle = (sum(float(row[key]) for row in layer_rows) for key in ("useful_cycles", "dispatch_cycles", "pe_makespan_cycles", "merge_serial_cycles", "idle_pe_cycles"))
    return {
        **{key: first[key] for key in ("batch_id", "batch_size_requested", "batch_size_actual", "request_ids", "page_tokens", "pe_count", "policy")},
        "layer_count": len(layer_rows), "head_task_count": sum(int(row["head_task_count"]) for row in layer_rows), "dynamic_task_count": sum(int(row["dynamic_task_count"]) for row in layer_rows), "queue_depth_max": max(int(row["queue_depth_max"]) for row in layer_rows),
        "useful_cycles": useful, "dispatch_cycles": dispatch, "merge_serial_cycles": merge, "pe_makespan_cycles": pe_makespan, "modeled_makespan_cycles": pe_makespan + merge, "idle_pe_cycles": idle,
        "utilization_useful": safe_divide(useful, int(first["pe_count"]) * pe_makespan), "utilization_with_dispatch": safe_divide(useful + dispatch, int(first["pe_count"]) * pe_makespan),
        "request_useful_cycles_cv": coefficient_of_variation(request_useful), "request_local_finish_cycles_cv": coefficient_of_variation(request_finish),
        "request_local_finish_cycles_p50": percentile(request_finish, 50), "request_local_finish_cycles_p95": percentile(request_finish, 95), "request_local_finish_cycles_max": max(request_finish),
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[int, int, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(int(row["page_tokens"]), int(row["pe_count"]), row["policy"], int(row["batch_size_requested"]))].append(row)
    output = []
    for (page, pes, policy, batch), values in sorted(groups.items()):
        pe_makespan = sum(float(row["pe_makespan_cycles"]) for row in values)
        useful = sum(float(row["useful_cycles"]) for row in values)
        dispatch = sum(float(row["dispatch_cycles"]) for row in values)
        makespans = [float(row["modeled_makespan_cycles"]) for row in values]
        output.append({"page_tokens": page, "pe_count": pes, "policy": policy, "batch_size_requested": batch, "batch_count": len(values), "request_count": sum(int(row["batch_size_actual"]) for row in values), "modeled_makespan_cycles_p50": percentile(makespans, 50), "modeled_makespan_cycles_p95": percentile(makespans, 95), "modeled_makespan_cycles_max": max(makespans), "utilization_useful_weighted": safe_divide(useful, pes * pe_makespan), "utilization_with_dispatch_weighted": safe_divide(useful + dispatch, pes * pe_makespan), "queue_depth_max_mean": float(np.mean([float(row["queue_depth_max"]) for row in values])), "request_useful_cycles_cv_mean": float(np.nanmean([float(row["request_useful_cycles_cv"]) for row in values])), "request_local_finish_cycles_cv_mean": float(np.nanmean([float(row["request_local_finish_cycles_cv"]) for row in values]))})
    return output


def public_layer_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def simulate_workloads(
    heads: list[dict[str, str]], kv_bytes: int, args: argparse.Namespace
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Build and schedule A0 workloads, then aggregate the modeled results."""
    source_order = list(dict.fromkeys(row["trace_id"] for row in heads))
    layer_rows: list[dict[str, Any]] = []
    batch_rows: list[dict[str, Any]] = []
    for page in args.page_tokens:
        page_rows = [row for row in heads if int(row["page_tokens"]) == page]
        layers = sorted({int(row["layer"]) for row in page_rows})
        cost = PageCostModel(kv_bytes, args.bandwidth_bytes_per_cycle, args.throughput_ops_per_cycle, args.attention_ops_per_kv_token, args.metadata_lookup_cycles_per_page)
        for requested_batch in args.batch_sizes:
            for batch_number, batch in enumerate(make_batches(source_order, requested_batch, args.drop_incomplete_batch)):
                batch_id = f"p{page}_b{requested_batch}_{batch_number:03d}"
                args.batch_size_requested = requested_batch
                for pe_count in args.pe_counts:
                    for policy in args.policies:
                        one_batch = [layer_result(batch_id, batch, page, pe_count, layer, policy, build_head_tasks(page_rows, batch, layer, page, cost), cost, args) for layer in layers]
                        layer_rows.extend(one_batch)
                        batch_rows.append(batch_result(one_batch))
    return source_order, layer_rows, batch_rows, summarize(batch_rows)
