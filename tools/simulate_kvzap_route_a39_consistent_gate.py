"""A3.9 state-consistent observable gate with continued admission.

Unlike A3.7/A3.8's preliminary per-layer accounting, a Full-KV attention
fallback here does not make admission disappear.  Each layer pays its recorded
post-attention admission ledger regardless of which attention-read path is
selected; this preserves the supplied shadow's future packed/FIFO state.

This deliberately models only ``continue_admission``.  A true
``defer_admission`` policy needs a branch-dependent FIFO/page replay and cannot
be reconstructed exactly from schema-1.4's count-only head progress.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a37_adaptive_gate import choose_layer_path
from tools.simulate_kvzap_route_a38_observable_gate import choose_observable_path
from tools.simulate_kvzap_route_a3_traffic import sha256


SUMMARY_COLUMNS = (
    "request_id", "admission_mode", "pending_token_threshold", "max_bank_burst_threshold", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "decode_steps", "layer_decisions", "oracle_hybrid_layer_count", "heuristic_hybrid_layer_count", "agreement_count", "agreement_fraction", "false_hybrid_count", "false_full_count", "full_kv_cumulative_bytes", "oracle_cumulative_bytes", "heuristic_cumulative_bytes", "oracle_net_bytes_saved_fraction", "heuristic_net_bytes_saved_fraction", "byte_regret_fraction_of_full", "full_kv_cumulative_cycle_proxy", "oracle_cumulative_cycle_proxy", "heuristic_cumulative_cycle_proxy", "oracle_net_cycle_proxy_saved_fraction", "heuristic_net_cycle_proxy_saved_fraction", "cycle_regret_fraction_of_full", "admission_cumulative_bytes", "interpretation",
)
DECISION_COLUMNS = (
    "request_id", "model_call", "decode_step", "layer", "admission_mode", "pending_token_threshold", "max_bank_burst_threshold", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "pending_dense_tokens", "pending_burst_count", "max_bank_burst_count", "fallback_full_kv", "admission_bytes", "heuristic_path", "heuristic_reason", "oracle_path", "oracle_reason", "full_layer_bytes", "hybrid_layer_bytes", "full_layer_cycle_proxy", "hybrid_layer_cycle_proxy", "heuristic_total_bytes", "heuristic_total_cycle_proxy", "oracle_total_bytes", "oracle_total_cycle_proxy",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3.9 state-consistent continue-admission gate DSE; never loads a model.")
    parser.add_argument("--memory-system-dir", type=Path, required=True, help="Completed A3.7 memory-system DSE directory.")
    parser.add_argument("--oracle-gate-dir", type=Path, required=True, help="Matching A3.7 gate directory; supplies only the declared cycle guard and provenance binding.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    parser.add_argument("--pending-token-thresholds", nargs="+", type=int, default=[0, 512, 2048, 8192, 32768])
    parser.add_argument("--max-bank-burst-thresholds", nargs="+", type=int, default=[0, 8, 32, 128])
    parser.add_argument("--emit-decision-point", nargs=2, type=int, metavar=("PENDING", "BURSTS"))
    return parser.parse_args(argv)


def write_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def validate_inputs(memory_dir: Path, oracle_dir: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    memory_manifest_path = memory_dir / "memory_system_manifest.json"
    oracle_manifest_path = oracle_dir / "adaptive_gate_manifest.json"
    layer_path = memory_dir / "memory_system_layer_results.csv"
    if not all(path.is_file() for path in (memory_manifest_path, oracle_manifest_path, layer_path)):
        raise FileNotFoundError("A3.7 memory-system ledger or matching oracle-gate manifest is missing")
    memory = json.loads(memory_manifest_path.read_text(encoding="utf-8"))
    oracle = json.loads(oracle_manifest_path.read_text(encoding="utf-8"))
    if memory.get("schema_version") != "kvzap-route-a37-memory-system-dse-1.0" or oracle.get("schema_version") != "kvzap-route-a37-adaptive-gate-dse-1.0":
        raise ValueError("unsupported A3.7 input schema")
    if "cycles" not in oracle.get("assumptions", {}).get("decision_objectives", []):
        raise ValueError("A3.9 requires an A3.7 cycle-objective oracle-gate manifest")
    if oracle.get("source_artifact_sha256", {}).get("memory_system_manifest_sha256") != sha256(memory_manifest_path):
        raise ValueError("oracle gate is not bound to the supplied memory-system manifest")
    return memory, oracle, layer_path


def total_with_continued_admission(row: dict[str, str], path: str, *, admission_bandwidth: float) -> tuple[float, float]:
    """Charge recorded admission after either attention choice, preserving state."""
    attention_bytes = float(row["hybrid_layer_bytes"] if path == "hybrid" else row["full_layer_bytes"])
    attention_cycles = float(row["hybrid_layer_cycle_proxy"] if path == "hybrid" else row["full_layer_cycle_proxy"])
    admission = float(row["admission_bytes"])
    return attention_bytes + admission, attention_cycles + admission / admission_bandwidth


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    memory, oracle_manifest, layer_path = validate_inputs(args.memory_system_dir, args.oracle_gate_dir)
    bandwidth = float(memory["assumptions"]["bandwidth_bytes_per_cycle"])
    guard = float(oracle_manifest["assumptions"]["hybrid_guard_fraction"])
    thresholds = [(pending, bursts) for pending in args.pending_token_thresholds for bursts in args.max_bank_burst_thresholds]
    dimensions = ("bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer")
    totals: dict[tuple[Any, ...], dict[str, Any]] = defaultdict(lambda: defaultdict(float))
    audit: list[dict[str, Any]] = []
    with layer_path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["baseline"] != "hybrid_memory_system":
                continue
            # Oracle chooses an attention path only.  Admission is independent
            # of that choice and is charged by total_with_continued_admission.
            oracle_path, oracle_reason = choose_layer_path({**row, "hybrid_total_cycle_proxy": row["hybrid_layer_cycle_proxy"], "hybrid_total_bytes": row["hybrid_layer_bytes"]}, objective="cycles", guard_fraction=guard)
            axis = tuple(row[key] for key in dimensions)
            full_bytes = float(row["full_layer_bytes"])
            full_cycles = float(row["full_layer_cycle_proxy"])
            oracle_bytes, oracle_cycles = total_with_continued_admission(row, oracle_path, admission_bandwidth=bandwidth)
            for pending, bursts in thresholds:
                heuristic_path, heuristic_reason = choose_observable_path(row, pending_threshold=pending, max_bank_burst_threshold=bursts)
                heuristic_bytes, heuristic_cycles = total_with_continued_admission(row, heuristic_path, admission_bandwidth=bandwidth)
                key = (row["request_id"], pending, bursts, *axis)
                result = totals[key]
                result["full_bytes"] += full_bytes
                result["full_cycles"] += full_cycles
                result["oracle_bytes"] += oracle_bytes
                result["oracle_cycles"] += oracle_cycles
                result["heuristic_bytes"] += heuristic_bytes
                result["heuristic_cycles"] += heuristic_cycles
                result["admission_bytes"] += float(row["admission_bytes"])
                result["decisions"] += 1
                result.setdefault("layers", set()).add(int(row["layer"]))
                result["oracle_hybrid"] += oracle_path == "hybrid"
                result["heuristic_hybrid"] += heuristic_path == "hybrid"
                result["agreement"] += oracle_path == heuristic_path
                result["false_hybrid"] += heuristic_path == "hybrid" and oracle_path == "full_kv"
                result["false_full"] += heuristic_path == "full_kv" and oracle_path == "hybrid"
                if args.emit_decision_point == [pending, bursts]:
                    audit.append({"request_id": row["request_id"], "model_call": int(row["model_call"]), "decode_step": int(row["decode_step"]), "layer": int(row["layer"]), "admission_mode": "continue_admission", "pending_token_threshold": pending, "max_bank_burst_threshold": bursts, **dict(zip(dimensions, axis)), "pending_dense_tokens": int(row["pending_dense_tokens"]), "pending_burst_count": int(row["pending_burst_count"]), "max_bank_burst_count": int(row["max_bank_burst_count"]), "fallback_full_kv": row["fallback_full_kv"], "admission_bytes": row["admission_bytes"], "heuristic_path": heuristic_path, "heuristic_reason": heuristic_reason, "oracle_path": oracle_path, "oracle_reason": oracle_reason, "full_layer_bytes": full_bytes, "hybrid_layer_bytes": float(row["hybrid_layer_bytes"]), "full_layer_cycle_proxy": full_cycles, "hybrid_layer_cycle_proxy": float(row["hybrid_layer_cycle_proxy"]), "heuristic_total_bytes": heuristic_bytes, "heuristic_total_cycle_proxy": heuristic_cycles, "oracle_total_bytes": oracle_bytes, "oracle_total_cycle_proxy": oracle_cycles})
    summaries: list[dict[str, Any]] = []
    for key, value in sorted(totals.items()):
        request_id, pending, bursts, *axis = key
        full_b, full_c = value["full_bytes"], value["full_cycles"]
        decode_steps = value["decisions"] / len(value["layers"])
        if not decode_steps.is_integer():
            raise ValueError("layer ledger does not contain complete decode calls")
        summaries.append({"request_id": request_id, "admission_mode": "continue_admission", "pending_token_threshold": pending, "max_bank_burst_threshold": bursts, **dict(zip(dimensions, axis)), "decode_steps": int(decode_steps), "layer_decisions": int(value["decisions"]), "oracle_hybrid_layer_count": int(value["oracle_hybrid"]), "heuristic_hybrid_layer_count": int(value["heuristic_hybrid"]), "agreement_count": int(value["agreement"]), "agreement_fraction": value["agreement"] / value["decisions"], "false_hybrid_count": int(value["false_hybrid"]), "false_full_count": int(value["false_full"]), "full_kv_cumulative_bytes": full_b, "oracle_cumulative_bytes": value["oracle_bytes"], "heuristic_cumulative_bytes": value["heuristic_bytes"], "oracle_net_bytes_saved_fraction": (full_b - value["oracle_bytes"]) / full_b, "heuristic_net_bytes_saved_fraction": (full_b - value["heuristic_bytes"]) / full_b, "byte_regret_fraction_of_full": (value["heuristic_bytes"] - value["oracle_bytes"]) / full_b, "full_kv_cumulative_cycle_proxy": full_c, "oracle_cumulative_cycle_proxy": value["oracle_cycles"], "heuristic_cumulative_cycle_proxy": value["heuristic_cycles"], "oracle_net_cycle_proxy_saved_fraction": (full_c - value["oracle_cycles"]) / full_c, "heuristic_net_cycle_proxy_saved_fraction": (full_c - value["heuristic_cycles"]) / full_c, "cycle_regret_fraction_of_full": (value["heuristic_cycles"] - value["oracle_cycles"]) / full_c, "admission_cumulative_bytes": value["admission_bytes"], "interpretation": "Full-KV is an attention-only fallback while recorded admission continues and is charged on both paths. This preserves the supplied shadow state. It is a model, not a deferred-admission replay, measured hardware result, or policy-on generation result."})
    provenance = {"memory_system_manifest_sha256": sha256(args.memory_system_dir / "memory_system_manifest.json"), "memory_system_layer_results_sha256": sha256(layer_path), "oracle_gate_manifest_sha256": sha256(args.oracle_gate_dir / "adaptive_gate_manifest.json")}
    return summaries, audit, provenance


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    if not args.pending_token_thresholds or not args.max_bank_burst_thresholds or min(args.pending_token_thresholds) < 0 or min(args.max_bank_burst_thresholds) < 0 or len(set(args.pending_token_thresholds)) != len(args.pending_token_thresholds) or len(set(args.max_bank_burst_thresholds)) != len(args.max_bank_burst_thresholds):
        raise ValueError("thresholds must be non-negative, non-empty, and unique")
    if args.emit_decision_point is not None and tuple(args.emit_decision_point) not in {(p, b) for p in args.pending_token_thresholds for b in args.max_bank_burst_thresholds}:
        raise ValueError("--emit-decision-point must be one of the scanned threshold pairs")
    summaries, audit, provenance = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "consistent_gate_summary.csv", summaries, SUMMARY_COLUMNS)
    if args.emit_decision_point is not None:
        write_csv(args.output_dir / "consistent_gate_layer_decisions.csv", audit, DECISION_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a39-consistent-gate-dse-1.0", "git_commit": get_git_commit(), "memory_system_dir": str(args.memory_system_dir), "oracle_gate_dir": str(args.oracle_gate_dir), "source_artifact_sha256": provenance, "assumptions": {"admission_mode": "continue_admission", "pending_token_thresholds": args.pending_token_thresholds, "max_bank_burst_thresholds": args.max_bank_burst_thresholds, "emit_decision_point": args.emit_decision_point, "oracle_objective": "cycles", "oracle_guard_fraction": float(json.loads((args.oracle_gate_dir / "adaptive_gate_manifest.json").read_text(encoding="utf-8"))["assumptions"]["hybrid_guard_fraction"])}, "boundaries": ["Full-KV is only an attention read-path fallback. Recorded admission continues after either path and is charged on both paths, so canonical shadow state remains valid.", "defer_admission is intentionally not modeled because count-only schema-1.4 does not contain enough pending-position detail for exact branch-dependent oldest-first replay.", "No result is a DRAM/HBM counter, allocator measurement, latency/throughput result, sparse-attention execution, or generation/accuracy result."]}
    (args.output_dir / "consistent_gate_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3.9 modeled {len(summaries)} state-consistent summaries" + (f" and {len(audit)} audit decisions" if args.emit_decision_point is not None else "") + f": {args.output_dir}")


if __name__ == "__main__":
    main()
