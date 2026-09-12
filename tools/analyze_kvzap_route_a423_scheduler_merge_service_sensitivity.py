"""A4.2.3 modeled fan-in/service sensitivity; it has no hardware timing claim."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


A423_SCHEMA = "kvzap-route-a423-scheduler-merge-service-sensitivity-1.0"
A4168_SCHEMA = "kvzap-route-a4168-cross-horizon-accounting-report-1.0"
A422_SCHEMA = "kvzap-route-a422-scheduler-merge-placement-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.2.3 modeled Route-A source/reduction service sensitivity; no model execution or hardware timing.")
    parser.add_argument("--cross-horizon-accounting", type=Path, required=True)
    parser.add_argument("--placement-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def load_complete(path: Path, schema: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != schema or payload.get("status") != "complete":
        raise ValueError(f"not a completed {schema} artifact: {path}")
    return payload


def require_true(payload: dict[str, Any], names: tuple[str, ...], label: str) -> None:
    missing = [name for name in names if payload.get("observational_guards", {}).get(name) is not True]
    if missing:
        raise ValueError(f"{label} lacks required guards: {missing}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fan_in_bounds(*, merge_calls: int, packed_partials: int, pending_partials: int) -> dict[str, dict[str, int]]:
    """Bounds from marginal packed/pending activity; hot is required on every merge."""
    if not all(isinstance(value, int) and value >= 0 for value in (merge_calls, packed_partials, pending_partials)) or merge_calls <= 0:
        raise ValueError("fan-in counts must be non-negative with positive merge calls")
    if packed_partials > merge_calls or pending_partials > merge_calls:
        raise ValueError("source partial count exceeds merge count")
    three_min = max(0, packed_partials + pending_partials - merge_calls)
    three_max = min(packed_partials, pending_partials)

    def counts(three: int) -> dict[str, int]:
        two = packed_partials + pending_partials - 2 * three
        one = merge_calls - packed_partials - pending_partials + three
        if min(one, two, three) < 0 or one + two + three != merge_calls:
            raise AssertionError("invalid fan-in decomposition")
        return {"one_active_source": one, "two_active_sources": two, "three_active_sources": three}

    return {"minimum_three_source_overlap": counts(three_min), "maximum_three_source_overlap": counts(three_max)}


def capacity_exceeding_evaluations(counts: dict[str, int], capacity: int) -> int:
    if capacity not in (1, 2, 3):
        raise ValueError("modeled state capacity must be 1, 2, or 3")
    fan_in = {"one_active_source": 1, "two_active_sources": 2, "three_active_sources": 3}
    return sum(value for name, value in counts.items() if fan_in[name] > capacity)


def state_waves(counts: dict[str, int], capacity: int) -> int:
    fan_in = {"one_active_source": 1, "two_active_sources": 2, "three_active_sources": 3}
    return sum(math.ceil(fan_in[name] / capacity) * value for name, value in counts.items())


def horizon_counts(horizon: dict[str, Any]) -> tuple[int, int, int, int]:
    merges = horizon.get("merge_calls")
    rows = {row.get("source"): row for row in horizon.get("source_rows", [])}
    if set(rows) != {"hot", "pending", "packed"}:
        raise ValueError("horizon must contain exactly hot/pending/packed rows")
    if not isinstance(merges, int) or merges <= 0:
        raise ValueError("horizon lacks positive merge calls")
    partials = {}
    for source, row in rows.items():
        partial, skipped, decisions = row.get("partial_attention_calls"), row.get("empty_source_skip_calls"), row.get("source_decisions")
        if not all(isinstance(value, int) and value >= 0 for value in (partial, skipped, decisions)) or decisions != merges or partial + skipped != merges:
            raise ValueError(f"{source} source decision conservation fails")
        partials[source] = partial
    if partials["hot"] != merges:
        raise ValueError("A4.2.3 requires hot source partial on every merge")
    return merges, partials["hot"], partials["packed"], partials["pending"]


def build_rows(*, label: str, horizon: dict[str, Any], schedulers: list[str]) -> list[dict[str, Any]]:
    merges, hot, packed, pending = horizon_counts(horizon)
    bounds = fan_in_bounds(merge_calls=merges, packed_partials=packed, pending_partials=pending)
    active = hot + packed + pending
    rows: list[dict[str, Any]] = []
    for scheduler in schedulers:
        for source_work in (1.0, 4.0):
            for merge_work in (1.0, 4.0):
                co = active * source_work + merges * merge_work
                for transfer_work in (0.0, 1.0, 4.0):
                    for reduction_dispatch_work in (0.0, 1.0, 4.0):
                        for capacity in (1, 2, 3):
                            for overlap, counts in bounds.items():
                                waves = state_waves(counts, capacity)
                                split = merges * (source_work + reduction_dispatch_work + merge_work) + waves * transfer_work
                                rows.append({
                                    "horizon": label,
                                    "scheduler_label_from_a422": scheduler,
                                    "marginal_source_partial_counts": {"hot": hot, "packed": packed, "pending": pending},
                                    "merge_decisions": merges,
                                    "fan_in_overlap_case": overlap,
                                    "fan_in_evaluation_count_bounds": counts,
                                    "modeled_state_capacity_per_logical_evaluation": capacity,
                                    "modeled_source_service_work_units_per_active_source": source_work,
                                    "modeled_merge_work_units_per_evaluation": merge_work,
                                    "modeled_partial_state_transfer_work_units_per_wave": transfer_work,
                                    "modeled_reduction_dispatch_work_units_per_evaluation": reduction_dispatch_work,
                                    "co_located_serial_service_work_units": co,
                                    "split_source_barrier_service_work_units": split,
                                    "split_minus_co_located_service_work_units": split - co,
                                    "split_state_transfer_waves": waves,
                                    "evaluations_exceeding_modeled_state_capacity": capacity_exceeding_evaluations(counts, capacity),
                                    "interpretation": "Both values are abstract modeled service-work sums over independent logical evaluations, not latency. The fan-in case is a bound from marginal source activity, not a recovered execution timeline or queue trace.",
                                })
    return rows


def build_report(*, accounting: dict[str, Any], placement: dict[str, Any]) -> dict[str, Any]:
    scope = placement.get("report", {}).get("scope", {})
    required = {"threshold": -4.0, "hot_window_tokens": 128, "page_tokens": 64, "admission_budget_retained_tokens_per_layer_call": 512}
    if any(scope.get(key) != value for key, value in required.items()):
        raise ValueError("A422 scope differs from the required Route-A policy point")
    axes = placement.get("report", {}).get("sensitivity_axes", {}).get("from_a4201", {})
    schedulers = axes.get("scheduler_labels")
    if not isinstance(schedulers, list) or not schedulers or not all(isinstance(item, str) and item for item in schedulers):
        raise ValueError("A422 lacks scheduler labels")
    horizons = {row.get("label"): row for row in accounting.get("report", {}).get("horizons", [])}
    if set(horizons) != {"h16", "h32"}:
        raise ValueError("A4168 must provide exactly h16 and h32 horizons")
    rows = [row for label in ("h16", "h32") for row in build_rows(label=label, horizon=horizons[label], schedulers=schedulers)]
    return {
        "evidence_classification": {"a4168": "profiler-derived Python-reference marginal source accounting", "a422": "modeled placement interface contract", "this_study": "modeled fan-in/service sensitivity"},
        "scope": scope,
        "method": {"hot_source_requirement": "hot partial is present for every logical merge in both accepted horizons", "fan_in_bound_method": "Only packed/pending overlap is unknown. Inclusion-exclusion bounds its 3-source overlap, then derive 1/2/3-active-source evaluation counts.", "service_model": "Co-located serializes active source service plus local merge. Split-source parallelizes source service per logical evaluation, then pays declared transfer waves, reduction dispatch, and merge. These are abstract work models, not a timing simulator."},
        "sensitivity_axes": {"source_service_work_units_per_active_source": [1.0, 4.0], "merge_work_units_per_evaluation": [1.0, 4.0], "partial_state_transfer_work_units_per_wave": [0.0, 1.0, 4.0], "reduction_dispatch_work_units_per_evaluation": [0.0, 1.0, 4.0], "state_capacity_per_logical_evaluation": [1, 2, 3], "scheduler_labels_from_a422": schedulers},
        "rows": rows,
        "guards": {"a4168_source_decision_conservation": True, "a422_policy_scope_verified": True, "hot_partial_per_merge_verified": True, "fan_in_bounds_derived_only_from_marginals": True, "no_service_timeline_inferred": True},
        "boundaries": ["This is a modeled sensitivity study. It executes no model and does not add functional, trace-derived, measured, or calibrated hardware performance evidence.", "The derived fan-in bounds do not recover per-layer/head execution order, source completion times, reduction arrival times, queue occupancy, or FIFO depth.", "Abstract service-work values are not cycles or latency, and state capacity per logical evaluation is not a physical FIFO or reducer count.", "No result is HBM traffic, throughput, energy, area, frequency, hardware acceleration, final scheduler choice, or RTL readiness."],
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    accounting = load_complete(args.cross_horizon_accounting, A4168_SCHEMA)
    placement = load_complete(args.placement_report, A422_SCHEMA)
    require_true(accounting, ("input_artifacts_complete", "source_partial_skip_merge_accounting_validated_per_horizon", "no_model_execution"), "A4168")
    require_true(placement, ("a4168_accounting_verified", "input_hashes_recorded", "source_merge_conservation_verified", "co_located_and_split_interfaces_explicit", "no_model_execution"), "A422")
    if placement.get("config", {}).get("cross_horizon_accounting_sha256") != digest(args.cross_horizon_accounting):
        raise ValueError("A422 is not bound to the supplied A4168 accounting")
    report = build_report(accounting=accounting, placement=placement)
    config = {"cross_horizon_accounting": str(args.cross_horizon_accounting), "placement_report": str(args.placement_report), "cross_horizon_accounting_sha256": digest(args.cross_horizon_accounting), "placement_report_sha256": digest(args.placement_report)}
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a423_scheduler_merge_service_sensitivity_report.json"
    manifest = {"schema_version": A423_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "report": report, "observational_guards": {"a4168_accounting_verified": True, "a422_placement_contract_verified": True, "input_hashes_recorded": True, "marginal_fan_in_bounds_conserved": True, "no_service_timeline_inferred": True, "no_hardware_parameter_selected": True, "no_model_execution": True}, "boundaries": report["boundaries"]}
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.2.3 modeled scheduler/merge service sensitivity completed: {output}")


if __name__ == "__main__":
    main()
