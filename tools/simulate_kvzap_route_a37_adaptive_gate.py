"""Choose a declared hybrid or Full-KV path per layer from A3.7 cost rows.

This is an offline cost-gate DSE, not a deployable controller or a measured
hardware result.  It intentionally consumes the A3.7 ledger instead of model
inputs so its decisions are reproducible without loading a model.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a3_traffic import read_csv, sha256


DECISION_COLUMNS = (
    "request_id", "model_call", "decode_step", "layer", "decision_objective", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "pending_dense_tokens", "fallback_full_kv", "full_layer_bytes", "hybrid_total_bytes", "full_layer_cycle_proxy", "hybrid_total_cycle_proxy", "selected_path", "decision_reason", "selected_total_bytes", "selected_total_cycle_proxy",
)
STEP_COLUMNS = (
    "request_id", "model_call", "decode_step", "decision_objective", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "full_total_bytes", "adaptive_total_bytes", "net_bytes_saved", "full_total_cycle_proxy", "adaptive_total_cycle_proxy", "net_cycle_proxy_saved", "hybrid_layer_count", "full_kv_layer_count", "capacity_fallback_layer_count",
)
SUMMARY_COLUMNS = (
    "request_id", "decision_objective", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "decode_steps", "full_kv_cumulative_bytes", "adaptive_cumulative_bytes", "net_bytes_saved", "net_bytes_saved_fraction", "full_kv_cumulative_cycle_proxy", "adaptive_cumulative_cycle_proxy", "net_cycle_proxy_saved", "net_cycle_proxy_saved_fraction", "hybrid_layer_count", "full_kv_layer_count", "capacity_fallback_layer_count", "interpretation",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3.7 adaptive hybrid/Full-KV layer-gate DSE; never loads a model.")
    parser.add_argument("--memory-system-dir", type=Path, required=True, help="Completed A3.7 memory-system DSE directory.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    parser.add_argument("--decision-objectives", nargs="+", choices=("bytes", "cycles"), default=["cycles"], help="Cost metric used for an explicitly oracle-like per-layer choice.")
    parser.add_argument("--hybrid-guard-fraction", type=float, default=0.0, help="Require hybrid objective to be at most Full-KV*(1-guard); models a guard band, not predictor accuracy.")
    return parser.parse_args(argv)


def write_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def choose_layer_path(row: dict[str, str], *, objective: str, guard_fraction: float) -> tuple[str, str]:
    """Return path and auditable reason.  Capacity fallback is never relabeled hybrid."""
    if str(row["fallback_full_kv"]).lower() in {"1", "true", "yes"}:
        return "full_kv", "staging_capacity_fallback"
    full_key, hybrid_key = ("full_layer_bytes", "hybrid_total_bytes") if objective == "bytes" else ("full_layer_cycle_proxy", "hybrid_total_cycle_proxy")
    full, hybrid = float(row[full_key]), float(row[hybrid_key])
    if hybrid <= full * (1.0 - guard_fraction):
        return "hybrid", f"hybrid_{objective}_not_above_guarded_full"
    return "full_kv", f"hybrid_{objective}_above_guarded_full"


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    manifest_path = args.memory_system_dir / "memory_system_manifest.json"
    layers_path = args.memory_system_dir / "memory_system_layer_results.csv"
    if not manifest_path.is_file() or not layers_path.is_file():
        raise FileNotFoundError("A3.7 memory-system manifest or layer ledger is missing")
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("schema_version") != "kvzap-route-a37-memory-system-dse-1.0":
        raise ValueError("unsupported memory-system DSE schema")
    rows = [row for row in read_csv(layers_path) if row["baseline"] == "hybrid_memory_system"]
    if not rows:
        raise ValueError("memory-system layer ledger has no hybrid rows")
    decisions: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    dimensions = ("bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer")
    for objective in args.decision_objectives:
        grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            grouped[tuple([row["request_id"], row["model_call"], row["decode_step"], *[row[key] for key in dimensions]])].append(row)
        summary_groups: dict[tuple[str, ...], dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for identity, members in sorted(grouped.items(), key=lambda item: tuple(int(x) if x.isdigit() else x for x in item[0])):
            request_id, call, step, *axis = identity
            full_b = adaptive_b = full_c = adaptive_c = 0.0
            hybrid_count = full_count = capacity_count = 0
            for row in sorted(members, key=lambda item: int(item["layer"])):
                selected, reason = choose_layer_path(row, objective=objective, guard_fraction=args.hybrid_guard_fraction)
                full_bytes, hybrid_bytes = float(row["full_layer_bytes"]), float(row["hybrid_total_bytes"])
                full_cycles, hybrid_cycles = float(row["full_layer_cycle_proxy"]), float(row["hybrid_total_cycle_proxy"])
                selected_bytes = hybrid_bytes if selected == "hybrid" else full_bytes
                selected_cycles = hybrid_cycles if selected == "hybrid" else full_cycles
                full_b += full_bytes
                adaptive_b += selected_bytes
                full_c += full_cycles
                adaptive_c += selected_cycles
                hybrid_count += selected == "hybrid"
                full_count += selected == "full_kv"
                capacity_count += reason == "staging_capacity_fallback"
                decisions.append({"request_id": request_id, "model_call": int(call), "decode_step": int(step), "layer": int(row["layer"]), "decision_objective": objective, **dict(zip(dimensions, axis)), "pending_dense_tokens": int(row["pending_dense_tokens"]), "fallback_full_kv": row["fallback_full_kv"], "full_layer_bytes": full_bytes, "hybrid_total_bytes": hybrid_bytes, "full_layer_cycle_proxy": full_cycles, "hybrid_total_cycle_proxy": hybrid_cycles, "selected_path": selected, "decision_reason": reason, "selected_total_bytes": selected_bytes, "selected_total_cycle_proxy": selected_cycles})
            record = {"request_id": request_id, "model_call": int(call), "decode_step": int(step), "decision_objective": objective, **dict(zip(dimensions, axis)), "full_total_bytes": full_b, "adaptive_total_bytes": adaptive_b, "net_bytes_saved": full_b - adaptive_b, "full_total_cycle_proxy": full_c, "adaptive_total_cycle_proxy": adaptive_c, "net_cycle_proxy_saved": full_c - adaptive_c, "hybrid_layer_count": hybrid_count, "full_kv_layer_count": full_count, "capacity_fallback_layer_count": capacity_count}
            steps.append(record)
            group_key = tuple([request_id, objective, *axis])
            aggregate = summary_groups[group_key]
            for key in ("full_total_bytes", "adaptive_total_bytes", "full_total_cycle_proxy", "adaptive_total_cycle_proxy", "hybrid_layer_count", "full_kv_layer_count", "capacity_fallback_layer_count"):
                aggregate[key] += record[key]
            aggregate["decode_steps"] += 1
        for key, value in sorted(summary_groups.items()):
            request_id, objective, *axis = key
            summaries.append({"request_id": request_id, "decision_objective": objective, **dict(zip(dimensions, axis)), "decode_steps": int(value["decode_steps"]), "full_kv_cumulative_bytes": value["full_total_bytes"], "adaptive_cumulative_bytes": value["adaptive_total_bytes"], "net_bytes_saved": value["full_total_bytes"] - value["adaptive_total_bytes"], "net_bytes_saved_fraction": (value["full_total_bytes"] - value["adaptive_total_bytes"]) / value["full_total_bytes"], "full_kv_cumulative_cycle_proxy": value["full_total_cycle_proxy"], "adaptive_cumulative_cycle_proxy": value["adaptive_total_cycle_proxy"], "net_cycle_proxy_saved": value["full_total_cycle_proxy"] - value["adaptive_total_cycle_proxy"], "net_cycle_proxy_saved_fraction": (value["full_total_cycle_proxy"] - value["adaptive_total_cycle_proxy"]) / value["full_total_cycle_proxy"], "hybrid_layer_count": int(value["hybrid_layer_count"]), "full_kv_layer_count": int(value["full_kv_layer_count"]), "capacity_fallback_layer_count": int(value["capacity_fallback_layer_count"]), "interpretation": "Per-layer choice uses the same call's modeled ledger and is therefore an oracle-like DSE gate, not an online predictor, hardware controller, sparse-attention execution, or performance measurement."})
    return decisions, steps, summaries, {"memory_system_manifest_sha256": sha256(manifest_path), "memory_system_layer_results_sha256": sha256(layers_path)}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    if not 0.0 <= args.hybrid_guard_fraction < 1.0 or not args.decision_objectives or len(set(args.decision_objectives)) != len(args.decision_objectives):
        raise ValueError("invalid adaptive-gate assumptions")
    decisions, steps, summaries, provenance = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "adaptive_gate_layer_decisions.csv", decisions, DECISION_COLUMNS)
    write_csv(args.output_dir / "adaptive_gate_step_results.csv", steps, STEP_COLUMNS)
    write_csv(args.output_dir / "adaptive_gate_summary.csv", summaries, SUMMARY_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a37-adaptive-gate-dse-1.0", "git_commit": get_git_commit(), "memory_system_dir": str(args.memory_system_dir), "source_artifact_sha256": provenance, "assumptions": {"decision_objectives": args.decision_objectives, "hybrid_guard_fraction": args.hybrid_guard_fraction}, "boundaries": ["The gate evaluates same-call modeled costs and is oracle-like; it is not an implementable online predictor.", "No result is a DRAM/HBM counter, allocator measurement, latency/throughput result, sparse-attention execution, or generation/accuracy result."]}
    (args.output_dir / "adaptive_gate_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3.7 adaptive gate modeled {len(summaries)} summaries, {len(steps)} steps, and {len(decisions)} layer decisions: {args.output_dir}")


if __name__ == "__main__":
    main()
