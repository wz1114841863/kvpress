from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/realization_preparation_wrapper_common_disposition_manifest.json"
REVIEW = ROOT / "analysis/realization_preparation_wrapper_common_disposition.md"
TOP_SELECTION = ROOT / "analysis/synthesis_top_candidate_selection_manifest.json"


def test_wrapper_disposition_covers_only_array_interiors_and_preserves_owners() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "kvzap-realization-preparation-wrapper-common-1.0"
    assert manifest["status"] == "human_approved_wrapper_rtl_in_progress"
    wrappers = {row["id"]: row for row in manifest["wrapper_contracts"]}
    assert set(wrappers) == {
        "m2_entry_access_v1",
        "p3_stage_access_v1",
        "s2_payload_access_v1",
        "r5_availability_access_v1",
    }
    assert wrappers["m2_entry_access_v1"]["retained_owner"] == "RouteAM2ProductionControlOwner"
    assert wrappers["m2_entry_access_v1"]["implementation_status"] == "parent_side_lookup_commit_ack_adapter_pending_remote_directed_regression"
    assert wrappers["p3_stage_access_v1"]["retained_owner"] == "RouteAM2P3Wrapper"
    assert wrappers["r5_availability_access_v1"]["retained_owner"] == "RouteAPageManager"
    assert wrappers["r5_availability_access_v1"]["descriptor_treatment"] == "external_memory_service_not_local_array"
    assert all(row["physical_wrapper_mapping_pending"] for row in wrappers.values())


def test_common_disposition_is_fail_closed_and_keeps_external_costs_nonzero() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    dispositions = {row["provision"]: row["disposition"] for row in manifest["common_equivalence"]}
    assert dispositions["r2_r1_registry_router"] == "eligible_common_after_identical_shell"
    assert dispositions["s2_payload_gqa"] == "noncancellable_pending_full_kv_payload_wrapper"
    assert dispositions["lifecycle_status"] == "noncancellable_paired_semantics"
    assert dispositions["hot_residency"] == "route_a_differential_for_current_pair"
    assert manifest["external_numeric_costs"]["r4_numeric_partial_state"] == "route_a_differential_unestimated_not_zero"
    assert manifest["external_numeric_costs"]["external_memory_service"] == "external_system_cost_nonzero_same_declared_profile"
    assert "DC/CACTI" in manifest["prohibited_actions"]


def test_disposition_succeeds_the_selected_tops_without_premature_realization() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    selected = json.loads(TOP_SELECTION.read_text(encoding="utf-8"))
    selected_classes = {candidate["projection_from"] for candidate in selected["candidates"]}
    assert {manifest["candidate_tops"]["route_a"], manifest["candidate_tops"]["full_kv"]} == selected_classes
    review = REVIEW.read_text(encoding="utf-8")
    for required in (
        "human_approved_wrapper_rtl_in_progress",
        "equivalent implementation",
        "route_a_differential_for_current_pair",
        "unestimated_not_zero",
        "does **not** authorize macro selection",
    ):
        assert required in review
