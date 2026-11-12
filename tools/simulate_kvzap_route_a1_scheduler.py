"""Route-A1 offline scheduler DSE over Route-A0 packed-page replay outputs.

This is a parameterized model, not a model execution or a hardware measurement.
It only constructs deterministic *simulated serving batches* from independent
predictor-only requests. Layers are sequential; work may be scheduled only
within a layer across requests already present in the simulated batch.

Data flow: load A0 per-head rows -> build head/page work -> schedule each
layer -> aggregate batches and summaries -> write the modeled results.
The shared calculations live in kvpress.research.scheduling.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

# Retain the historical import surface for existing callers.
from kvpress.research.scheduling import (
    PageCostModel, batch_result, build_dynamic_tasks, build_head_tasks, coefficient_of_variation,
    infer_kv_bytes_per_token, layer_result, make_batches, percentile, public_layer_row,
    safe_divide, schedule_lpt, schedule_static, simulate_workloads, summarize,
)
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
    source_order, layer_rows, batch_rows, summary_rows = simulate_workloads(heads, kv_bytes, args)
    args.output_dir.mkdir(parents=True)
    write_csv(args.output_dir / "scheduler_layer_results.csv", [public_layer_row(row) for row in layer_rows], LAYER_COLUMNS)
    write_csv(args.output_dir / "scheduler_batch_results.csv", batch_rows, BATCH_COLUMNS)
    write_csv(args.output_dir / "scheduler_summary.csv", summary_rows, SUMMARY_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a1-scheduler-dse-1.0", "git_commit": get_git_commit(), "a0_dir": str(args.a0_dir), "a0_replay_manifest_sha256": sha256(args.a0_dir / "replay_manifest.json"), "a0_layer_head_sha256": sha256(args.a0_dir / "layer_head_packed_page_replay.csv"), "source_trace_count": len(a0_manifest["source_traces"]), "source_traces": a0_manifest["source_traces"], "batch_construction": {"kind": "sequential-source-order", "source_trace_ids": source_order, "drop_incomplete_batch": args.drop_incomplete_batch, "label": "simulated serving batches; independent predictor-only requests, not native model batches"}, "page_tokens": args.page_tokens, "pe_counts": args.pe_counts, "batch_sizes": args.batch_sizes, "policies": args.policies, "cost_model": {"kv_bytes_per_token": kv_bytes, "bandwidth_bytes_per_cycle": args.bandwidth_bytes_per_cycle, "throughput_ops_per_cycle": args.throughput_ops_per_cycle, "attention_ops_per_kv_token": args.attention_ops_per_kv_token, "metadata_lookup_cycles_per_page": args.metadata_lookup_cycles_per_page, "head_dispatch_cycles": args.head_dispatch_cycles, "dynamic_dispatch_cycles": args.dynamic_dispatch_cycles, "merge_cycles_per_extra_segment": args.merge_cycles_per_extra_segment, "page_cost": "max(KV_bytes / bandwidth, attention_ops / throughput) + page metadata lookup"}, "policy_definitions": {"static_head": "fixed owner = (batch request slot * kv_heads + kv_head) mod PE count", "length_aware_head": "whole-head LPT scheduling; no cross-PE partial-softmax merge", "dynamic_page": "LPT scheduling of a hot segment plus one task per allocated cold page; per-task dispatch and serial merge cost for each extra head segment"}, "notes": ["Request-local finish sums per-layer PE completion offsets by trace ID; it excludes serial merge and is not end-to-end request latency.", "All cycles and utilization are modeled from declared constants and static A0 replay work; they are not hardware measurements.", "Layers are sequential barriers; only requests already in a simulated batch are jointly schedulable within a layer.", "No conclusion about decode admission, actual HBM traffic, latency, throughput, or accuracy is supported."]}
    (args.output_dir / "scheduler_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Simulated {len(batch_rows)} Route-A1 batch/policy/PE/page workloads: {args.output_dir}")


if __name__ == "__main__":
    main()
