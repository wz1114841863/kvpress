"""Summarize a fixed A3.9 gate point across independently collected workloads.

Inputs are completed state-consistent A3.9 directories.  This tool neither
loads a model nor chooses thresholds; callers must fix one threshold pair
before applying it to every named evaluation workload.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a3_traffic import sha256


PER_WORKLOAD_COLUMNS = (
    "workload", "request_id", "consistent_gate_dir", "pending_token_threshold", "max_bank_burst_threshold", "hardware_point_count", "all_hardware_points_positive_cycle", "min_heuristic_net_cycle_saved_fraction", "mean_heuristic_net_cycle_saved_fraction", "max_heuristic_net_cycle_saved_fraction", "mean_oracle_net_cycle_saved_fraction", "mean_cycle_regret_fraction_of_full", "mean_heuristic_net_bytes_saved_fraction", "mean_agreement_fraction", "mean_false_hybrid_count", "mean_false_full_count", "worst_hardware_point",
)
ROBUSTNESS_COLUMNS = (
    "pending_token_threshold", "max_bank_burst_threshold", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "workload_count", "all_workloads_positive_cycle", "min_heuristic_net_cycle_saved_fraction", "mean_heuristic_net_cycle_saved_fraction", "max_heuristic_net_cycle_saved_fraction", "min_heuristic_net_bytes_saved_fraction", "mean_agreement_fraction", "max_false_hybrid_count", "max_false_full_count",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize one fixed A3.9 observable-gate threshold pair across workloads; never loads a model.")
    parser.add_argument("--consistent-gate-dir", type=Path, action="append", required=True, help="Completed A3.9 directory; repeat once per workload.")
    parser.add_argument("--workload-label", action="append", required=True, help="Human-readable workload label; repeat in the same order as --consistent-gate-dir.")
    parser.add_argument("--pending-token-threshold", type=int, required=True)
    parser.add_argument("--max-bank-burst-threshold", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args(argv)


def write_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def load_fixed_point(directory: Path, *, pending: int, bursts: int) -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest_path, summary_path = directory / "consistent_gate_manifest.json", directory / "consistent_gate_summary.csv"
    if not manifest_path.is_file() or not summary_path.is_file():
        raise FileNotFoundError(f"A3.9 manifest or summary missing: {directory}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a39-consistent-gate-dse-1.0" or manifest.get("assumptions", {}).get("admission_mode") != "continue_admission":
        raise ValueError(f"unsupported or non-state-consistent A3.9 input: {directory}")
    rows = [row for row in csv.DictReader(summary_path.open(encoding="utf-8", newline="")) if int(row["pending_token_threshold"]) == pending and int(row["max_bank_burst_threshold"]) == bursts]
    if not rows:
        raise ValueError(f"A3.9 input has no requested threshold point P={pending}, Q={bursts}: {directory}")
    return manifest, rows


def mean(rows: list[dict[str, str]], field: str) -> float:
    return sum(float(row[field]) for row in rows) / len(rows)


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if len(args.consistent_gate_dir) != len(args.workload_label) or len(args.workload_label) < 2 or len(set(args.workload_label)) != len(args.workload_label):
        raise ValueError("supply at least two unique workload labels, paired in order with --consistent-gate-dir")
    per_workload: list[dict[str, Any]] = []
    robust: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    provenance: dict[str, Any] = {}
    for label, directory in zip(args.workload_label, args.consistent_gate_dir, strict=True):
        manifest, rows = load_fixed_point(directory, pending=args.pending_token_threshold, bursts=args.max_bank_burst_threshold)
        request_ids = {row["request_id"] for row in rows}
        if len(request_ids) != 1:
            raise ValueError(f"A3.9 summary contains multiple request IDs: {directory}")
        worst = min(rows, key=lambda row: float(row["heuristic_net_cycle_proxy_saved_fraction"]))
        per_workload.append({"workload": label, "request_id": request_ids.pop(), "consistent_gate_dir": str(directory), "pending_token_threshold": args.pending_token_threshold, "max_bank_burst_threshold": args.max_bank_burst_threshold, "hardware_point_count": len(rows), "all_hardware_points_positive_cycle": all(float(row["heuristic_net_cycle_proxy_saved_fraction"]) > 0 for row in rows), "min_heuristic_net_cycle_saved_fraction": float(worst["heuristic_net_cycle_proxy_saved_fraction"]), "mean_heuristic_net_cycle_saved_fraction": mean(rows, "heuristic_net_cycle_proxy_saved_fraction"), "max_heuristic_net_cycle_saved_fraction": max(float(row["heuristic_net_cycle_proxy_saved_fraction"]) for row in rows), "mean_oracle_net_cycle_saved_fraction": mean(rows, "oracle_net_cycle_proxy_saved_fraction"), "mean_cycle_regret_fraction_of_full": mean(rows, "cycle_regret_fraction_of_full"), "mean_heuristic_net_bytes_saved_fraction": mean(rows, "heuristic_net_bytes_saved_fraction"), "mean_agreement_fraction": mean(rows, "agreement_fraction"), "mean_false_hybrid_count": mean(rows, "false_hybrid_count"), "mean_false_full_count": mean(rows, "false_full_count"), "worst_hardware_point": json.dumps({key: worst[key] for key in ("bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer")}, sort_keys=True)})
        for row in rows:
            key = tuple(row[name] for name in ("bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer"))
            robust[key].append(row)
        provenance[label] = {"directory": str(directory), "consistent_gate_manifest_sha256": sha256(directory / "consistent_gate_manifest.json"), "consistent_gate_summary_sha256": sha256(directory / "consistent_gate_summary.csv"), "request_id": per_workload[-1]["request_id"]}
    robustness: list[dict[str, Any]] = []
    expected = len(args.workload_label)
    for axes, rows in sorted(robust.items()):
        if len(rows) != expected:
            raise ValueError("workloads do not share an identical hardware sweep")
        cycles = [float(row["heuristic_net_cycle_proxy_saved_fraction"]) for row in rows]
        robustness.append({"pending_token_threshold": args.pending_token_threshold, "max_bank_burst_threshold": args.max_bank_burst_threshold, **dict(zip(("bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer"), axes)), "workload_count": len(rows), "all_workloads_positive_cycle": all(value > 0 for value in cycles), "min_heuristic_net_cycle_saved_fraction": min(cycles), "mean_heuristic_net_cycle_saved_fraction": sum(cycles) / len(cycles), "max_heuristic_net_cycle_saved_fraction": max(cycles), "min_heuristic_net_bytes_saved_fraction": min(float(row["heuristic_net_bytes_saved_fraction"]) for row in rows), "mean_agreement_fraction": mean(rows, "agreement_fraction"), "max_false_hybrid_count": max(int(row["false_hybrid_count"]) for row in rows), "max_false_full_count": max(int(row["false_full_count"]) for row in rows)})
    return per_workload, robustness, provenance


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    if args.pending_token_threshold < 0 or args.max_bank_burst_threshold < 0:
        raise ValueError("thresholds must be non-negative")
    per_workload, robustness, provenance = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "cross_workload_gate_summary.csv", per_workload, PER_WORKLOAD_COLUMNS)
    write_csv(args.output_dir / "cross_workload_hardware_robustness.csv", robustness, ROBUSTNESS_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a39-cross-workload-summary-1.0", "git_commit": get_git_commit(), "workload_labels": args.workload_label, "fixed_threshold": {"pending_token_threshold": args.pending_token_threshold, "max_bank_burst_threshold": args.max_bank_burst_threshold}, "source_artifact_sha256": provenance, "boundaries": ["The threshold is supplied by the caller and is not selected by this tool.", "This summarizes independently modeled A3.9 continue-admission runs. It does not prove cross-workload online-controller generalization, hardware performance, sparse attention, or generation equivalence."]}
    (args.output_dir / "cross_workload_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3.9 cross-workload summary wrote {len(per_workload)} workloads and {len(robustness)} common hardware points: {args.output_dir}")


if __name__ == "__main__":
    main()
