"""A3.16 lower-bound continuation-contract gate over aligned A3.11 outputs.

Unlike A3.14's ``max_new_tokens`` upper bound, each workload supplies an
externally declared lower bound on remaining decode model calls.  The gate may
use only that declaration: below a selected contract threshold it remains Full
KV; otherwise it reuses one fixed A3.11 admission policy.  Observed trace
length is used only afterwards to audit whether the declared contract held.
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
from tools.simulate_kvzap_route_a314_request_cap_gate import HARDWARE, hardware_key, load_pair
from tools.simulate_kvzap_route_a3_traffic import sha256


PER_COLUMNS = (
    "workload", "request_id", "lifecycle_dir", "deferred_memory_dir",
    "declared_minimum_continuation_calls", "observed_decode_model_calls",
    "contract_held_by_observed_trace", "required_minimum_continuation_calls",
    "gate_path", "deferred_decode_steps", "admission_flush_token_budget",
    *HARDWARE, "net_bytes_saved_fraction", "net_cycle_proxy_saved_fraction",
    "interpretation",
)
CROSS_COLUMNS = (
    "required_minimum_continuation_calls", "deferred_decode_steps",
    "admission_flush_token_budget", *HARDWARE, "workload_count",
    "all_declared_contracts_held_by_observed_trace", "all_workloads_nonnegative_cycle",
    "all_workloads_positive_cycle", "min_net_bytes_saved_fraction",
    "mean_net_bytes_saved_fraction", "min_net_cycle_proxy_saved_fraction",
    "mean_net_cycle_proxy_saved_fraction", "worst_cycle_workload",
)
AUDIT_COLUMNS = (
    "workload", "request_id", "declared_minimum_continuation_calls",
    "observed_decode_model_calls", "contract_held_by_observed_trace",
    "contract_scope",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3.16 lower-bound continuation-contract admission-gate DSE; never loads a model.")
    parser.add_argument("--lifecycle-dir", type=Path, action="append", required=True, help="Validated A2 lifecycle; repeat once per workload.")
    parser.add_argument("--deferred-memory-dir", type=Path, action="append", required=True, help="Aligned A3.11 directory; repeat once per workload.")
    parser.add_argument("--workload-label", action="append", required=True, help="Unique label paired with input directories.")
    parser.add_argument("--declared-minimum-continuation-calls", type=int, action="append", required=True, help="External lower-bound contract paired with each workload; never inferred from the trace.")
    parser.add_argument("--required-minimum-continuation-calls", nargs="+", type=int, required=True, help="Gate activates only when declared lower bound is at least this threshold.")
    parser.add_argument("--active-deferred-decode-steps", type=int, default=5)
    parser.add_argument("--active-admission-flush-token-budget", type=int, default=512)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args(argv)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def observed_calls(lifecycle: dict[str, Any]) -> int:
    value = lifecycle.get("decode_lifecycle_observation", {}).get("decode_model_call_count")
    if not isinstance(value, int) or value < 0:
        raise ValueError("A3.16 lifecycle lacks a valid observed decode_model_call_count")
    return value


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    lengths = (len(args.lifecycle_dir), len(args.deferred_memory_dir), len(args.workload_label), len(args.declared_minimum_continuation_calls))
    if len(set(lengths)) != 1 or lengths[0] < 2 or len(set(args.workload_label)) != len(args.workload_label):
        raise ValueError("supply at least two unique, ordered lifecycle/memory/label/contract quadruples")
    if any(value < 0 for value in args.declared_minimum_continuation_calls):
        raise ValueError("declared minimum continuation calls must be non-negative")
    if not args.required_minimum_continuation_calls or min(args.required_minimum_continuation_calls) < 0 or len(set(args.required_minimum_continuation_calls)) != len(args.required_minimum_continuation_calls):
        raise ValueError("required continuation thresholds must be unique non-negative integers")

    selected_inputs: list[dict[str, Any]] = []
    expected_hardware: set[tuple[str, ...]] | None = None
    provenance: dict[str, Any] = {}
    audit: list[dict[str, Any]] = []
    for label, life_dir, memory_dir, declared in zip(args.workload_label, args.lifecycle_dir, args.deferred_memory_dir, args.declared_minimum_continuation_calls, strict=True):
        lifecycle, _memory, rows = load_pair(life_dir, memory_dir)
        selected = [row for row in rows if int(row["deferred_decode_steps"]) == args.active_deferred_decode_steps and int(row["admission_flush_token_budget"]) == args.active_admission_flush_token_budget]
        by_hardware = {hardware_key(row): row for row in selected}
        if not by_hardware or len(by_hardware) != len(selected):
            raise ValueError(f"A3.11 active policy is missing or duplicated for workload {label}")
        if expected_hardware is None:
            expected_hardware = set(by_hardware)
        elif set(by_hardware) != expected_hardware:
            raise ValueError(f"A3.11 hardware points disagree for workload {label}")
        observed = observed_calls(lifecycle)
        held = declared <= observed
        audit.append({"workload": label, "request_id": lifecycle["request_id"], "declared_minimum_continuation_calls": declared, "observed_decode_model_calls": observed, "contract_held_by_observed_trace": held, "contract_scope": "Trace is used only to audit this externally supplied lower-bound declaration; it is not a gate input."})
        provenance[label] = {"lifecycle_dir": str(life_dir), "deferred_memory_dir": str(memory_dir), "request_id": lifecycle["request_id"], "declared_minimum_continuation_calls": declared, "observed_decode_model_calls": observed, "lifecycle_manifest_sha256": sha256(life_dir / "lifecycle_manifest.json"), "memory_manifest_sha256": sha256(memory_dir / "deferred_memory_system_manifest.json"), "memory_summary_sha256": sha256(memory_dir / "deferred_memory_system_summary.csv")}
        selected_inputs.append({"label": label, "lifecycle_dir": life_dir, "memory_dir": memory_dir, "lifecycle": lifecycle, "declared": declared, "observed": observed, "held": held, "by_hardware": by_hardware})

    per: list[dict[str, Any]] = []
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for required in args.required_minimum_continuation_calls:
        for item in selected_inputs:
            protected = item["declared"] < required
            for hardware, source in sorted(item["by_hardware"].items()):
                row = {"workload": item["label"], "request_id": item["lifecycle"]["request_id"], "lifecycle_dir": str(item["lifecycle_dir"]), "deferred_memory_dir": str(item["memory_dir"]), "declared_minimum_continuation_calls": item["declared"], "observed_decode_model_calls": item["observed"], "contract_held_by_observed_trace": item["held"], "required_minimum_continuation_calls": required, "gate_path": "full_kv_no_admission" if protected else "active_deferred_admission", "deferred_decode_steps": args.active_deferred_decode_steps, "admission_flush_token_budget": args.active_admission_flush_token_budget, **dict(zip(HARDWARE, hardware)), "net_bytes_saved_fraction": 0.0 if protected else float(source["net_bytes_saved_fraction"]), "net_cycle_proxy_saved_fraction": 0.0 if protected else float(source["net_cycle_proxy_saved_fraction"]), "interpretation": "Gate uses only an external lower-bound continuation contract. Observed decode length is audit-only; a contract breach invalidates deployment interpretation for that workload."}
                per.append(row); grouped[(required, *hardware)].append(row)

    cross: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items()):
        required, *hardware = key
        if len(rows) != len(selected_inputs):
            raise AssertionError("missing workload at continuation-contract point")
        bytes_ = [float(row["net_bytes_saved_fraction"]) for row in rows]
        cycles = [float(row["net_cycle_proxy_saved_fraction"]) for row in rows]
        worst = min(range(len(rows)), key=lambda index: cycles[index])
        cross.append({"required_minimum_continuation_calls": required, "deferred_decode_steps": args.active_deferred_decode_steps, "admission_flush_token_budget": args.active_admission_flush_token_budget, **dict(zip(HARDWARE, hardware)), "workload_count": len(rows), "all_declared_contracts_held_by_observed_trace": all(bool(row["contract_held_by_observed_trace"]) for row in rows), "all_workloads_nonnegative_cycle": all(value >= 0 for value in cycles), "all_workloads_positive_cycle": all(value > 0 for value in cycles), "min_net_bytes_saved_fraction": min(bytes_), "mean_net_bytes_saved_fraction": mean(bytes_), "min_net_cycle_proxy_saved_fraction": min(cycles), "mean_net_cycle_proxy_saved_fraction": mean(cycles), "worst_cycle_workload": rows[worst]["workload"]})
    return per, cross, audit, provenance


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    per, cross, audit, provenance = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "continuation_contract_gate_per_workload.csv", per, PER_COLUMNS)
    write_csv(args.output_dir / "continuation_contract_gate_cross_summary.csv", cross, CROSS_COLUMNS)
    write_csv(args.output_dir / "continuation_contract_audit.csv", audit, AUDIT_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a316-continuation-contract-gate-1.0", "git_commit": get_git_commit(), "workloads": provenance, "assumptions": {"required_minimum_continuation_calls": args.required_minimum_continuation_calls, "active_deferred_decode_steps": args.active_deferred_decode_steps, "active_admission_flush_token_budget": args.active_admission_flush_token_budget, "selection_features": ["externally declared minimum continuation calls only"], "protected_semantic": "Full KV with zero admission"}, "boundaries": ["Declared minimum continuation calls are an API/higher-level scheduler contract, not a value predicted from this trace.", "Observed decode length is used only to audit whether a supplied contract held; it is never used to select a gate path.", "This is an offline composition of A3.11 modeled results, not an online controller, HBM/DRAM measurement, latency/throughput result, sparse-attention execution, or generation result."]}
    (args.output_dir / "continuation_contract_gate_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3.16 evaluated {len(provenance)} workloads and {len(cross)} continuation-contract/hardware points: {args.output_dir}")


if __name__ == "__main__":
    main()
