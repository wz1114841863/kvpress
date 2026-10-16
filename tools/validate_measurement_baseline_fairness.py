#!/usr/bin/env python3
"""Validate MBR.1's bounded paired Full-KV fairness-plan record."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/synthesis_eligibility_manifest.json"
BOM = ROOT / "analysis/measurement_boundary_bom.json"
MATRIX = ROOT / "analysis/measurement_baseline_matrix.json"
PLAN = ROOT / "analysis/measurement_baseline_fairness_plan.md"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bom = json.loads(BOM.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert bom["status"] == "human_review_passed_mbr1_planning_authorized"
    assert matrix["schema_version"] == "kvzap-route-a-mbr-1-baseline-fairness-matrix-1.0"
    assert matrix["status"] == "baseline_planning_approved_for_limited_chisel_measurement_dut_preparation"
    assert matrix["route_a_candidate"] == bom["candidate"]["id"]
    assert matrix["full_kv_candidate"]["id"] == "full_kv_measurement_control_cut"
    assert matrix["full_kv_candidate"]["source_top_exists"] is False
    assert "same core_mem_if_v1 reset/init/fault/stale-response contract" in matrix["shared_configuration_requirements"]
    assert "same declared external-memory service/profile basis; service is not zero cost" in matrix["shared_configuration_requirements"]

    expected = {row["id"] for row in manifest["partition_records"]}
    rows = matrix["comparison_rows"]
    mapped = [row["partition_id"] for row in rows]
    assert len(expected) == 30
    assert len(mapped) == len(expected)
    assert len(set(mapped)) == len(mapped)
    assert set(mapped) == expected
    allowed = set(matrix["comparison_class_values"])
    assert all(row["comparison_class"] in allowed for row in rows)
    assert all(row["route_a_treatment"] and row["full_kv_treatment"] and row["evidence_route"] and row["prohibited_assumption"] for row in rows)
    by_id = {row["partition_id"]: row for row in rows}
    for record_id in ["r6_common_lifecycle_control", "common_hot_residency_control", "r2_shared_arbitration_control", "r1_core_transaction_control", "s2_common_payload_gqa_control"]:
        assert by_id[record_id]["comparison_class"] == "paired_common_pending_equivalence"
    for record_id in ["m2_reference_provider", "functional_sidecar_delivery_reference", "testbench_observers_fixtures_and_oracles"]:
        assert by_id[record_id]["comparison_class"] == "excluded_verification_only"
    assert by_id["external_memory_service"]["comparison_class"] == "external_same_service_pending_evidence"
    assert by_id["r4_numeric_partial_state"]["comparison_class"] == "external_route_a_increment_pending_evidence"
    assert by_id["outer_attention_partial_provider"]["comparison_class"] == "differential_activity_pending_event_evidence"
    assert by_id["top_future_synthesis_boundary"]["comparison_class"] == "mixed_common_differential_deferred"
    assert by_id["top_future_synthesis_boundary"]["cost_evidence_status"] == "deferred_unestimated"
    assert "zero" in by_id["external_memory_service"]["prohibited_assumption"]

    allocations = matrix["integration_cost_allocations"]
    assert len(allocations) == 5
    assert {row["category"] for row in allocations} == {
        "interface_adaptation", "reset_init_gating", "protocol_fanout_muxing",
        "delivery_context_connectivity", "logical_storage_wrapper_adapters",
    }
    assert all(row["evidence_status"] == "deferred_unestimated" and row["required_evidence"] for row in allocations)
    assert "cannot add them into latency, throughput, energy, or net-benefit" in matrix["non_additivity_rule"]
    assert "MBR.1 is closed and must not be repeated" in matrix["approval_record"]
    assert matrix["next_gate"].startswith("separate user authorization for the bounded Chisel")

    plan = PLAN.read_text(encoding="utf-8")
    for phrase in [
        "MBR.1 — Paired Full-KV Measurement-Baseline Fairness Plan",
        "full_kv_measurement_control_cut",
        "Full-KV is not defined by deleting Route-A signals from a witness.",
        "Future-top integration allocation",
        "deferred_unestimated",
        "declared matching service/profile basis",
        "Payload\nand metadata coordinates are retained separately",
        "Area, static-power, and dynamic-energy/activity ledgers",
        "A_RA_R4_numeric_or_partial_state",
        "E_RA_source_partial_delta_events",
        "mixed\ncommon/differential, deferred",
        "does not create Full-KV RTL",
    ]:
        assert phrase in plan, phrase
    print("PASS: MBR.1 maps a paired Full-KV fairness plan without realization claims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
