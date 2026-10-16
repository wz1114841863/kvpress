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
    assert bom["status"] == "candidate_selection_pending_human_review"
    assert bom["anchors"]["functional_closure_decision"] == "cf9f055"
    candidate = bom["candidate"]
    assert candidate["id"] == "route_a_measurement_control_cut"
    assert candidate["current_top_is_candidate"] is False
    assert "functional_providers_fixtures_observers_oracles" in candidate["outside_boundary"]
    assert "logical-storage-wrapper adapters" in candidate["mandatory_integration_costs"]

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
    assert by_id["r1_core_transaction_control"]["membership"] == "inside_candidate_logic_with_external_port"
    assert by_id["m2_storage_realization"]["membership"] == "inside_logical_control_wrapper_boundary"
    assert by_id["p3_payload_stage_page"]["membership"] == "inside_logical_control_wrapper_boundary"
    assert by_id["r4_numeric_partial_state"]["membership"] == "external_boundary_pending_evidence"
    assert by_id["outer_attention_partial_provider"]["membership"] == "external_boundary_pending_evidence"
    assert by_id["external_memory_service"]["membership"] == "external_boundary_pending_evidence"
    assert by_id["m2_reference_provider"]["membership"] == "excluded_functional_reference"
    assert by_id["functional_sidecar_delivery_reference"]["membership"] == "excluded_functional_reference"
    assert by_id["testbench_observers_fixtures_and_oracles"]["membership"] == "excluded_verification_only"
    assert bom["next_gate"].startswith("human MBR.0 review")

    top = TOP.read_text(encoding="utf-8")
    assert "composition-only" in top
    assert "StructuralTieOff.source" in top
    assert "functional_r4_reference" in top

    selection = SELECTION.read_text(encoding="utf-8")
    for phrase in [
        "Candidate selection complete; **pending human MBR review**",
        "route_a_measurement_control_cut",
        "Required non-tied functional contours",
        "not the MBR.1 baseline design",
        "**not** resolve SRP.5's future-top blocker",
        "it does not authorize RTL, wrapper selection, synthesis, or PPA.",
    ]:
        assert phrase in selection, phrase
    print("PASS: MBR.0 selects a bounded candidate BOM without authorizing realization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
