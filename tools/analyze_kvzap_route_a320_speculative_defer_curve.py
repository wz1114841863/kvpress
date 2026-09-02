"""Analyze no-contract speculative deferred-admission curves from A3.11.

The input is a branch-consistent A3.11 step ledger for dense defer points.
It does not infer a future horizon or select a contract.  It reports what each
online-observable wait-D policy accumulated at every *observed* decode prefix,
plus an exact Full-KV reference row.  All byte/cycle fields are A3.11 models.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a314_request_cap_gate import HARDWARE, hardware_key
from tools.simulate_kvzap_route_a3_traffic import sha256


FINAL_COLUMNS = (
    "workload", "request_id", "deferred_decode_steps", "admission_flush_token_budget",
    *HARDWARE, "observed_decode_steps", "policy_activated_by_trace_end",
    "initial_full_kv_call_count", "staging_full_kv_call_count",
    "net_bytes_saved_fraction", "net_cycle_proxy_saved_fraction", "final_policy_class",
    "interpretation",
)
PREFIX_COLUMNS = (
    "workload", "request_id", "deferred_decode_steps", "admission_flush_token_budget",
    *HARDWARE, "observed_decode_steps", "decode_step", "policy_activated_at_prefix",
    "full_cumulative_bytes", "candidate_cumulative_bytes", "net_bytes_saved_fraction",
    "full_cumulative_cycle_proxy", "candidate_cumulative_cycle_proxy",
    "net_cycle_proxy_saved_fraction", "interpretation",
)
SUMMARY_COLUMNS = (
    "workload", "request_id", "admission_flush_token_budget", *HARDWARE,
    "observed_decode_steps", "dense_defer_count", "negative_final_defer_count",
    "positive_final_defer_count", "zero_final_defer_count", "best_final_deferred_decode_steps",
    "best_final_cycle_saving_fraction", "first_nonnegative_final_deferred_decode_steps",
    "strict_full_kv_reference_cycle_saving_fraction", "interpretation",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline Route-A3.20 no-contract speculative defer-curve analysis; never loads a model."
    )
    parser.add_argument("--deferred-memory-dir", type=Path, action="append", required=True,
                        help="Dense A3.11 deferred-memory output; repeat in workload-label order.")
    parser.add_argument("--workload-label", action="append", required=True,
                        help="Unique label for each --deferred-memory-dir.")
    parser.add_argument("--deferred-decode-steps-points", nargs="+", type=int, required=True,
                        help="Exact dense A3.11 defer points required in every input.")
    parser.add_argument("--admission-flush-token-budget", type=int, required=True,
                        help="One aligned A3.11 admission budget to analyze.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args(argv)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def policy_key(row: dict[str, str]) -> tuple[int, int]:
    return int(row["deferred_decode_steps"]), int(row["admission_flush_token_budget"])


def classify_final(*, deferred: int, observed_steps: int, saving: float, eps: float = 1e-9) -> str:
    if deferred >= observed_steps:
        if not math.isclose(saving, 0.0, abs_tol=eps):
            raise ValueError("unactivated deferred policy must equal Full-KV at trace end")
        return "strict_full_kv_no_admission"
    if saving > eps:
        return "speculative_admission_positive_at_observed_end"
    if saving < -eps:
        return "speculative_admission_negative_at_observed_end"
    return "speculative_admission_break_even_at_observed_end"


def load(directory: Path) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    manifest_path = directory / "deferred_memory_system_manifest.json"
    step_path = directory / "deferred_memory_system_step_results.csv"
    summary_path = directory / "deferred_memory_system_summary.csv"
    if not all(path.is_file() for path in (manifest_path, step_path, summary_path)):
        raise FileNotFoundError("A3.20 requires A3.11 deferred-memory manifest, step ledger, and summary")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a311-deferred-memory-system-dse-1.0":
        raise ValueError("unsupported A3.11 schema")
    return manifest, read_csv(step_path), read_csv(summary_path)


def validate_args(args: argparse.Namespace) -> None:
    if len(args.deferred_memory_dir) != len(args.workload_label) or not args.workload_label:
        raise ValueError("supply equal non-empty ordered --deferred-memory-dir/--workload-label lists")
    if len(set(args.workload_label)) != len(args.workload_label):
        raise ValueError("workload labels must be unique")
    if not args.deferred_decode_steps_points or min(args.deferred_decode_steps_points) < 0:
        raise ValueError("defer points must be non-empty and non-negative")
    if len(set(args.deferred_decode_steps_points)) != len(args.deferred_decode_steps_points):
        raise ValueError("defer points must be unique")
    if args.deferred_decode_steps_points != sorted(args.deferred_decode_steps_points):
        raise ValueError("defer points must be ascending")
    if args.admission_flush_token_budget <= 0:
        raise ValueError("admission budget must be positive")


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    validate_args(args)
    requested = set(args.deferred_decode_steps_points)
    final_rows: list[dict[str, Any]] = []
    prefix_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {}
    for label, directory in zip(args.workload_label, args.deferred_memory_dir, strict=True):
        _manifest, steps, summaries = load(directory)
        selected = [
            row for row in summaries
            if int(row["admission_flush_token_budget"]) == args.admission_flush_token_budget
            and int(row["deferred_decode_steps"]) in requested
        ]
        summary_by: dict[tuple[int, tuple[Any, ...]], dict[str, str]] = {}
        for row in selected:
            key = (int(row["deferred_decode_steps"]), hardware_key(row))
            if key in summary_by:
                raise ValueError(f"{label}: duplicate A3.11 final row for {key}")
            summary_by[key] = row
        grids = {defer: {hw for d, hw in summary_by if d == defer} for defer in requested}
        missing = [defer for defer in sorted(requested) if not grids[defer]]
        if missing:
            raise ValueError(f"{label}: missing requested dense defer points {missing}")
        hardware_grid = next(iter(grids.values()))
        if any(grid != hardware_grid for grid in grids.values()):
            raise ValueError(f"{label}: A3.11 hardware grid differs across defer points")
        request_ids = {row["request_id"] for row in selected}
        if len(request_ids) != 1:
            raise ValueError(f"{label}: A3.11 input mixes request ids")
        request_id = next(iter(request_ids))
        grouped: dict[tuple[int, tuple[Any, ...]], list[dict[str, str]]] = defaultdict(list)
        for row in steps:
            if int(row["admission_flush_token_budget"]) == args.admission_flush_token_budget and int(row["deferred_decode_steps"]) in requested:
                grouped[(int(row["deferred_decode_steps"]), hardware_key(row))].append(row)
        for hardware in sorted(hardware_grid):
            endpoints: list[dict[str, Any]] = []
            for defer in args.deferred_decode_steps_points:
                summary = summary_by[(defer, hardware)]
                rows = sorted(grouped[(defer, hardware)], key=lambda row: int(row["decode_step"]))
                observed = int(summary["decode_steps"])
                if [int(row["decode_step"]) for row in rows] != list(range(1, observed + 1)):
                    raise ValueError(f"{label}: non-contiguous A3.11 step ledger for defer={defer}")
                full_b = candidate_b = full_c = candidate_c = 0.0
                for row in rows:
                    full_b += float(row["full_total_bytes"]); candidate_b += float(row["candidate_total_bytes"])
                    full_c += float(row["full_total_cycle_proxy"]); candidate_c += float(row["candidate_total_cycle_proxy"])
                    prefix_rows.append({
                        "workload": label, "request_id": request_id, "deferred_decode_steps": defer,
                        "admission_flush_token_budget": args.admission_flush_token_budget,
                        **dict(zip(HARDWARE, hardware)), "observed_decode_steps": observed,
                        "decode_step": int(row["decode_step"]), "policy_activated_at_prefix": int(row["decode_step"]) > defer,
                        "full_cumulative_bytes": full_b, "candidate_cumulative_bytes": candidate_b,
                        "net_bytes_saved_fraction": (full_b - candidate_b) / full_b,
                        "full_cumulative_cycle_proxy": full_c, "candidate_cumulative_cycle_proxy": candidate_c,
                        "net_cycle_proxy_saved_fraction": (full_c - candidate_c) / full_c,
                        "interpretation": "Observed-prefix no-contract speculative policy curve from A3.11; modeled only, not an online controller or hardware measurement.",
                    })
                cycle = (full_c - candidate_c) / full_c
                byte = (full_b - candidate_b) / full_b
                if not math.isclose(cycle, float(summary["net_cycle_proxy_saved_fraction"]), abs_tol=1e-9):
                    raise ValueError(f"{label}: step ledger disagrees with A3.11 final cycle summary")
                if not math.isclose(byte, float(summary["net_bytes_saved_fraction"]), abs_tol=1e-9):
                    raise ValueError(f"{label}: step ledger disagrees with A3.11 final byte summary")
                endpoint = {
                    "workload": label, "request_id": request_id, "deferred_decode_steps": defer,
                    "admission_flush_token_budget": args.admission_flush_token_budget,
                    **dict(zip(HARDWARE, hardware)), "observed_decode_steps": observed,
                    "policy_activated_by_trace_end": defer < observed,
                    "initial_full_kv_call_count": int(summary["initial_full_kv_call_count"]),
                    "staging_full_kv_call_count": int(summary["staging_full_kv_call_count"]),
                    "net_bytes_saved_fraction": byte, "net_cycle_proxy_saved_fraction": cycle,
                    "final_policy_class": classify_final(deferred=defer, observed_steps=observed, saving=cycle),
                    "interpretation": "No trusted continuation contract: online-observable deferred admission, evaluated post-hoc on one observed trace; modeled only.",
                }
                final_rows.append(endpoint); endpoints.append(endpoint)
            values = [float(row["net_cycle_proxy_saved_fraction"]) for row in endpoints]
            best = max(endpoints, key=lambda row: float(row["net_cycle_proxy_saved_fraction"]))
            nonnegative = [row for row in endpoints if float(row["net_cycle_proxy_saved_fraction"]) >= -1e-9]
            summary_rows.append({
                "workload": label, "request_id": request_id, "admission_flush_token_budget": args.admission_flush_token_budget,
                **dict(zip(HARDWARE, hardware)), "observed_decode_steps": int(endpoints[0]["observed_decode_steps"]),
                "dense_defer_count": len(endpoints), "negative_final_defer_count": sum(value < -1e-9 for value in values),
                "positive_final_defer_count": sum(value > 1e-9 for value in values), "zero_final_defer_count": sum(abs(value) <= 1e-9 for value in values),
                "best_final_deferred_decode_steps": best["deferred_decode_steps"], "best_final_cycle_saving_fraction": best["net_cycle_proxy_saved_fraction"],
                "first_nonnegative_final_deferred_decode_steps": min((row["deferred_decode_steps"] for row in nonnegative), default="not_found"),
                "strict_full_kv_reference_cycle_saving_fraction": 0.0,
                "interpretation": "Final observed-horizon no-contract comparison; exact Full-KV is the zero-saving reference, not a Route-A benefit.",
            })
        provenance[label] = {
            "deferred_memory_dir": str(directory), "request_id": request_id,
            "memory_manifest_sha256": sha256(directory / "deferred_memory_system_manifest.json"),
            "memory_step_sha256": sha256(directory / "deferred_memory_system_step_results.csv"),
            "memory_summary_sha256": sha256(directory / "deferred_memory_system_summary.csv"),
        }
    return final_rows, prefix_rows, summary_rows, provenance


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    final_rows, prefix_rows, summary_rows, provenance = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "speculative_defer_final_curve.csv", final_rows, FINAL_COLUMNS)
    write_csv(args.output_dir / "speculative_defer_prefix_curve.csv", prefix_rows, PREFIX_COLUMNS)
    write_csv(args.output_dir / "speculative_defer_summary.csv", summary_rows, SUMMARY_COLUMNS)
    manifest = {
        "schema_version": "kvzap-route-a320-speculative-defer-curve-1.0", "git_commit": get_git_commit(), "workloads": provenance,
        "assumptions": {"deferred_decode_steps_points": args.deferred_decode_steps_points, "admission_flush_token_budget": args.admission_flush_token_budget,
                        "policy": "No trusted continuation contract. Full-KV/no-service through defer D, then branch-consistent A3.11 admission."},
        "output_contract": {"speculative_defer_final_curve.csv": "Final observed-horizon net byte/cycle curve over defer D.", "speculative_defer_prefix_curve.csv": "Cumulative byte/cycle curve for every (defer D, observed decode prefix).", "speculative_defer_summary.csv": "Per-workload/hardware speculative loss, break-even, gain, and Full-KV reference."},
        "boundaries": ["Observed horizon is post-hoc only; no future horizon or contract is inferred online.", "Deferred admission does not establish policy-on generation equivalence.", "A3.11 bytes/cycles are models, not HBM/DRAM, allocator, latency, throughput, or hardware measurements."],
    }
    (args.output_dir / "speculative_defer_curve_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3.20 analyzed {len(provenance)} workloads, {len(final_rows)} final points, and {len(prefix_rows)} observed-prefix points: {args.output_dir}")


if __name__ == "__main__":
    main()
