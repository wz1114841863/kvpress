#!/usr/bin/env python3
"""A4.3.3 conditional, untimed admission/staging envelope from A4.3.2 traces."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a432_policy_lifecycle_transition_envelope import PRESETS, load_events, load_manifest, sha256
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a433-conditional-admission-staging-envelope-1.0"
DEFAULT_SERVICE_QUANTA = (1, 2, 4, 8, 16, 32, 64, 128)
DEFAULT_STAGING_CAPACITIES = (64, 128, 256, 512, 1024, 2048, 4096, 8192)


def event_arrivals(event: dict[str, Any]) -> int:
    return sum(int(row["matured_kept_tokens"]) for row in event["heads"])


def event_reference_pending(event: dict[str, Any]) -> int:
    return sum(int(row["pending_tokens_after_service"]) for row in event["heads"])


def by_layer(events: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[int(event["layer"])].append(event)
    for layer in grouped:
        grouped[layer].sort(key=lambda event: int(event["start_position"]))
    return dict(sorted(grouped.items()))


def simulate_layer(events: list[dict[str, Any]], service_quantum: int) -> list[dict[str, int | str]]:
    """Replay one layer's scalar pending recurrence under a declared quantum.

    A quantum is a count allowed after each logical append; it has no time or
    controller-rate meaning. It cannot infer page sealing or per-head depth.
    """
    if service_quantum <= 0:
        raise ValueError("service quantum must be positive")
    pending = 0
    rows: list[dict[str, int | str]] = []
    for event in events:
        arrivals = event_arrivals(event)
        before_service = pending + arrivals
        serviced = min(service_quantum, before_service)
        pending = before_service - serviced
        rows.append({"phase": str(event["phase"]), "start_position": int(event["start_position"]), "end_position": int(event["end_position"]), "matured_kept_head_tokens": arrivals, "pending_before_service_head_tokens": before_service, "conditional_service_head_tokens": serviced, "pending_after_service_head_tokens": pending, "reference_pending_after_service_head_tokens": event_reference_pending(event)})
    return rows


def verify_budget_one_reproduction(events: list[dict[str, Any]]) -> dict[str, Any]:
    mismatches = []
    for layer, layer_events in by_layer(events).items():
        for row in simulate_layer(layer_events, 1):
            if row["pending_after_service_head_tokens"] != row["reference_pending_after_service_head_tokens"]:
                mismatches.append({"layer": layer, "start_position": row["start_position"], "simulated": row["pending_after_service_head_tokens"], "reference": row["reference_pending_after_service_head_tokens"]})
    if mismatches:
        raise AssertionError(f"budget-one scalar recurrence differs from A4.3.2 reference state: {mismatches[:4]}")
    return {"passed": True, "checked_layer_append_count": len(events), "interpretation": "Exact aggregate head-token recurrence reproduction for the declared A4.3.2 budget-one append action; not a timing or FIFO validation."}


def conditional_quantum_summary(events: list[dict[str, Any]], service_quantum: int, capacities: tuple[int, ...]) -> dict[str, Any]:
    per_layer, all_rows = [], []
    for layer, layer_events in by_layer(events).items():
        rows = simulate_layer(layer_events, service_quantum)
        all_rows.extend(rows)
        per_layer.append({"layer": layer, "peak_pending_head_tokens": max(int(row["pending_after_service_head_tokens"]) for row in rows), "terminal_pending_head_tokens": int(rows[-1]["pending_after_service_head_tokens"]), "append_count": len(rows)})
    peak = max(int(row["pending_after_service_head_tokens"]) for row in all_rows)
    capacity_rows = []
    for capacity in capacities:
        excesses = [max(0, int(row["pending_after_service_head_tokens"]) - capacity) for row in all_rows]
        capacity_rows.append({"conditional_staging_capacity_head_tokens": capacity, "no_breach_on_this_trace": not any(excesses), "conditional_breach_layer_append_count": sum(excess > 0 for excess in excesses), "maximum_conditional_excess_head_tokens": max(excesses), "sum_conditional_excess_head_tokens": sum(excesses), "interpretation": "Counterfactual capacity comparison with no eviction or timing model; excess is not observed FIFO overflow."})
    return {"conditional_service_quantum_head_tokens_per_logical_append": service_quantum, "required_conditional_staging_capacity_head_tokens_no_breach": peak, "per_layer": per_layer, "capacity_rows": capacity_rows, "boundaries": ["Service quantum is an untimed count applied after each recorded layer-local append.", "The scalar aggregate recurrence does not assign admissions to KV heads and cannot infer page sealing, PTE behavior, bank conflicts, or per-head queue depth."]}


def positive_unique(values: list[int], *, name: str) -> tuple[int, ...]:
    if not values or any(value <= 0 for value in values) or len(set(values)) != len(values):
        raise ValueError(f"{name} must contain unique positive integers")
    return tuple(values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.3.3 conditional untimed Route-A admission/staging envelope; no FIFO, timing, or hardware-capacity claim.")
    parser.add_argument("--policy-manifest", action="append", type=Path, required=True, help="Exactly three A4.3.2 retrieval/summarization/reasoning manifests.")
    parser.add_argument("--service-quantum", type=int, nargs="+", default=list(DEFAULT_SERVICE_QUANTA), help="Untimed head-token service counts per recorded layer append; must include 1.")
    parser.add_argument("--staging-capacity", type=int, nargs="+", default=list(DEFAULT_STAGING_CAPACITIES), help="Conditional aggregate pending capacities in head-token entries.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    quanta = positive_unique(args.service_quantum, name="--service-quantum")
    capacities = positive_unique(args.staging_capacity, name="--staging-capacity")
    if 1 not in quanta:
        raise ValueError("--service-quantum must include 1 for the A4.3.2 reproduction gate")
    if args.output_dir.exists() or len(args.policy_manifest) != 3:
        raise ValueError("A4.3.3 requires exactly three manifests and a new output directory")
    loaded = [(path, load_manifest(path)) for path in args.policy_manifest]
    by_preset = {data["config"]["preset"]: (path, data) for path, data in loaded}
    if set(by_preset) != PRESETS or len(by_preset) != 3:
        raise ValueError("A4.3.3 requires one distinct A4.3.2 manifest per preset")
    reference = loaded[0][1]["config"]
    common = ("model_name", "model_revision", "predictor_name", "predictor_revision", "threshold", "window_size", "page_tokens", "admission_budget", "max_new_tokens", "seed", "target_layers", "target_kv_head", "record_lifecycle_transitions")
    if any(any(data["config"].get(key) != reference.get(key) for key in common) for _, data in loaded[1:]):
        raise ValueError("A4.3.3 source manifests have inconsistent functional inputs")
    workload_rows = []
    for preset in sorted(PRESETS):
        manifest_path, manifest = by_preset[preset]
        events = load_events(manifest_path, manifest["lifecycle_transition_trace"])
        workload_rows.append({"preset": preset, "manifest_path": str(manifest_path), "manifest_sha256": sha256(manifest_path), "lifecycle_trace": manifest["lifecycle_transition_trace"], "budget_one_reproduction": verify_budget_one_reproduction(events), "conditional_quantum_rows": [conditional_quantum_summary(events, quantum, capacities) for quantum in quanta]})
    config = {"policy_manifests": [{"path": str(path), "sha256": sha256(path)} for path in args.policy_manifest], "service_quantum_head_tokens_per_logical_append": list(quanta), "conditional_staging_capacity_head_tokens": list(capacities)}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model conditional scalar replay of A4.3.2 functional/trace-derived lifecycle events; not FIFO occupancy, service timing, or hardware evidence", "shared_functional_reference_inputs": {key: reference[key] for key in common}, "per_workload_rows": workload_rows, "observational_guards": {"three_distinct_workloads_preserved": True, "a432_source_hashes_verified": True, "source_timestamps_absent": True, "budget_one_reproduced_before_counterfactual_sweep": True, "no_fifo_depth_selected": True, "no_hardware_performance_claim": True}, "architecture_spec_gate": {"eligible": False, "rtl_authorized": False, "reason": "Conditional discrete Q/C rows select neither an observed FIFO depth nor a hardware service rate or resource parameter."}, "boundaries": ["Q is an untimed service count after each layer-local logical append, not a per-cycle, per-token, or per-second service rate.", "C is a conditional aggregate pending-state comparison threshold in head-token entries, not a finite FIFO size, SRAM capacity, or overflow observation.", "No admission arrival/completion time, allocator/HBM traffic, latency, throughput, energy, area, page/bank/burst behavior, architecture specification, or RTL conclusion follows."]}
    args.output_dir.mkdir(parents=True)
    report_path = args.output_dir / "a433_conditional_admission_staging_envelope_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.3.3 completed: {report_path}")


if __name__ == "__main__":
    main()
