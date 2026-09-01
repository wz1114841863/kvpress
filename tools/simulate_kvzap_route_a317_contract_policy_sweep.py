"""A3.17 aligned continuation-contract, defer, and admission-budget sweep.

This is the multi-policy extension of A3.16.  Gate selection uses an external
lower-bound continuation declaration and a selected policy only; observed
decode length remains an audit field.  All supplied workloads must expose the
same selected A3.11 policy and hardware points.
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
    "workload", "request_id", "declared_minimum_continuation_calls", "observed_decode_model_calls", "contract_held_by_observed_trace", "required_minimum_continuation_calls", "gate_path", "deferred_decode_steps", "admission_flush_token_budget", *HARDWARE, "net_bytes_saved_fraction", "net_cycle_proxy_saved_fraction", "interpretation",
)
CROSS_COLUMNS = (
    "required_minimum_continuation_calls", "deferred_decode_steps", "admission_flush_token_budget", *HARDWARE, "workload_count", "active_workload_count", "all_declared_contracts_held_by_observed_trace", "all_workloads_nonnegative_cycle", "all_active_workloads_positive_cycle", "min_net_bytes_saved_fraction", "mean_net_bytes_saved_fraction", "min_net_cycle_proxy_saved_fraction", "mean_net_cycle_proxy_saved_fraction", "min_active_net_cycle_proxy_saved_fraction", "mean_active_net_cycle_proxy_saved_fraction", "worst_cycle_workload",
)
AUDIT_COLUMNS = ("workload", "request_id", "declared_minimum_continuation_calls", "observed_decode_model_calls", "contract_held_by_observed_trace", "contract_scope")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3.17 continuation-contract/policy sweep over aligned A3.11 results; never loads a model.")
    parser.add_argument("--lifecycle-dir", type=Path, action="append", required=True)
    parser.add_argument("--deferred-memory-dir", type=Path, action="append", required=True)
    parser.add_argument("--workload-label", action="append", required=True)
    parser.add_argument("--declared-minimum-continuation-calls", type=int, action="append", required=True, help="External lower-bound contract paired with each workload; never inferred from trace length.")
    parser.add_argument("--required-minimum-continuation-calls", nargs="+", type=int, required=True)
    parser.add_argument("--deferred-decode-steps-points", nargs="+", type=int, required=True)
    parser.add_argument("--admission-flush-token-budget-points", nargs="+", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args(argv)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def observed_calls(lifecycle: dict[str, Any]) -> int:
    value = lifecycle.get("decode_lifecycle_observation", {}).get("decode_model_call_count")
    if not isinstance(value, int) or value < 0:
        raise ValueError("A3.17 lifecycle lacks valid decode_model_call_count")
    return value


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    counts = (len(args.lifecycle_dir), len(args.deferred_memory_dir), len(args.workload_label), len(args.declared_minimum_continuation_calls))
    if len(set(counts)) != 1 or counts[0] < 2 or len(set(args.workload_label)) != counts[0]:
        raise ValueError("supply at least two unique, ordered lifecycle/memory/label/contract quadruples")
    if any(value < 0 for value in (*args.declared_minimum_continuation_calls, *args.required_minimum_continuation_calls, *args.deferred_decode_steps_points, *args.admission_flush_token_budget_points)):
        raise ValueError("all contract and policy points must be non-negative")
    if not args.required_minimum_continuation_calls or len(set(args.required_minimum_continuation_calls)) != len(args.required_minimum_continuation_calls):
        raise ValueError("continuation thresholds must be unique")
    policies = [(defer, budget) for defer in args.deferred_decode_steps_points for budget in args.admission_flush_token_budget_points]
    if len(set(policies)) != len(policies):
        raise ValueError("policy points must be unique")

    inputs: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {}
    for label, life_dir, memory_dir, declared in zip(args.workload_label, args.lifecycle_dir, args.deferred_memory_dir, args.declared_minimum_continuation_calls, strict=True):
        lifecycle, _memory, rows = load_pair(life_dir, memory_dir)
        by_policy: dict[tuple[int, int], dict[tuple[str, ...], dict[str, str]]] = {}
        for policy in policies:
            selected = [row for row in rows if int(row["deferred_decode_steps"]) == policy[0] and int(row["admission_flush_token_budget"]) == policy[1]]
            by_hardware = {hardware_key(row): row for row in selected}
            if not by_hardware or len(by_hardware) != len(selected):
                raise ValueError(f"A3.11 policy {policy} is missing or duplicated for workload {label}")
            by_policy[policy] = by_hardware
        observed = observed_calls(lifecycle); held = declared <= observed
        inputs.append({"label": label, "lifecycle": lifecycle, "declared": declared, "observed": observed, "held": held, "by_policy": by_policy})
        audit.append({"workload": label, "request_id": lifecycle["request_id"], "declared_minimum_continuation_calls": declared, "observed_decode_model_calls": observed, "contract_held_by_observed_trace": held, "contract_scope": "Observed trace horizon audits an external declaration only; it is not a gate feature."})
        provenance[label] = {"lifecycle_dir": str(life_dir), "deferred_memory_dir": str(memory_dir), "request_id": lifecycle["request_id"], "declared_minimum_continuation_calls": declared, "observed_decode_model_calls": observed, "lifecycle_manifest_sha256": sha256(life_dir / "lifecycle_manifest.json"), "memory_manifest_sha256": sha256(memory_dir / "deferred_memory_system_manifest.json"), "memory_summary_sha256": sha256(memory_dir / "deferred_memory_system_summary.csv")}

    per: list[dict[str, Any]] = []; grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for policy in policies:
        hardware_sets = [set(item["by_policy"][policy]) for item in inputs]
        if any(points != hardware_sets[0] for points in hardware_sets[1:]):
            raise ValueError(f"A3.11 hardware points disagree across workloads for policy {policy}")
        for threshold in args.required_minimum_continuation_calls:
            for item in inputs:
                protected = item["declared"] < threshold
                for hardware, source in sorted(item["by_policy"][policy].items()):
                    row = {"workload": item["label"], "request_id": item["lifecycle"]["request_id"], "declared_minimum_continuation_calls": item["declared"], "observed_decode_model_calls": item["observed"], "contract_held_by_observed_trace": item["held"], "required_minimum_continuation_calls": threshold, "gate_path": "full_kv_no_admission" if protected else "active_deferred_admission", "deferred_decode_steps": policy[0], "admission_flush_token_budget": policy[1], **dict(zip(HARDWARE, hardware)), "net_bytes_saved_fraction": 0.0 if protected else float(source["net_bytes_saved_fraction"]), "net_cycle_proxy_saved_fraction": 0.0 if protected else float(source["net_cycle_proxy_saved_fraction"]), "interpretation": "Selection uses only external lower-bound continuation declaration and fixed policy; observed trace horizon is audit-only."}
                    per.append(row); grouped[(threshold, *policy, *hardware)].append(row)
    cross: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items()):
        threshold, defer, budget, *hardware = key
        if len(rows) != len(inputs): raise AssertionError("missing workload at A3.17 point")
        bytes_ = [float(row["net_bytes_saved_fraction"]) for row in rows]; cycles = [float(row["net_cycle_proxy_saved_fraction"]) for row in rows]
        active = [row for row in rows if row["gate_path"] == "active_deferred_admission"]
        active_cycles = [float(row["net_cycle_proxy_saved_fraction"]) for row in active]
        worst = min(range(len(rows)), key=lambda index: cycles[index])
        cross.append({"required_minimum_continuation_calls": threshold, "deferred_decode_steps": defer, "admission_flush_token_budget": budget, **dict(zip(HARDWARE, hardware)), "workload_count": len(rows), "active_workload_count": len(active), "all_declared_contracts_held_by_observed_trace": all(row["contract_held_by_observed_trace"] for row in rows), "all_workloads_nonnegative_cycle": all(value >= 0 for value in cycles), "all_active_workloads_positive_cycle": bool(active) and all(value > 0 for value in active_cycles), "min_net_bytes_saved_fraction": min(bytes_), "mean_net_bytes_saved_fraction": mean(bytes_), "min_net_cycle_proxy_saved_fraction": min(cycles), "mean_net_cycle_proxy_saved_fraction": mean(cycles), "min_active_net_cycle_proxy_saved_fraction": min(active_cycles) if active_cycles else 0.0, "mean_active_net_cycle_proxy_saved_fraction": mean(active_cycles) if active_cycles else 0.0, "worst_cycle_workload": rows[worst]["workload"]})
    return per, cross, audit, provenance


def main() -> None:
    args = parse_args()
    if args.output_dir.exists(): raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    per, cross, audit, provenance = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "contract_policy_sweep_per_workload.csv", per, PER_COLUMNS)
    write_csv(args.output_dir / "contract_policy_sweep_cross_summary.csv", cross, CROSS_COLUMNS)
    write_csv(args.output_dir / "continuation_contract_audit.csv", audit, AUDIT_COLUMNS)
    manifest = {"schema_version": "kvzap-route-a317-contract-policy-sweep-1.0", "git_commit": get_git_commit(), "workloads": provenance, "assumptions": {"required_minimum_continuation_calls": args.required_minimum_continuation_calls, "deferred_decode_steps_points": args.deferred_decode_steps_points, "admission_flush_token_budget_points": args.admission_flush_token_budget_points, "selection_features": ["externally declared minimum continuation calls only"], "protected_semantic": "Full KV with zero admission"}, "boundaries": ["This is an offline composition of aligned A3.11 modeled results.", "Observed trace decode length audits an external contract but never selects the gate.", "No result is an online-controller implementation, sparse-attention execution, HBM/DRAM measurement, allocator measurement, latency, or throughput result."]}
    (args.output_dir / "contract_policy_sweep_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    policy_count = len(args.deferred_decode_steps_points) * len(args.admission_flush_token_budget_points)
    print(f"Route-A3.17 evaluated {len(provenance)} workloads, {policy_count} policies, and {len(cross)} threshold/policy/hardware points: {args.output_dir}")


if __name__ == "__main__": main()
