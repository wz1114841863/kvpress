"""A3.14 observable request-cap gate over aligned A3.11 DSE outputs.

``max_new_tokens`` is caller-visible but only an upper bound on output length.
This tool models a deliberately conservative deployment contract: calls below a
chosen cap threshold remain Full KV with no admission; all other calls use one
caller-selected A3.11 deferred policy.  It never uses observed output length
to make the selection.
"""

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


HARDWARE = ("bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer")
PER_COLUMNS = ("workload", "request_id", "lifecycle_dir", "deferred_memory_dir", "request_max_new_tokens", "request_cap_threshold", "gate_path", "deferred_decode_steps", "admission_flush_token_budget", *HARDWARE, "net_bytes_saved_fraction", "net_cycle_proxy_saved_fraction", "interpretation")
CROSS_COLUMNS = ("request_cap_threshold", "deferred_decode_steps", "admission_flush_token_budget", *HARDWARE, "workload_count", "all_workloads_nonnegative_cycle", "all_workloads_positive_cycle", "min_net_bytes_saved_fraction", "mean_net_bytes_saved_fraction", "min_net_cycle_proxy_saved_fraction", "mean_net_cycle_proxy_saved_fraction", "worst_cycle_workload")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3.14 observable request-cap admission-gate DSE; never loads a model.")
    parser.add_argument("--lifecycle-dir", type=Path, action="append", required=True, help="Validated A2 lifecycle; repeat once per workload.")
    parser.add_argument("--deferred-memory-dir", type=Path, action="append", required=True, help="Aligned A3.11 directory; repeat once per workload.")
    parser.add_argument("--workload-label", action="append", required=True, help="Unique label paired with the input directories.")
    parser.add_argument("--request-max-new-tokens-thresholds", nargs="+", type=int, required=True, help="Protect request when its caller max_new_tokens is below this threshold.")
    parser.add_argument("--active-deferred-decode-steps", type=int, default=5)
    parser.add_argument("--active-admission-flush-token-budget", type=int, default=512)
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


def hardware_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[key] for key in HARDWARE)


