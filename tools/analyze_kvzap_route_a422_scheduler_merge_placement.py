"""A4.2.2 modeled scheduler/merge placement reconciliation; no model execution."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


A422_SCHEMA = "kvzap-route-a422-scheduler-merge-placement-1.0"
A4168_SCHEMA = "kvzap-route-a4168-cross-horizon-accounting-report-1.0"
A4200_SCHEMA = "kvzap-route-a4200-observed-resource-contract-1.0"
A4201_SCHEMA = "kvzap-route-a4201-contract-sensitivity-matrix-1.0"
SOURCES = ("hot", "pending", "packed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.2.2 modeled Route-A scheduler/merge placement comparison; no model execution or hardware sizing."
    )
    parser.add_argument("--cross-horizon-accounting", type=Path, required=True)
    parser.add_argument("--observed-resource-contract", type=Path, required=True)
    parser.add_argument("--contract-sensitivity-matrix", type=Path, required=True)
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_counts(horizon: dict[str, Any]) -> tuple[int, dict[str, int]]:
    merges = horizon.get("merge_calls")
    if not isinstance(merges, int) or merges <= 0:
        raise ValueError("horizon lacks positive merge_calls")
    rows = {row.get("source"): row for row in horizon.get("source_rows", [])}
    if set(rows) != set(SOURCES):
        raise ValueError("horizon must contain exactly hot, pending, and packed source rows")
    partials: dict[str, int] = {}
    for source in SOURCES:
        row = rows[source]
        partial = row.get("partial_attention_calls")
        skipped = row.get("empty_source_skip_calls")
        decisions = row.get("source_decisions")
        if not all(isinstance(value, int) and value >= 0 for value in (partial, skipped, decisions)):
            raise ValueError(f"{source} source counts must be non-negative integers")
        if decisions != merges or partial + skipped != merges:
            raise ValueError(f"{source} source/merge conservation fails")
        partials[source] = partial
    if sum(partials.values()) != horizon.get("actual_partial_calls"):
        raise ValueError("partial count total differs from actual_partial_calls")
    return merges, partials


def modeled_axes(matrix: dict[str, Any]) -> tuple[list[int], list[float], list[str]]:
    rows = {row.get("parameter"): row for row in matrix.get("report", {}).get("matrix", [])}
    merge = rows.get("merge_state_precision_and_PE_scheduler_interface")
    if merge is None:
        raise ValueError("A4201 lacks merge/scheduler candidate range")
    candidate = merge.get("candidate_modeled_range", {})
    state_bytes = candidate.get("merge_state_bytes_per_head")
    merge_work = candidate.get("merge_cycles_per_head")
    schedulers = candidate.get("schedulers")
    if not (isinstance(state_bytes, list) and isinstance(merge_work, list) and isinstance(schedulers, list)):
        raise ValueError("A4201 merge/scheduler candidate range is malformed")
    if not all(isinstance(value, int) and value > 0 for value in state_bytes):
        raise ValueError("merge state payload points must be positive integer modeled bytes")
    if not all(isinstance(value, (int, float)) and value > 0 for value in merge_work):
        raise ValueError("merge work points must be positive")
    if not all(isinstance(value, str) and value for value in schedulers):
        raise ValueError("scheduler labels must be non-empty")
    return state_bytes, [float(value) for value in merge_work], schedulers


def placement_rows(*, label: str, horizon: dict[str, Any], state_bytes: list[int], merge_work: list[float], schedulers: list[str]) -> list[dict[str, Any]]:
    merges, partials = source_counts(horizon)
    active = sum(partials.values())
    rows: list[dict[str, Any]] = []
    for scheduler in schedulers:
        for state in state_bytes:
            for merge_units in merge_work:
                rows.append({
                    "horizon": label,
                    "organization": "co_located",
                    "scheduler_label_from_a4201": scheduler,
                    "modeled_partial_state_payload_bytes": state,
                    "modeled_merge_work_units_per_merge": merge_units,
                    "merge_decisions": merges,
                    "active_source_partials": active,
                    "source_partial_counts": partials,
                    "local_merge_work_units": merges * merge_units,
                    "cross_engine_partial_state_transfers": 0,
                    "cross_engine_state_payload_bytes": 0,
                    "explicit_reduction_dispatches": 0,
                    "additional_modeled_interface_work_units": 0.0,
                    "modeled_inflight_partial_state_capacity_axis": "not_applicable_local_merge",
                    "interpretation": "One (layer, KV head-group) engine owns source service and the one logical online merge; no cross-engine partial state exists in this organization.",
                })
                for source_dispatch in (0.0, 1.0):
                    for transfer in (0.0, 1.0, 4.0):
                        for reduction_dispatch in (0.0, 1.0):
                            for capacity in (1, 2, 3):
                                added = active * (source_dispatch + transfer) + merges * reduction_dispatch
                                rows.append({
                                    "horizon": label,
                                    "organization": "split_source",
                                    "scheduler_label_from_a4201": scheduler,
                                    "modeled_partial_state_payload_bytes": state,
                                    "modeled_merge_work_units_per_merge": merge_units,
                                    "merge_decisions": merges,
                                    "active_source_partials": active,
                                    "source_partial_counts": partials,
                                    "local_merge_work_units": merges * merge_units,
                                    "cross_engine_partial_state_transfers": active,
                                    "cross_engine_state_payload_bytes": active * state,
                                    "explicit_reduction_dispatches": merges,
                                    "modeled_source_dispatch_work_units_per_active_partial": source_dispatch,
                                    "modeled_partial_state_transfer_work_units_per_active_partial": transfer,
                                    "modeled_reduction_dispatch_work_units_per_merge": reduction_dispatch,
                                    "additional_modeled_interface_work_units": added,
                                    "modeled_inflight_partial_state_capacity_axis": capacity,
                                    "interpretation": "Every non-empty source exports the explicit online-softmax partial state {max, normalization, value accumulator} to a reduction interface. Capacity is a sensitivity label only: event counts have no service timeline and cannot infer queue occupancy or FIFO depth.",
                                })
    return rows


def build_report(*, accounting: dict[str, Any], observed: dict[str, Any], matrix: dict[str, Any]) -> dict[str, Any]:
    scope = observed.get("contract", {}).get("contract_scope", {})
    if (scope.get("threshold"), scope.get("hot_window_tokens"), scope.get("page_tokens"), scope.get("admission_budget_retained_tokens_per_layer_call")) != (-4.0, 128, 64, 512):
        raise ValueError("A4200 scope differs from required A4.2.2 policy point")
    if matrix.get("report", {}).get("contract_scope") != scope:
        raise ValueError("A4201 scope differs from A4200 observed contract")
    horizons = {row.get("label"): row for row in accounting.get("report", {}).get("horizons", [])}
    if set(horizons) != {"h16", "h32"}:
        raise ValueError("A4168 must provide exactly h16 and h32 horizons")
    state_bytes, merge_work, schedulers = modeled_axes(matrix)
    rows = [row for label in ("h16", "h32") for row in placement_rows(label=label, horizon=horizons[label], state_bytes=state_bytes, merge_work=merge_work, schedulers=schedulers)]
    return {
        "evidence_classification": {
            "a4168": "profiler-derived Python-reference source partial/skip/merge accounting",
            "a4200": "observed Python-reference software interface contract",
            "a4201_and_this_study": "modeled candidate sensitivity only",
        },
        "scope": scope,
        "logical_partial_softmax_state_interface": {
            "state_fields": ["partial max", "partial normalization state", "partial value accumulator", "valid/empty outcome"],
            "source_order": list(SOURCES),
            "merge_rule": "Exactly one numerically stable online-softmax merge follows the three source decisions per attention evaluation.",
        },
        "organizations": {
            "co_located": "One engine owns hot, pending, packed source service and merge for a (layer, KV head-group); it preserves A3-edge no-cross-engine merge placement.",
            "split_source": "Non-empty sources may service independently. Each exports the explicit partial-softmax state to a reduction interface; state payload, transfer/dispatch work, and an in-flight-state capacity axis are shown explicitly.",
        },
        "sensitivity_axes": {
            "from_a4201": {"modeled_partial_state_payload_bytes": state_bytes, "modeled_merge_work_units_per_merge": merge_work, "scheduler_labels": schedulers},
            "new_explicit_split_interface_axes": {"source_dispatch_work_units_per_active_partial": [0.0, 1.0], "partial_state_transfer_work_units_per_active_partial": [0.0, 1.0, 4.0], "reduction_dispatch_work_units_per_merge": [0.0, 1.0], "inflight_partial_state_capacity_axis": [1, 2, 3]},
            "axis_boundary": "The new axes are abstract modeled interface work/capacity labels, not cycles, queues, FIFO depths, PE counts, controller timing, or hardware calibration.",
        },
        "rows": rows,
        "guards": {"horizon_source_merge_conservation": True, "a4200_a4201_scope_equal": True, "co_located_has_no_cross_engine_state_transfer": True, "split_source_exports_one_state_per_active_partial": True, "one_logical_merge_per_attention_evaluation_preserved": True},
        "boundaries": [
            "This is a modeled contract study. It executes no model and does not add functional, trace-derived, or measured performance evidence.",
            "A4168 Python-reference accounting counts are not hardware operations, HBM traffic, latency, throughput, energy, area, frequency, or acceleration evidence.",
            "Modeled interface work units and state payload bytes do not select a FIFO depth, PTE layout, bank/burst map, merge precision, PE count, scheduler, controller timing, or RTL implementation.",
            "The in-flight capacity axis cannot establish queue occupancy because the input lacks source/reduction service timing; it is retained solely as an explicit unresolved interface sensitivity.",
            "Full-KV bypass and same-mask dense KVzap remain distinct controls and are not assigned a placement-performance conclusion here.",
        ],
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    accounting = load_complete(args.cross_horizon_accounting, A4168_SCHEMA)
    observed = load_complete(args.observed_resource_contract, A4200_SCHEMA)
    matrix = load_complete(args.contract_sensitivity_matrix, A4201_SCHEMA)
    require_true(accounting, ("input_artifacts_complete", "source_partial_skip_merge_accounting_validated_per_horizon", "page_tail_coverage_validated_per_horizon", "profiler_ranges_not_aggregated_as_latency", "no_model_execution"), "A4168")
    require_true(observed, ("a4168_cross_horizon_accounting_verified", "all_layer_all_head_external_storage_semantics_verified", "native_cold_absence_verified", "unresolved_hardware_parameters_explicit", "no_model_execution"), "A4200")
    require_true(matrix, ("a4200_observed_contract_verified", "all_unresolved_contract_parameters_mapped", "no_hardware_parameter_selected", "no_model_execution"), "A4201")
    report = build_report(accounting=accounting, observed=observed, matrix=matrix)
    config = {"cross_horizon_accounting": str(args.cross_horizon_accounting), "observed_resource_contract": str(args.observed_resource_contract), "contract_sensitivity_matrix": str(args.contract_sensitivity_matrix), "cross_horizon_accounting_sha256": sha256(args.cross_horizon_accounting), "observed_resource_contract_sha256": sha256(args.observed_resource_contract), "contract_sensitivity_matrix_sha256": sha256(args.contract_sensitivity_matrix)}
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a422_scheduler_merge_placement_report.json"
    manifest = {"schema_version": A422_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "report": report, "observational_guards": {"a4168_accounting_verified": True, "a4200_observed_contract_verified": True, "a4201_modeled_range_verified": True, "input_hashes_recorded": True, "source_merge_conservation_verified": True, "co_located_and_split_interfaces_explicit": True, "no_hardware_parameter_selected": True, "no_model_execution": True}, "boundaries": report["boundaries"]}
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.2.2 modeled scheduler/merge placement report completed: {output}")


if __name__ == "__main__":
    main()
