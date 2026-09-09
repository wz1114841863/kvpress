"""A4.2.1 bind observed Route-A interfaces to explicit A3 sensitivity ranges."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


A4201_SCHEMA = "kvzap-route-a4201-contract-sensitivity-matrix-1.0"
A4200_SCHEMA = "kvzap-route-a4200-observed-resource-contract-1.0"
A36_SCHEMA = "kvzap-route-a36-hybrid-activation-dse-1.1"
A3_EDGE_SCHEMA = "kvzap-route-a3-edge-dse-1.1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.2.1 offline Route-A contract sensitivity matrix; no model execution and no hardware sizing claim.")
    parser.add_argument("--observed-resource-contract", type=Path, required=True)
    parser.add_argument("--hybrid-sensitivity-manifest", type=Path, required=True)
    parser.add_argument("--edge-dse-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def load(path: Path, schema: str, *, require_complete: bool) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != schema:
        raise ValueError(f"unexpected schema at {path}: {payload.get('schema_version')}")
    if require_complete and payload.get("status") != "complete":
        raise ValueError(f"not a completed {schema} artifact: {path}")
    return payload


def require_true(manifest: dict[str, Any], names: tuple[str, ...]) -> None:
    missing = [name for name in names if manifest.get("observational_guards", {}).get(name) is not True]
    if missing:
        raise ValueError(f"observed contract lacks required guards: {missing}")


def positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def build_matrix(*, contract: dict[str, Any], hybrid: dict[str, Any], edge: dict[str, Any]) -> list[dict[str, Any]]:
    scope = contract.get("contract", {}).get("contract_scope", {})
    unresolved = {row.get("name") for row in contract.get("contract", {}).get("unresolved_hardware_contract_parameters", [])}
    expected = {"pending_FIFO_depth_and_overflow_policy", "page_table_entry_bits_and_allocator_seal_policy", "bank_mapping_burst_gather_format", "merge_state_precision_and_PE_scheduler_interface", "bypass_switch_timing_and_admission_service_rate"}
    if unresolved != expected:
        raise ValueError("A4200 unresolved parameter set differs from the A4.2.1 contract")
    page_tokens = positive_int(scope.get("page_tokens"), "A4200 page tokens")
    if positive_int(hybrid.get("assumptions", {}).get("page_tokens"), "A36 page tokens") != page_tokens:
        raise ValueError("A36 page token point differs from A4200 observed contract")
    edge_pages = edge.get("assumptions", {}).get("page_tokens", [])
    if page_tokens not in edge_pages:
        raise ValueError("A3-edge sweep lacks A4200 observed page token point")
    ha, ea = hybrid["assumptions"], edge["assumptions"]
    return [
        {"parameter": "pending_FIFO_depth_and_overflow_policy", "a4_observed_requirement": "Pending retained cold staging is an explicit ordered source; empty pending is skipped, and dense native cold is absent.", "candidate_modeled_range": {"capacity_tokens_per_layer": ha["pending_staging_capacity_tokens_per_layer_points"], "overflow_policy": ha["pending_overflow_policy"]}, "evidence_class": "A4 semantic interface + A3.6 modeled sensitivity", "binding_status": "candidate_range_only", "next_binding_needed": "Measure or trace pending occupancy/overflow distribution under policy-on workloads before selecting a finite FIFO depth."},
        {"parameter": "page_table_entry_bits_and_allocator_seal_policy", "a4_observed_requirement": "Sealed pages expose ID, valid token count, retained positions, and append order; 64-token pages have full/tail witnesses.", "candidate_modeled_range": {"page_tokens": [page_tokens], "metadata_lookup_bytes_per_page": ha["metadata_lookup_bytes_per_page"], "metadata_lookup_cycles_per_page": ha["metadata_lookup_cycles_per_page"]}, "evidence_class": "A4 state/page witness + A3.6 modeled metadata point", "binding_status": "field_semantics_observed_size_unresolved", "next_binding_needed": "Choose a concrete PTE layout and allocator/seal protocol; rerun its explicit metadata sensitivity."},
        {"parameter": "bank_mapping_burst_gather_format", "a4_observed_requirement": "Packed and pending sources must be readable independently before merge; source skips are explicit.", "candidate_modeled_range": {"pending_gather_bytes_per_token": ha["pending_gather_bytes_per_token_points"], "bandwidth_bytes_per_cycle": ha["bandwidth_bytes_per_cycle"], "admission_memory_burst_bytes": ea["admission_memory_burst_bytes"], "admission_pack_bytes_per_cycle": ea["admission_pack_bytes_per_cycle_points"]}, "evidence_class": "A4 interface + A3.6/A3-edge modeled sensitivity", "binding_status": "candidate_range_only", "next_binding_needed": "Select a memory target and validate bank mapping, burst utilization, and gather representation against that target."},
        {"parameter": "merge_state_precision_and_PE_scheduler_interface", "a4_observed_requirement": "Every evaluation performs exactly one numerically stable online-softmax merge after source decisions.", "candidate_modeled_range": {"merge_state_bytes_per_head": ha["hybrid_merge_state_bytes_per_head_points"], "merge_cycles_per_head": ha["hybrid_merge_cycles_per_head_points"], "attention_engine_counts": ea["attention_engine_counts"], "schedulers": ha["schedulers"]}, "evidence_class": "A4 merge semantics + A3.6/A3-edge modeled sensitivity", "binding_status": "requires_scheduler_merge_reconciliation", "next_binding_needed": "A3-edge keeps each KV head-group on one engine and models no cross-engine merge; decide whether the hardware scheduler preserves that placement or explicitly models cross-engine merge."},
        {"parameter": "bypass_switch_timing_and_admission_service_rate", "a4_observed_requirement": "Full-KV bypass enters no Route-A admission/cold ownership; selected fast path performs original-mask replay and admission.", "candidate_modeled_range": {"admission_engine_counts": ea["admission_engine_counts"], "admission_page_setup_cycles": ea["admission_page_setup_cycles"], "admission_memory_burst_bytes": ea["admission_memory_burst_bytes"], "deferred_admission_decode_steps": ea["deferred_admission_decode_steps"]}, "evidence_class": "A4 control semantics + A3-edge modeled sensitivity", "binding_status": "candidate_range_only", "next_binding_needed": "Define the target controller and its service/overlap assumptions; preserve bypass as a true zero-admission control in each branch."},
    ]


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    observed = load(args.observed_resource_contract, A4200_SCHEMA, require_complete=True)
    require_true(observed, ("a4168_cross_horizon_accounting_verified", "a4167_h32_profiler_parent_verified", "all_layer_all_head_external_storage_semantics_verified", "native_cold_absence_verified", "cross_horizon_page_tail_witnesses_bound", "h32_profiler_and_cross_horizon_counts_agree", "unresolved_hardware_parameters_explicit", "no_model_execution"))
    hybrid = load(args.hybrid_sensitivity_manifest, A36_SCHEMA, require_complete=False)
    edge = load(args.edge_dse_manifest, A3_EDGE_SCHEMA, require_complete=False)
    matrix = build_matrix(contract=observed, hybrid=hybrid, edge=edge)
    config = {"observed_resource_contract": str(args.observed_resource_contract), "hybrid_sensitivity_manifest": str(args.hybrid_sensitivity_manifest), "edge_dse_manifest": str(args.edge_dse_manifest), "observed_resource_contract_sha256": hashlib.sha256(args.observed_resource_contract.read_bytes()).hexdigest(), "hybrid_sensitivity_manifest_sha256": hashlib.sha256(args.hybrid_sensitivity_manifest.read_bytes()).hexdigest(), "edge_dse_manifest_sha256": hashlib.sha256(args.edge_dse_manifest.read_bytes()).hexdigest()}
    args.output_dir.mkdir(parents=True)
    report = {"contract_scope": observed["contract"]["contract_scope"], "matrix": matrix, "modeled_source_boundaries": {"a36": hybrid.get("boundaries", []), "a3_edge": edge.get("notes", [])}, "boundaries": ["Candidate ranges come only from declared A3.6/A3-edge model assumptions; they are not A4 measurements or hardware calibration.", "This matrix does not choose a FIFO depth, metadata width, bank map, burst size, merge precision, PE count, scheduler, or controller timing.", "No Python timing, profiler row, allocator value, byte/cycle proxy, HBM traffic, throughput, energy, area, frequency, hardware acceleration, or RTL result is inferred."]}
    manifest = {"schema_version": A4201_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "report": report, "observational_guards": {"a4200_observed_contract_verified": True, "a36_modeled_sensitivity_schema_verified": True, "a3_edge_modeled_sensitivity_schema_verified": True, "observed_page_token_point_present_in_modeled_ranges": True, "all_unresolved_contract_parameters_mapped": True, "all_bindings_labeled_observed_or_modeled": True, "no_hardware_parameter_selected": True, "no_model_execution": True}, "boundaries": report["boundaries"]}
    output = args.output_dir / "a4201_contract_sensitivity_matrix.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.2.1 contract sensitivity matrix completed: {output}")


if __name__ == "__main__":
    main()