def load_pair(lifecycle_dir: Path, memory_dir: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    lifecycle_path = lifecycle_dir / "lifecycle_manifest.json"
    memory_manifest_path, summary_path = memory_dir / "deferred_memory_system_manifest.json", memory_dir / "deferred_memory_system_summary.csv"
    if not all(path.is_file() for path in (lifecycle_path, memory_manifest_path, summary_path)):
        raise FileNotFoundError("A3.14 requires lifecycle manifest plus A3.11 manifest/summary")
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    memory = json.loads(memory_manifest_path.read_text(encoding="utf-8"))
    if lifecycle.get("schema_version") != "kvzap-route-a2-readonly-lifecycle-1.0" or memory.get("schema_version") != "kvzap-route-a311-deferred-memory-system-dse-1.0":
        raise ValueError("unsupported A2/A3.11 schema")
    if Path(memory.get("lifecycle_dir", "")) != lifecycle_dir:
        raise ValueError("A3.11 directory is not bound to its supplied A2 lifecycle")
    rows = read_csv(summary_path)
    if not rows:
        raise ValueError("A3.11 summary is empty")
    return lifecycle, memory, rows


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    lengths = (len(args.lifecycle_dir), len(args.deferred_memory_dir), len(args.workload_label))
    if len(set(lengths)) != 1 or lengths[0] < 2 or len(set(args.workload_label)) != len(args.workload_label):
        raise ValueError("supply at least two unique, ordered lifecycle/memory/label triples")
    if not args.request_max_new_tokens_thresholds or min(args.request_max_new_tokens_thresholds) < 0 or len(set(args.request_max_new_tokens_thresholds)) != len(args.request_max_new_tokens_thresholds):
        raise ValueError("request-cap thresholds must be unique non-negative integers")
    pairs = [(label, lifecycle_dir, memory_dir, *load_pair(lifecycle_dir, memory_dir)) for label, lifecycle_dir, memory_dir in zip(args.workload_label, args.lifecycle_dir, args.deferred_memory_dir, strict=True)]
    active_rows: list[tuple[str, Path, Path, dict[str, Any], dict[str, Any], dict[tuple[str, ...], dict[str, str]]]] = []
    expected_hardware: set[tuple[str, ...]] | None = None
    provenance: dict[str, Any] = {}
    for label, lifecycle_dir, memory_dir, lifecycle, memory, rows in pairs:
        selected = [row for row in rows if int(row["deferred_decode_steps"]) == args.active_deferred_decode_steps and int(row["admission_flush_token_budget"]) == args.active_admission_flush_token_budget]
        by_hardware = {hardware_key(row): row for row in selected}
        if len(by_hardware) != len(selected) or not by_hardware:
            raise ValueError(f"A3.11 active policy is missing or duplicated for workload {label}")
        if expected_hardware is None:
            expected_hardware = set(by_hardware)
        elif set(by_hardware) != expected_hardware:
            raise ValueError(f"A3.11 hardware points disagree for workload {label}")
        config = lifecycle.get("config", {})
        if "max_new_tokens" not in config:
            raise ValueError(f"A2 lifecycle has no max_new_tokens config for workload {label}")
        provenance[label] = {"lifecycle_dir": str(lifecycle_dir), "deferred_memory_dir": str(memory_dir), "request_id": lifecycle["request_id"], "request_max_new_tokens": int(config["max_new_tokens"]), "lifecycle_manifest_sha256": sha256(lifecycle_dir / "lifecycle_manifest.json"), "memory_manifest_sha256": sha256(memory_dir / "deferred_memory_system_manifest.json"), "memory_summary_sha256": sha256(memory_dir / "deferred_memory_system_summary.csv")}
        active_rows.append((label, lifecycle_dir, memory_dir, lifecycle, memory, by_hardware))
    per: list[dict[str, Any]] = []
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for threshold in args.request_max_new_tokens_thresholds:
        for label, lifecycle_dir, memory_dir, lifecycle, _memory, by_hardware in active_rows:
            cap = int(lifecycle["config"]["max_new_tokens"])
            protected = cap < threshold
            for hardware, source in sorted(by_hardware.items()):
                item = {"workload": label, "request_id": lifecycle["request_id"], "lifecycle_dir": str(lifecycle_dir), "deferred_memory_dir": str(memory_dir), "request_max_new_tokens": cap, "request_cap_threshold": threshold, "gate_path": "full_kv_no_admission" if protected else "active_deferred_admission", "deferred_decode_steps": args.active_deferred_decode_steps, "admission_flush_token_budget": args.active_admission_flush_token_budget, **dict(zip(HARDWARE, hardware)), "net_bytes_saved_fraction": 0.0 if protected else float(source["net_bytes_saved_fraction"]), "net_cycle_proxy_saved_fraction": 0.0 if protected else float(source["net_cycle_proxy_saved_fraction"]), "interpretation": "Caller cap below threshold selects Full-KV with no admission; otherwise reuses the selected A3.11 modeled policy. max_new_tokens is an upper bound, not a future-length prediction."}
                per.append(item)
                grouped[(threshold, *hardware)].append(item)
    cross: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items()):
        threshold, *hardware = key
        if len(rows) != len(active_rows):
            raise AssertionError("missing workload at a request-cap gate point")
        bytes_ = [float(row["net_bytes_saved_fraction"]) for row in rows]
        cycles = [float(row["net_cycle_proxy_saved_fraction"]) for row in rows]
        worst = min(range(len(rows)), key=lambda index: cycles[index])
        cross.append({"request_cap_threshold": threshold, "deferred_decode_steps": args.active_deferred_decode_steps, "admission_flush_token_budget": args.active_admission_flush_token_budget, **dict(zip(HARDWARE, hardware)), "workload_count": len(rows), "all_workloads_nonnegative_cycle": all(value >= 0 for value in cycles), "all_workloads_positive_cycle": all(value > 0 for value in cycles), "min_net_bytes_saved_fraction": min(bytes_), "mean_net_bytes_saved_fraction": mean(bytes_), "min_net_cycle_proxy_saved_fraction": min(cycles), "mean_net_cycle_proxy_saved_fraction": mean(cycles), "worst_cycle_workload": rows[worst]["workload"]})
    return per, cross, provenance


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    per, cross, provenance = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "request_cap_gate_per_workload.csv", per, PER_COLUMNS)
    write_csv(args.output_dir / "request_cap_gate_cross_summary.csv", cross, CROSS_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a314-request-cap-gate-1.0", "git_commit": get_git_commit(), "workloads": provenance, "assumptions": {"request_max_new_tokens_thresholds": args.request_max_new_tokens_thresholds, "active_deferred_decode_steps": args.active_deferred_decode_steps, "active_admission_flush_token_budget": args.active_admission_flush_token_budget, "selection_features": ["caller max_new_tokens only"], "protected_semantic": "Full KV with zero admission"}, "boundaries": ["max_new_tokens is a caller-visible upper bound, not a prediction or guarantee of future decode length.", "This is an offline composition of A3.11 modeled results, not an online controller, HBM/DRAM measurement, latency/throughput result, sparse-attention execution, or generation result."]}
    (args.output_dir / "request_cap_gate_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3.14 evaluated {len(provenance)} workloads and {len(cross)} request-cap/hardware points: {args.output_dir}")


if __name__ == "__main__":
    main()
