"""Summarize shared Route-A3.11 deferred-DSE points across workloads."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a3_traffic import sha256


POLICY = ("deferred_decode_steps", "admission_flush_token_budget")
HARDWARE = ("bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer")
PER_COLUMNS = ("workload", "request_id", "deferred_memory_dir", *POLICY, *HARDWARE, "net_bytes_saved_fraction", "net_cycle_proxy_saved_fraction", "initial_full_kv_call_count", "staging_full_kv_call_count", "staging_full_kv_layer_count")
CROSS_COLUMNS = (*POLICY, *HARDWARE, "workload_count", "all_workloads_positive_bytes", "all_workloads_positive_cycle", "min_net_bytes_saved_fraction", "mean_net_bytes_saved_fraction", "min_net_cycle_proxy_saved_fraction", "mean_net_cycle_proxy_saved_fraction", "worst_cycle_workload", "worst_cycle_request_id")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3.12 cross-workload deferred-DSE summary; never loads a model.")
    parser.add_argument("--deferred-memory-dir", type=Path, action="append", required=True, help="Completed A3.11 directory; repeat once per workload.")
    parser.add_argument("--workload-label", action="append", required=True, help="Unique label paired with --deferred-memory-dir.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args(argv)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def point(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[field] for field in (*POLICY, *HARDWARE))


def load(directory: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest_path, summary_path = directory / "deferred_memory_system_manifest.json", directory / "deferred_memory_system_summary.csv"
    if not manifest_path.is_file() or not summary_path.is_file():
        raise FileNotFoundError("A3.12 requires A3.11 deferred-memory manifest and summary")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a311-deferred-memory-system-dse-1.0":
        raise ValueError("unsupported A3.11 schema")
    rows = read_csv(summary_path)
    if not rows or len({point(row) for row in rows}) != len(rows):
        raise ValueError("A3.11 summary is empty or has duplicate policy/hardware points")
    return manifest, rows


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if len(args.deferred_memory_dir) != len(args.workload_label) or len(args.workload_label) < 2 or len(set(args.workload_label)) != len(args.workload_label):
        raise ValueError("supply at least two unique workload labels paired with A3.11 directories")
    inputs = [(label, directory, *load(directory)) for label, directory in zip(args.workload_label, args.deferred_memory_dir, strict=True)]
    expected = {point(row) for row in inputs[0][3]}
    for label, _directory, _manifest, rows in inputs[1:]:
        if {point(row) for row in rows} != expected:
            raise ValueError(f"A3.11 policy/hardware points disagree for workload {label}")
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    per: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {}
    for label, directory, manifest, rows in inputs:
        request_ids = {row["request_id"] for row in rows}
        if len(request_ids) != 1:
            raise ValueError(f"A3.11 summary has multiple request IDs for {label}")
        provenance[label] = {"directory": str(directory), "request_id": next(iter(request_ids)), "manifest_sha256": sha256(directory / "deferred_memory_system_manifest.json"), "summary_sha256": sha256(directory / "deferred_memory_system_summary.csv"), "source_deferred_replay_manifest_sha256": manifest.get("source_artifact_sha256", {}).get("deferred_replay_manifest_sha256")}
        for row in rows:
            item = {"workload": label, "request_id": row["request_id"], "deferred_memory_dir": str(directory), **{field: row[field] for field in (*POLICY, *HARDWARE)}, **{field: row[field] for field in ("net_bytes_saved_fraction", "net_cycle_proxy_saved_fraction", "initial_full_kv_call_count", "staging_full_kv_call_count", "staging_full_kv_layer_count")}}
            per.append(item)
            grouped[point(row)].append(item)
    cross: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items()):
        if len(rows) != len(inputs):
            raise AssertionError("missing workload at a shared point")
        bytes_ = [float(row["net_bytes_saved_fraction"]) for row in rows]
        cycles = [float(row["net_cycle_proxy_saved_fraction"]) for row in rows]
        worst = min(range(len(rows)), key=lambda i: cycles[i])
        cross.append({**dict(zip((*POLICY, *HARDWARE), key)), "workload_count": len(rows), "all_workloads_positive_bytes": all(value > 0 for value in bytes_), "all_workloads_positive_cycle": all(value > 0 for value in cycles), "min_net_bytes_saved_fraction": min(bytes_), "mean_net_bytes_saved_fraction": mean(bytes_), "min_net_cycle_proxy_saved_fraction": min(cycles), "mean_net_cycle_proxy_saved_fraction": mean(cycles), "worst_cycle_workload": rows[worst]["workload"], "worst_cycle_request_id": rows[worst]["request_id"]})
    return per, cross, provenance


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    per, cross, provenance = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "deferred_memory_cross_per_workload.csv", per, PER_COLUMNS)
    write_csv(args.output_dir / "deferred_memory_cross_summary.csv", cross, CROSS_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a312-cross-workload-deferred-dse-1.0", "git_commit": get_git_commit(), "workloads": provenance, "assumptions": {"selection_rule": "none; report every caller-supplied shared point", "positive_rule": "strictly positive modeled savings for every supplied workload"}, "boundaries": ["Cross-workload summary of A3.11 models only; not controller calibration or hardware measurement.", "No HBM/DRAM counter, allocator measurement, latency/throughput, sparse-attention execution, or generation result."]}
    (args.output_dir / "deferred_memory_cross_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3.12 summarized {len(provenance)} workloads and {len(cross)} shared points: {args.output_dir}")


if __name__ == "__main__":
    main()
