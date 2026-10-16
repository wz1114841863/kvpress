#!/usr/bin/env python3
"""Validate the bounded MBR.1-A measurement-realization candidate proposal."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/measurement_realization_candidate_manifest.json"
PROPOSAL = ROOT / "analysis/measurement_realization_candidate_proposal.md"
MATRIX = ROOT / "analysis/measurement_baseline_matrix.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "kvzap-route-a-mbr-1a-measurement-realization-candidate-1.0"
    assert manifest["status"] == "candidate_preparation_scope_approved_for_bounded_chisel_work_package"
    assert matrix["status"] == "baseline_planning_approved_for_limited_chisel_measurement_dut_preparation"
    candidates = {item["id"]: item for item in manifest["candidates"]}
    assert set(candidates) == {"route_a_control_measurement_dut_candidate_v0", "full_kv_control_measurement_dut_candidate_v0"}
    assert all(item["source_top_exists"] is False for item in candidates.values())
    route_a = candidates["route_a_control_measurement_dut_candidate_v0"]
    route_a_ids = {partition_id for group in route_a["included_control_groups"] for partition_id in group["partition_ids"]}
    assert {"r3_materialization_publication_control", "m2_control_protocol", "p3_wrapper_control", "r5_allocator_reclaim_control", "s2_common_payload_gqa_control", "r4_structural_merge_control"} <= route_a_ids
    assert "core_mem_if_v1" in route_a["external_contract_ports"]
    full_kv = candidates["full_kv_control_measurement_dut_candidate_v0"]
    full_kv_ids = {partition_id for group in full_kv["included_contract_groups"] for partition_id in group["partition_ids"]}
    assert full_kv_ids == {"r6_common_lifecycle_control", "common_hot_residency_control", "r2_shared_arbitration_control", "r1_core_transaction_control", "s2_common_payload_gqa_control"}
    assert "position_sidecar" in full_kv["excluded_features"]
    assert "r6_terminal_retire_contract" in full_kv["external_contract_ports"]
    assert "same core_mem_if_v1" in manifest["common_interface_requirements"]
    assert "same S2 fill_READY_four_consumer_release lifecycle" in manifest["common_interface_requirements"]
    assert set(manifest["no_tieoff_gate"]["forbidden"]) == {"StructuralTieOff", "forced_internal_carrier", "testbench_producer", "dangling_accepted_output"}
    assert len(manifest["array_proxy_boundaries"]) == 6
    by_storage_id = {item["id"]: item for item in manifest["array_proxy_boundaries"]}
    assert by_storage_id["r5_descriptor"]["boundary_type"] == "external_memory_service"
    assert "not a local SRAM-array proxy" in by_storage_id["r5_descriptor"]["array_only"]
    r4 = manifest["r4_numeric_candidate"]
    assert r4["partial_topology"] == {"consumer_count": 4, "max_source_partials_per_consumer": 3, "canonical_source_order": ["hot", "pending", "packed"], "interpretation": "consumer count is not a physical numeric-interface count"}
    assert r4["excluded"] == ["qkv_generation", "dot_products", "score_creation", "complete_attention_mac_array"]
    full_kv_precondition = manifest["full_kv_path_provenance_precondition"]
    assert full_kv_precondition["status"] == "unresolved_required_before_chisel_integration"
    assert len(full_kv_precondition["required_mappings"]) == 3
    assert full_kv_precondition["failure_action"].startswith("block any Full-KV Chisel integration")
    assert manifest["integration_shell"]["classification"] == "mixed_common_differential_deferred"
    assert "do not repeat MBR review" in manifest["approval_record"]
    assert manifest["next_gate"].startswith("separate user authorization for the bounded Chisel")

    proposal = PROPOSAL.read_text(encoding="utf-8")
    for phrase in [
        "Measurement-Realization Candidate Proposal",
        "not a re-execution of MBR.1",
        "No-tie-off / no-optimization gate",
        "Full-KV legal-path provenance prerequisite",
        "StructuralTieOff",
        "Array-only proxy boundary and DC + CACTI preparation",
        "R4 numeric route without a full attention PE",
        "mixed common/differential deferred envelope",
        "no Chisel change",
        "each consumer accepts at most three source partials",
    ]:
        assert phrase in proposal, phrase
    print("PASS: MBR.1-A candidate preparation remains bounded and approval-gated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
