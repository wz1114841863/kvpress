"""Route-A1 offline scheduler DSE over Route-A0 packed-page replay outputs.

This is a parameterized model, not a model execution or a hardware measurement.
It only constructs deterministic *simulated serving batches* from independent
predictor-only requests. Layers are sequential; work may be scheduled only
within a layer across requests already present in the simulated batch.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from tools.analyze_kvzap_trace import get_git_commit


POLICIES = ("static_head", "length_aware_head", "dynamic_page")
LAYER_COLUMNS = (
    "batch_id", "batch_size_requested", "batch_size_actual", "request_ids", "page_tokens", "pe_count", "policy", "layer",
    "head_task_count", "dynamic_task_count", "queue_depth_max", "useful_cycles", "dispatch_cycles", "merge_serial_cycles",
    "pe_makespan_cycles", "modeled_layer_cycles", "idle_pe_cycles", "utilization_useful", "utilization_with_dispatch",
    "request_local_finish_p50", "request_local_finish_p95", "request_local_finish_max",
)
BATCH_COLUMNS = (
    "batch_id", "batch_size_requested", "batch_size_actual", "request_ids", "page_tokens", "pe_count", "policy", "layer_count",
    "head_task_count", "dynamic_task_count", "queue_depth_max", "useful_cycles", "dispatch_cycles", "merge_serial_cycles",
    "pe_makespan_cycles", "modeled_makespan_cycles", "idle_pe_cycles", "utilization_useful", "utilization_with_dispatch",
    "request_useful_cycles_cv", "request_local_finish_cycles_cv", "request_local_finish_cycles_p50",
    "request_local_finish_cycles_p95", "request_local_finish_cycles_max",
)
SUMMARY_COLUMNS = (
    "page_tokens", "pe_count", "policy", "batch_size_requested", "batch_count", "request_count",
    "modeled_makespan_cycles_p50", "modeled_makespan_cycles_p95", "modeled_makespan_cycles_max",
    "utilization_useful_weighted", "utilization_with_dispatch_weighted", "queue_depth_max_mean",
    "request_useful_cycles_cv_mean", "request_local_finish_cycles_cv_mean",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A1 packed-page scheduler DSE; no model execution.")
    parser.add_argument("--a0-dir", type=Path, required=True, help="Completed Route-A0 output directory.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory; existing directories are never overwritten.")
    parser.add_argument("--page-tokens", nargs="+", type=int, default=[16, 32, 64, 128])
    parser.add_argument("--pe-counts", nargs="+", type=int, default=[8, 16, 32, 64])
    parser.add_argument("--batch-sizes", nargs="+", type=int, default=[1, 2, 4, 8])
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=list(POLICIES))
    parser.add_argument("--drop-incomplete-batch", action="store_true", help="Drop the final short sequential batch instead of labelling its actual size.")
    parser.add_argument("--bandwidth-bytes-per-cycle", type=float, default=1024.0, help="Declared modeled bandwidth, not a measurement.")
    parser.add_argument("--throughput-ops-per-cycle", type=float, default=4096.0, help="Declared modeled attention throughput, not a measurement.")
    parser.add_argument("--attention-ops-per-kv-token", type=float, default=512.0, help="Declared QK+AV+softmax work per layer/head KV token.")
    parser.add_argument("--metadata-lookup-cycles-per-page", type=float, default=1.0)
    parser.add_argument("--head-dispatch-cycles", type=float, default=0.0, help="Whole-head dispatch overhead for length-aware scheduling.")
    parser.add_argument("--dynamic-dispatch-cycles", type=float, default=2.0, help="Per dynamic hot/page task queue-dispatch overhead.")
    parser.add_argument("--merge-cycles-per-extra-segment", type=float, default=8.0, help="Serial partial-softmax merge cost per split head segment beyond the first.")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: Iterable[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def load_a0(a0_dir: Path) -> tuple[list[dict[str, str]], dict[str, Any], int]:
    required = [a0_dir / "layer_head_packed_page_replay.csv", a0_dir / "request_packed_page_replay.csv", a0_dir / "replay_manifest.json"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"A0 directory is missing required files: {missing}")
    manifest = json.loads((a0_dir / "replay_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a0-static-packed-page-replay-1.0":
        raise ValueError(f"Unsupported A0 replay schema: {manifest.get('schema_version')!r}")
    heads = read_csv(a0_dir / "layer_head_packed_page_replay.csv")
    if not heads:
        raise ValueError("A0 layer/head replay is empty")
    return heads, manifest, infer_kv_bytes_per_token(heads)


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


def schedule_static(tasks: list[dict[str, Any]], pe_count: int) -> tuple[list[float], list[float], float, int]:
    loads = [0.0] * pe_count
    request_finish: dict[str, float] = defaultdict(float)
    for task in tasks:
        owner = int(task["owner"]) % pe_count
        loads[owner] += float(task["useful"])
        request_finish[task["trace_id"]] = max(request_finish[task["trace_id"]], loads[owner])
    return loads, list(request_finish.values()), 0.0, len(tasks)


def schedule_lpt(tasks: list[dict[str, Any]], pe_count: int, dispatch_cycles: float) -> tuple[list[float], list[float], float, int]:
    loads = [0.0] * pe_count
    request_finish: dict[str, float] = defaultdict(float)
    for task in sorted(tasks, key=lambda row: (-float(row["useful"]), str(row["trace_id"]), int(row["kv_head"]))):
        pe = min(range(pe_count), key=lambda index: loads[index])
        loads[pe] += float(task["useful"]) + dispatch_cycles
        request_finish[task["trace_id"]] = max(request_finish[task["trace_id"]], loads[pe])
    return loads, list(request_finish.values()), len(tasks) * dispatch_cycles, len(tasks)


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


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    for name, values in (("--page-tokens", args.page_tokens), ("--pe-counts", args.pe_counts), ("--batch-sizes", args.batch_sizes)):
        if not values or len(set(values)) != len(values) or any(value <= 0 for value in values):
            raise ValueError(f"{name} must contain unique positive integers")
    if len(set(args.policies)) != len(args.policies) or min(args.head_dispatch_cycles, args.dynamic_dispatch_cycles, args.merge_cycles_per_extra_segment) < 0:
        raise ValueError("policies must be unique and overhead values must be non-negative")
    heads, a0_manifest, kv_bytes = load_a0(args.a0_dir)
    available_pages = {int(row["page_tokens"]) for row in heads}
    if set(args.page_tokens) - available_pages:
        raise ValueError(f"Requested page sizes absent from A0: {sorted(set(args.page_tokens) - available_pages)}")
    source_order = list(dict.fromkeys(row["trace_id"] for row in heads))
    args.output_dir.mkdir(parents=True)
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
    write_csv(args.output_dir / "scheduler_layer_results.csv", [public_layer_row(row) for row in layer_rows], LAYER_COLUMNS)
    write_csv(args.output_dir / "scheduler_batch_results.csv", batch_rows, BATCH_COLUMNS)
    write_csv(args.output_dir / "scheduler_summary.csv", summarize(batch_rows), SUMMARY_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a1-scheduler-dse-1.0", "git_commit": get_git_commit(), "a0_dir": str(args.a0_dir), "a0_replay_manifest_sha256": sha256(args.a0_dir / "replay_manifest.json"), "a0_layer_head_sha256": sha256(args.a0_dir / "layer_head_packed_page_replay.csv"), "source_trace_count": len(a0_manifest["source_traces"]), "source_traces": a0_manifest["source_traces"], "batch_construction": {"kind": "sequential-source-order", "source_trace_ids": source_order, "drop_incomplete_batch": args.drop_incomplete_batch, "label": "simulated serving batches; independent predictor-only requests, not native model batches"}, "page_tokens": args.page_tokens, "pe_counts": args.pe_counts, "batch_sizes": args.batch_sizes, "policies": args.policies, "cost_model": {"kv_bytes_per_token": kv_bytes, "bandwidth_bytes_per_cycle": args.bandwidth_bytes_per_cycle, "throughput_ops_per_cycle": args.throughput_ops_per_cycle, "attention_ops_per_kv_token": args.attention_ops_per_kv_token, "metadata_lookup_cycles_per_page": args.metadata_lookup_cycles_per_page, "head_dispatch_cycles": args.head_dispatch_cycles, "dynamic_dispatch_cycles": args.dynamic_dispatch_cycles, "merge_cycles_per_extra_segment": args.merge_cycles_per_extra_segment, "page_cost": "max(KV_bytes / bandwidth, attention_ops / throughput) + page metadata lookup"}, "policy_definitions": {"static_head": "fixed owner = (batch request slot * kv_heads + kv_head) mod PE count", "length_aware_head": "whole-head LPT scheduling; no cross-PE partial-softmax merge", "dynamic_page": "LPT scheduling of a hot segment plus one task per allocated cold page; per-task dispatch and serial merge cost for each extra head segment"}, "notes": ["All cycles and utilization are modeled from declared constants and static A0 replay work; they are not hardware measurements.", "Layers are sequential barriers; only requests already in a simulated batch are jointly schedulable within a layer.", "No conclusion about decode admission, actual HBM traffic, latency, throughput, or accuracy is supported."]}
    (args.output_dir / "scheduler_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Simulated {len(batch_rows)} Route-A1 batch/policy/PE/page workloads: {args.output_dir}")


if __name__ == "__main__":
    main()
