#!/usr/bin/env python3
"""Validate the bounded, non-implementing MBR.0 candidate boundary record."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/synthesis_eligibility_manifest.json"
BOM = ROOT / "analysis/measurement_boundary_bom.json"
SELECTION = ROOT / "analysis/measurement_boundary_selection.md"
TOP = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bom = json.loads(BOM.read_text(encoding="utf-8"))
    assert bom["schema_version"] == "kvzap-route-a-mbr-0-measurement-boundary-bom-1.0"
    assert bom["status"] == "human_review_passed_mbr1_planning_authorized"
    assert bom["anchors"]["functional_closure_decision"] == "cf9f055"
    candidate = bom["candidate"]
    assert candidate["id"] == "route_a_measurement_control_cut"
    assert candidate["current_top_is_candidate"] is False
    assert "functional_providers_fixtures_observers_oracles" in candidate["outside_boundary"]
    assert "logical-storage-wrapper adapters" in candidate["mandatory_integration_costs"]
    assert candidate["integration_cost_evidence_status"] == "deferred_unestimated"
    assert candidate["integration_cost_allocation_due"] == "MBR.1 paired Full-KV classification"
    assert "analysis/srp4_differential_cost_evidence_plan.md" in candidate["integration_cost_evidence_plan_ref"]

    expected_ids = {item["id"] for item in manifest["partition_records"]}
    mapped_ids = [partition_id for row in bom["records"] for partition_id in row["partition_ids"]]
    assert len(expected_ids) == 30
    assert len(mapped_ids) == len(expected_ids)
    assert len(set(mapped_ids)) == len(mapped_ids)
    assert set(mapped_ids) == expected_ids
    assert {row["membership"] for row in bom["records"]} <= set(bom["membership_values"])
    assert all(row["source_classes"] and row["activation"] and row["regression"] for row in bom["records"])

    by_id = {row["id"]: row for row in bom["records"]}
    assert by_id["top_future_synthesis_boundary"]["membership"] == "new_measurement_top_required"
    assert by_id["top_future_synthesis_boundary"]["integration_cost_evidence_status"] == "deferred_unestimated"
    assert by_id["r1_core_transaction_control"]["membership"] == "inside_candidate_logic_with_external_port"
    assert by_id["m2_storage_realization"]["membership"] == "inside_logical_control_wrapper_boundary"
    assert by_id["p3_payload_stage_page"]["membership"] == "inside_logical_control_wrapper_boundary"
    assert by_id["r4_numeric_partial_state"]["membership"] == "external_boundary_pending_evidence"
    assert by_id["outer_attention_partial_provider"]["membership"] == "external_boundary_pending_evidence"
    assert by_id["external_memory_service"]["membership"] == "external_boundary_pending_evidence"
    assert by_id["m2_reference_provider"]["membership"] == "excluded_functional_reference"
    assert by_id["functional_sidecar_delivery_reference"]["membership"] == "excluded_functional_reference"
    assert by_id["testbench_observers_fixtures_and_oracles"]["membership"] == "excluded_verification_only"
    for record_id in [
        "m2_storage_realization",
        "p3_pending_hbm_backing",
        "p3_payload_stage_page",
        "r5_availability_state",
        "r5_descriptor_hbm_region",
        "s2_common_payload_gqa_control",
        "s2_incremental_sidecar_storage",
        "r4_numeric_partial_state",
        "external_memory_service",
    ]:
        assert "analysis/srp3_realization_requirements_decision_plan.md" in by_id[record_id]["cost_evidence_plan_ref"]
        assert "analysis/srp4_differential_cost_evidence_plan.md" in by_id[record_id]["cost_evidence_plan_ref"]
    for record_id in ["m2_storage_realization", "p3_payload_stage_page", "r5_availability_state", "s2_common_payload_gqa_control", "s2_incremental_sidecar_storage"]:
        assert "array only may use a future black-box/macro proxy" in by_id[record_id]["array_treatment"]
    assert bom["next_gate"].startswith("MBR.1 paired Full-KV fairness-plan review")

    top = TOP.read_text(encoding="utf-8")
    assert "composition-only" in top
    assert "StructuralTieOff.source" in top
    assert "functional_r4_reference" in top

    selection = SELECTION.read_text(encoding="utf-8")
    for phrase in [
        "Candidate selection completed and **human MBR.0 review passed**",
        "route_a_measurement_control_cut",
        "Required non-tied functional contours",
        "Evidence references and array-versus-control split",
        "deferred_unestimated",
        "RouteAS2GqaSourceWrapper",
        "wholesale merely because it",
        "not the MBR.1 baseline design",
        "It **does not** resolve SRP.5's future-top",
        "fairness-baseline planning; it does not authorize RTL, wrapper selection,",
    ]:
        assert phrase in selection, phrase
    print("PASS: MBR.0 selects a bounded candidate BOM without authorizing realization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
