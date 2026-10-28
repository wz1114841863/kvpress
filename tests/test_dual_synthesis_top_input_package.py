from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "analysis/dual_synthesis_top_input_package_20261028.json"
FREEZE = ROOT / "analysis/successor_synthesis_source_port_filelist_freeze_20261028.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_input_package_reuses_exact_successor_sources_and_live_ports() -> None:
    package = _load(PACKAGE)
    freeze = _load(FREEZE)
    assert package["status"] == "input_inventory_prepared_projection_generator_and_externalization_pending"
    assert package["preparation_anchor"]["source_port_freeze"] == "analysis/successor_synthesis_source_port_filelist_freeze_20261028.json"
    assert package["scala_source_closure"]["included_main_sources"] == list(freeze["scala_filelist"]["included_main_sources"])
    assert package["scala_source_closure"]["build_inputs"] == list(freeze["scala_filelist"]["build_inputs"])
    for contour in ("full_kv", "route_a"):
        assert package["candidates"][contour]["projection_source_class"] == freeze["candidate_tops"][contour]["class"]
        assert package["candidates"][contour]["outer_ports"] == freeze["candidate_tops"][contour]["outer_interfaces"]


def test_input_package_keeps_array_controls_and_external_references_explicit() -> None:
    package = _load(PACKAGE)
    assert {row["id"] for row in package["array_only_boundaries"]} == {"m2_entry_access_v1", "p3_stage_access_v1", "r5_availability_access_v1", "s2_payload_access_v1"}
    assert all("parent_control_retained" in row for row in package["array_only_boundaries"])
    external_ids = {row["id"] for row in package["external_and_reference_boundary_plan"]}
    assert {"external_core_mem_if_v1", "p3_pending_hbm_backing", "r5_descriptor_hbm_region", "functional_sidecar_delivery_reference", "outer_attention_partial_provider", "r4_numeric_partial_state"} <= external_ids
    readiness = package["synthesis_input_readiness"]
    assert readiness["projection_generator"].startswith("pending")
    assert readiness["generated_hdl_filelists"].startswith("pending")
    assert readiness["eligibility_disposition"] == "not DC ready; input inventory only"


def test_input_package_fails_closed_on_test_profile_or_common_cost_claims() -> None:
    package = _load(PACKAGE)
    assert package["shared_elaboration_profile"]["matched_fields"]["coreMemoryFragmentIndexWidth"] == 9
    assert "test-only" in package["shared_elaboration_profile"]["restriction"]
    prohibited = set(package["prohibited_conclusions"])
    assert "existing MeasurementDut classes are direct DC tops" in prohibited
    assert "generated Verilog or a DC filelist exists" in prohibited
    assert "S2/common cost cancellation" in prohibited
