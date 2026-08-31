"""Validate the A3.13 no-admission short-horizon Full-KV control."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a3_traffic import sha256


OUTPUT_COLUMNS = (
    "request_id", "deferred_decode_steps", "admission_flush_token_budget", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "decode_steps", "initial_full_kv_call_count", "staging_full_kv_call_count", "staging_full_kv_layer_count", "net_bytes_saved_fraction", "net_cycle_proxy_saved_fraction", "guard_passed", "interpretation",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3.13 short-horizon Full-KV guard validator; never loads a model.")
    parser.add_argument("--deferred-memory-dir", type=Path, required=True, help="Completed A3.11 directory containing the requested guard variants.")
    parser.add_argument("--guard-deferred-decode-steps", nargs="+", type=int, required=True, help="Guard horizons to validate; each must be at least the observed decode-step count.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args(argv)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_rows(rows: list[dict[str, str]], *, horizons: set[int]) -> list[dict[str, Any]]:
    selected = [row for row in rows if int(row["deferred_decode_steps"]) in horizons]
    found = {int(row["deferred_decode_steps"]) for row in selected}
    missing = horizons - found
    if missing:
        raise ValueError(f"requested guard horizon(s) absent from A3.11 summary: {sorted(missing)}")
    result: list[dict[str, Any]] = []
    for row in selected:
        decode_steps, horizon = int(row["decode_steps"]), int(row["deferred_decode_steps"])
        if horizon < decode_steps:
            raise ValueError(f"guard horizon {horizon} is shorter than observed decode length {decode_steps}")
        full_bytes, candidate_bytes = float(row["full_kv_cumulative_bytes"]), float(row["candidate_cumulative_bytes"])
        full_cycles, candidate_cycles = float(row["full_kv_cumulative_cycle_proxy"]), float(row["candidate_cumulative_cycle_proxy"])
        zero_cost = math.isclose(full_bytes, candidate_bytes, abs_tol=1e-9) and math.isclose(full_cycles, candidate_cycles, abs_tol=1e-9)
        passed = zero_cost and int(row["initial_full_kv_call_count"]) == decode_steps and int(row["staging_full_kv_call_count"]) == 0 and int(row["staging_full_kv_layer_count"]) == 0
        if not passed:
            raise ValueError("short-horizon guard did not degenerate exactly to no-admission Full KV")
        result.append({**{field: row[field] for field in OUTPUT_COLUMNS if field in row}, "guard_passed": True, "interpretation": "Observed decode horizon was fully protected: Full-KV attention and zero admission service. This is a no-gain/no-loss control, not an online horizon predictor."})
    return result


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    if not args.guard_deferred_decode_steps or min(args.guard_deferred_decode_steps) < 0 or len(set(args.guard_deferred_decode_steps)) != len(args.guard_deferred_decode_steps):
        raise ValueError("guard horizons must be unique non-negative integers")
    manifest_path = args.deferred_memory_dir / "deferred_memory_system_manifest.json"
    summary_path = args.deferred_memory_dir / "deferred_memory_system_summary.csv"
    if not manifest_path.is_file() or not summary_path.is_file():
        raise FileNotFoundError("A3.13 requires A3.11 manifest and summary")
    input_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if input_manifest.get("schema_version") != "kvzap-route-a311-deferred-memory-system-dse-1.0":
        raise ValueError("A3.13 requires A3.11 deferred memory-system evidence")
    checked = validate_rows(read_csv(summary_path), horizons=set(args.guard_deferred_decode_steps))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "short_horizon_guard_summary.csv", checked)
    manifest = {"schema_version": "kvzap-route-a313-short-horizon-guard-1.0", "git_commit": get_git_commit(), "deferred_memory_dir": str(args.deferred_memory_dir), "source_artifact_sha256": {"deferred_memory_manifest_sha256": sha256(manifest_path), "deferred_memory_summary_sha256": sha256(summary_path)}, "assumptions": {"guard_deferred_decode_steps": args.guard_deferred_decode_steps, "pass_condition": "guard horizon >= observed decode steps; candidate cumulative bytes/cycles equal Full KV; no staging fallback; all decode calls initial Full-KV"}, "boundaries": ["This is a trace-known-horizon control, not a deployable output-length predictor or controller.", "No result is a DRAM/HBM counter, allocator measurement, latency/throughput result, sparse-attention execution, or generation result."]}
    (args.output_dir / "short_horizon_guard_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3.13 validated {len(checked)} no-admission Full-KV guard points: {args.output_dir}")


if __name__ == "__main__":
    main()
