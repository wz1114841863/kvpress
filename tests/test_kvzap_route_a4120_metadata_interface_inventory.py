from copy import deepcopy
import hashlib

import pytest

from tools.build_kvzap_route_a4120_metadata_interface_inventory import FROZEN_INPUTS, materialize_inputs, validate_contracts


def reports():
    a491 = {
        "semantic_guards": {"a490_exit_and_hash_chain_validated": True, "fifo_ownership_and_commit_predecessors_reused_unchanged": True, "joint_safe_field_widths_fit_every_declared_word_padded_modeled_object": True, "candidate_queue_overflow_is_observed_never_dropped": True, "no_hardware_measurement_claim": True},
        "config": {"candidates": [{"name": "ha8_wide", "banks": 8, "mapping": "head_affine_v1", "read_ports": 2, "write_ports": 2, "rmw_lanes": 2, "queue_groups_per_bank": 32, "commit_slots": 0}]},
        "candidate_entry_sufficiency": {"modeled_object_raw_width_bits": {"head_control": 59, "span_owner": 50}, "candidate_entry_width_bits": {"head_control": 64, "span_owner": 64}, "joint_safe_raw_metadata_bits": 43975, "candidate_aligned_metadata_bits": 53696, "modeled_object_counts": {"head_control": 225, "span_owner": 614}, "joint_safe_field_widths_bits": {"valid_bit": 1, "span_slot_bits": 6}},
    }
    a410 = {"semantic_guards": {"a492_record_granular_execution_fixed_without_new_variant": True, "ha8_wide_primary_and_ha8_base_control_only": True, "lossless_credit_only_delays_transactions_without_drop_or_reorder": True, "transaction_fifo_ownership_and_single_commit_boundary_unchanged": True}, "config": {"fixed_execution": "A4.9.2 record-granular only", "local_capacity_per_bank": 32, "shared_capacity_per_layer": 256, "staging_capacity_per_layer": 512, "candidates": ["ha8_base", "ha8_wide"]}}
    a4112b = {"semantic_guards": {"a4111_external_storage_exact_token_guard_remains_bound": True, "trace_on_external_storage_is_token_identical_to_trace_off_and_dense": True, "prefill_armed_external_storage_lifecycle_observed": True, "fixed_a410_parameters_not_retuned": True, "unmapped_hardware_fields_not_synthesized": True}, "config": {"fixed_a410_execution": "record-granular HA8-wide", "local_capacity_per_bank": 32, "shared_capacity_per_layer": 256, "staging_capacity_per_layer": 512, "token_to_span_tokens": 64}, "input_artifacts": {"a410_report_sha256": "97f9cec11c8ffff95ce8405d303f35ddf76ea2c4078512f0d98d38e6ec0ec9e4"}, "evidence_classes": {"direct_software_observation": ["maturity"], "deterministic_conversion": ["token_to_span"], "declared_hardware_model_only": ["bank mapping"]}}
    c5 = {"direction_decision": {"primary_direction": "route_a_persistent_packed_backend", "decision": "retain_as_primary_research_and_architecture_path"}, "c5_gate": {"hardware_parameter_selected": False, "architecture_spec_frozen": False, "rtl_authorized": False}}
    return a491, a410, a4112b, c5, deepcopy(c5)


def test_inventory_separates_service_requirement_from_macro_ports_and_payload_fields():
    inventory = validate_contracts(*reports())
    service = inventory["frozen_service_requirement"]
    assert service["bank_count"] == 8
    assert service["maximum_commit_coupled_rmw_issues_per_abstract_service_opportunity"] == 2
    assert "not selected SRAM" in service["requirement_boundary"]
    assert {item["name"] for item in inventory["metadata_entry_accounting"]["payload_dependent_fields"]} == {"payload_page_id_bits", "payload_page_offset_bits", "payload_bank_bits", "payload_address_or_handle_bits"}


def test_inventory_rejects_a410_contract_reparameterization():
    a491, a410, a4112b, c5, c5_remote = reports()
    a410["config"]["staging_capacity_per_layer"] = 513
    with pytest.raises(ValueError, match="logical queue/staging contract"):
        validate_contracts(a491, a410, a4112b, c5, c5_remote)


def test_inventory_rejects_c5_premature_rtl_authorization():
    a491, a410, a4112b, c5, c5_remote = reports()
    c5_remote["c5_gate"]["rtl_authorized"] = True
    with pytest.raises(ValueError, match="incorrectly authorizes"):
        validate_contracts(a491, a410, a4112b, c5, c5_remote)


def test_inventory_materializes_hash_checked_inputs_beside_result(tmp_path, monkeypatch):
    source = tmp_path / "source.json"
    source.write_text('{"frozen": true}\n', encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setitem(FROZEN_INPUTS, "unit", {"sha256": digest, "schema": "unit", "canonical_origin_path": "canonical/unit.json"})
    output = tmp_path / "result"
    output.mkdir()
    report = {"input_artifacts": {"unit": {"sha256": digest}}}
    materialize_inputs({"unit": source}, output, report)
    copied = output / "input_artifacts" / "unit_source.json"
    assert copied.read_bytes() == source.read_bytes()
    assert report["input_artifacts"]["unit"]["materialized_copy"] == str(copied)
