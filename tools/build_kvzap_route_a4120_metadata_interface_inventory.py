#!/usr/bin/env python3
"""Freeze A4.12.0's metadata/control service interface (no macro or RTL)."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

SCHEMA = "kvzap-route-a4120-metadata-interface-inventory-1.0"

# Inputs are frozen by content, not by location. A verified remote mirror is
# acceptable; a later rerun is not.
FROZEN_INPUTS = {
    "a491": {"sha256": "ddf033d33234c4e1b0870cf8b9c3e775b30b1daca7ce43567f11dae6970be8b0", "schema": "kvzap-route-a491-candidate-metadata-engine-1.0"},
    "a410": {"sha256": "97f9cec11c8ffff95ce8405d303f35ddf76ea2c4078512f0d98d38e6ec0ec9e4", "schema": "kvzap-route-a410-queue-staging-credit-contract-1.0"},
    "a4112b": {"sha256": "57da81a6fb7e3a9540fad2d0a45ba28ae418ffc69d9e81ef2fbf02090dcdc3a3", "schema": "kvzap-route-a4112b-external-storage-binding-1.0"},
    "c5": {"sha256": "f7f3aec661602e5ec8febb7a43418c16cdf3dfc27e84a808a084b737d3c06fff", "schema": "cross-frontend-c5-hardware-direction-decision-1.0"},
    "c5_remote_replica": {"sha256": "1e45e60713ce6256df33c5efb06b5db93f1ecf6a630b9de7fb916b9d730868b3", "schema": "cross-frontend-c5-hardware-direction-decision-1.0"},
}
REQUIRED_A491_GUARDS = ("a490_exit_and_hash_chain_validated", "fifo_ownership_and_commit_predecessors_reused_unchanged", "joint_safe_field_widths_fit_every_declared_word_padded_modeled_object", "candidate_queue_overflow_is_observed_never_dropped", "no_hardware_measurement_claim")
REQUIRED_A410_GUARDS = ("a492_record_granular_execution_fixed_without_new_variant", "ha8_wide_primary_and_ha8_base_control_only", "lossless_credit_only_delays_transactions_without_drop_or_reorder", "transaction_fifo_ownership_and_single_commit_boundary_unchanged")
REQUIRED_A4112B_GUARDS = ("a4111_external_storage_exact_token_guard_remains_bound", "trace_on_external_storage_is_token_identical_to_trace_off_and_dense", "prefill_armed_external_storage_lifecycle_observed", "fixed_a410_parameters_not_retuned", "unmapped_hardware_fields_not_synthesized")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.12.0 no-model metadata/control interface inventory; no SRAM port/macro, physical-capacity, timing, energy, area, architecture, or RTL selection.")
    parser.add_argument("--a491-report", type=Path, required=True)
    parser.add_argument("--a410-report", type=Path, required=True)
    parser.add_argument("--a4112b-report", type=Path, required=True)
    parser.add_argument("--c5-report", type=Path, required=True)
    parser.add_argument("--c5-remote-replica-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate frozen bindings without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def read_frozen(path: Path, name: str) -> tuple[dict[str, Any], dict[str, str]]:
    spec = FROZEN_INPUTS[name]
    if not path.is_file():
        raise FileNotFoundError(f"{name} frozen input is absent: {path}")
    actual_sha = sha256_file(path)
    if actual_sha != spec["sha256"]:
        raise ValueError(f"{name} SHA-256 differs from the A4.12.0 frozen input")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != spec["schema"] or value.get("status") != "complete":
        raise ValueError(f"{name} is not a completed frozen {spec['schema']} artifact")
    return value, {"path": str(path), "sha256": actual_sha, "schema_version": spec["schema"]}


def require_guards(report: dict[str, Any], required: tuple[str, ...], name: str) -> None:
    if any(report.get("semantic_guards", {}).get(key) is not True for key in required):
        raise ValueError(f"{name} lacks a required frozen semantic guard")


def validate_contracts(a491: dict[str, Any], a410: dict[str, Any], a4112b: dict[str, Any], c5: dict[str, Any], c5_remote: dict[str, Any]) -> dict[str, Any]:
    """Validate immutable semantic inputs and return the normalized inventory."""
    require_guards(a491, REQUIRED_A491_GUARDS, "A4.9.1")
    require_guards(a410, REQUIRED_A410_GUARDS, "A4.10")
    require_guards(a4112b, REQUIRED_A4112B_GUARDS, "A4.11.2b")
    candidate = next((row for row in a491.get("config", {}).get("candidates", []) if row.get("name") == "ha8_wide"), None)
    expected_candidate = {"name": "ha8_wide", "banks": 8, "mapping": "head_affine_v1", "read_ports": 2, "write_ports": 2, "rmw_lanes": 2, "queue_groups_per_bank": 32, "commit_slots": 0}
    if candidate != expected_candidate:
        raise ValueError("A4.9.1 HA8-wide declared candidate differs from the frozen input")
    entry = a491.get("candidate_entry_sufficiency", {})
    padded = {"head_control": 64, "span_owner": 64}
    if entry.get("modeled_object_raw_width_bits") != {"head_control": 59, "span_owner": 50} or entry.get("candidate_entry_width_bits") != padded:
        raise ValueError("A4.9.1 joint-safe metadata entry accounting differs from the frozen input")
    if entry.get("joint_safe_raw_metadata_bits") != 43975 or entry.get("candidate_aligned_metadata_bits") != 53696:
        raise ValueError("A4.9.1 joint-safe metadata totals differ from the frozen input")
    q = a410.get("config", {})
    if (q.get("fixed_execution"), q.get("local_capacity_per_bank"), q.get("shared_capacity_per_layer"), q.get("staging_capacity_per_layer")) != ("A4.9.2 record-granular only", 32, 256, 512):
        raise ValueError("A4.10 logical queue/staging contract differs from the frozen input")
    if q.get("candidates") != ["ha8_base", "ha8_wide"]:
        raise ValueError("A4.10 candidate set differs from the frozen input")
    binding = a4112b.get("config", {})
    if (binding.get("fixed_a410_execution"), binding.get("local_capacity_per_bank"), binding.get("shared_capacity_per_layer"), binding.get("staging_capacity_per_layer"), binding.get("token_to_span_tokens")) != ("record-granular HA8-wide", 32, 256, 512, 64):
        raise ValueError("A4.11.2b fixed software-to-model binding differs from the frozen input")
    if a4112b.get("input_artifacts", {}).get("a410_report_sha256") != FROZEN_INPUTS["a410"]["sha256"]:
        raise ValueError("A4.11.2b no longer binds the frozen A4.10 report")
    for label, report in (("C5", c5), ("C5 remote replica", c5_remote)):
        decision, gate = report.get("direction_decision", {}), report.get("c5_gate", {})
        if decision.get("primary_direction") != "route_a_persistent_packed_backend" or decision.get("decision") != "retain_as_primary_research_and_architecture_path":
            raise ValueError(f"{label} no longer retains Route-A persistent-packed as the research path")
        if any(gate.get(key) is not expected for key, expected in {"hardware_parameter_selected": False, "architecture_spec_frozen": False, "rtl_authorized": False}.items()):
            raise ValueError(f"{label} incorrectly authorizes a physical parameter, architecture, or RTL")
    semantic_fields = [{"name": name, "bits": int(bits), "class": "metadata_semantics", "source": "A4.9.1 joint-safe accounting"} for name, bits in sorted(entry["joint_safe_field_widths_bits"].items())]
    payload_parameters = [
        {"name": "payload_page_id_bits", "status": "parameterized_unfrozen", "depends_on": ["A4.13 physical page count", "A4.13 payload allocation scope"]},
        {"name": "payload_page_offset_bits", "status": "parameterized_unfrozen", "depends_on": ["A4.13 payload page size"]},
        {"name": "payload_bank_bits", "status": "parameterized_unfrozen", "depends_on": ["A4.13 payload-bank organization"]},
        {"name": "payload_address_or_handle_bits", "status": "parameterized_unfrozen", "depends_on": ["A4.13 payload address space and placement"]},
    ]
    return {
        "frozen_service_requirement": {"bank_count": 8, "mapping": "head_affine_v1", "maximum_read_class_issues_per_abstract_service_opportunity": 2, "maximum_write_class_issues_per_abstract_service_opportunity": 2, "maximum_commit_coupled_rmw_issues_per_abstract_service_opportunity": 2, "requirement_boundary": "These are HA8-wide declared modeled service capabilities. They are not selected SRAM read/write port counts, macro ports, lanes, access timing, or a hardware implementation."},
        "logical_resource_contract": {"local_queue_capacity_per_bank_transaction_groups": 32, "shared_overflow_capacity_per_layer_transaction_groups": 256, "staging_capacity_per_layer_transaction_groups": 512, "logical_contract_boundary": "These are A4.10 logical guaranteed capacities, not a decision to physically duplicate SRAM per layer. A4.12.1 may evaluate provisioning/pooling only without changing these guarantees."},
        "metadata_entry_accounting": {"layout": "both_colocated_direct_v1", "joint_safe_raw_width_bits": {"head_control": 59, "span_owner": 50}, "declared_word_padded_width_bits": padded, "word_alignment_bits": 64, "joint_safe_modeled_object_counts": entry["modeled_object_counts"], "joint_safe_raw_modeled_bits": 43975, "declared_padded_candidate_bits": 53696, "semantic_fields": semantic_fields, "payload_dependent_fields": payload_parameters, "address_boundary": "No payload page, bank, HBM, or physical address field is included in the frozen 59/50-bit accounting. A4.13 must instantiate these parameters, after which A4.12 metadata width accounting may be re-evaluated without reopening metadata semantics or queue contracts."},
        "software_to_model_interface": {"arrival_source": "A4.11.2b prefill-armed external-storage maturity/admission lifecycle", "fixed_conversion": "retained token -> 64-token span -> append-event/layer/KV-head transaction group", "transaction_members": ["head_control_rmw", "span_owner_rmw"], "directly_observed": a4112b["evidence_classes"]["direct_software_observation"], "deterministic_conversion_only": a4112b["evidence_classes"]["deterministic_conversion"], "hardware_model_only": a4112b["evidence_classes"]["declared_hardware_model_only"]},
        "immutability_rules": ["A4.12 must not change A4.8/A4.9 RMW or single-commit semantics, A4.9.2 execution granularity, or A4.10 queue/credit parameters.", "A4.12.1/2 may choose a physical realization for the frozen service requirement but may not relabel it as a previously observed physical port count.", "A4.12 results do not authorize returning to A4.8-A4.11 to change semantics, queue, scheduler, pruning, or admission to improve a cost result.", "Payload-dependent fields remain parameters for A4.13; their later instantiation must not silently change the frozen semantic entry accounting."],
    }


def build_report(paths: dict[str, Path]) -> dict[str, Any]:
    reports, inputs = {}, {}
    for name, path in paths.items():
        reports[name], inputs[name] = read_frozen(path, name)
    inventory = validate_contracts(reports["a491"], reports["a410"], reports["a4112b"], reports["c5"], reports["c5_remote_replica"])
    config = {"stage": "A4.12.0", "purpose": "freeze metadata/control logical service requirements and provenance before physical macro DSE", "a4121_candidate_limit": ["M1_banked_sram_pipelined_rmw", "M2_replicated_or_duplicated_control_storage", "M3_register_hot_state_with_sram_backing"], "payload_physicalization_stage": "A4.13"}
    return {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "execution_classification": "no-model provenance and logical-interface inventory; not a measured or modeled physical hardware result", "config": config, "config_hash": stable_hash(config), "input_artifacts": inputs, "interface_inventory": inventory, "semantic_guards": {"only_accepted_a491_a410_a4112b_and_c5_contents_are_bound": True, "ha8_wide_service_capability_not_relabelled_as_physical_sram_ports": True, "logical_queue_contract_not_relabelled_as_per_layer_physical_sram_provision": True, "payload_dependent_address_fields_remain_parameterized": True, "a412_does_not_reopen_execution_queue_scheduler_or_pruning_variants": True, "no_model_trace_replay_macro_cycle_area_or_energy_execution": True}, "boundaries": ["A4.12.0 freezes provenance and a logical metadata/control interface only. It selects neither macro organization nor physical capacity provisioning.", "The frozen HA8-wide 2/2/2 abstract capability is a service requirement, not a statement that an SRAM macro has 2R2W ports or two physical RMW lanes.", "Logical capacity, trace peak occupancy, and physical provisioned capacity are intentionally distinct. Only the first appears in this inventory.", "The report contains no cycle, timing, throughput, traffic, energy, area, architecture-specification, or RTL result."]}


def main() -> None:
    args = parse_args()
    paths = {"a491": args.a491_report, "a410": args.a410_report, "a4112b": args.a4112b_report, "c5": args.c5_report, "c5_remote_replica": args.c5_remote_replica_report}
    report = build_report(paths)
    if args.preflight_only:
        print("A4.12.0 preflight passed: frozen source hashes, semantic guards, and logical interface are valid; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"A4.12.0 output directory already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a4120_metadata_interface_inventory_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.12.0 complete: {output} sha256={sha256_file(output)}")


if __name__ == "__main__":
    main()
