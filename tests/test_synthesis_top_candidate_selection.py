from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/synthesis_top_candidate_selection_manifest.json"
BOM = ROOT / "analysis/measurement_boundary_bom.json"
REVIEW = ROOT / "analysis/synthesis_top_candidate_selection_review.md"
HANDOFF = ROOT / "analysis/route_a_current_handoff.md"
SKELETON = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala"


def test_candidate_selection_covers_the_bom_without_selecting_the_skeleton() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bom = json.loads(BOM.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "kvzap-synthesis-top-candidate-selection-1.0"
    assert manifest["status"] == "conditional_paired_control_top_candidates_selected"
    assert manifest["measurement_cut_freeze"]["record"] == "analysis/measurement_dut_cut_freeze_20261025.json"
    assert manifest["rejected_current_top"]["class"] == "kvpress.routea.top.RouteAKVSubsystemTop"

    ids = {candidate["id"] for candidate in manifest["candidates"]}
    assert ids == {"route_a_synthesis_control_top_candidate_v1", "full_kv_synthesis_control_top_candidate_v1"}
    assert all(candidate["projection_from"] != manifest["rejected_current_top"]["class"] for candidate in manifest["candidates"])

    route_a = next(candidate for candidate in manifest["candidates"] if candidate["id"].startswith("route_a_"))
    selected = set(route_a["included_partition_classes"])
    selected.update(route_a["external_or_wrapper_partitions"])
    selected.update(route_a["excluded_partition_classes"])
    selected.update(manifest["deferred_partition_classes"])
    expected = {partition_id for row in bom["records"] for partition_id in row["partition_ids"]}
    assert selected == expected
    assert sum(
        len(values)
        for values in (
            route_a["included_partition_classes"],
            route_a["external_or_wrapper_partitions"],
            route_a["excluded_partition_classes"],
            manifest["deferred_partition_classes"],
        )
    ) == len(selected)


def test_candidate_selection_preserves_pre_dc_fairness_and_reference_gates() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    common = manifest["common_equivalence"]
    assert "RouteAHotSourcePath" in common["pre_dc_fairness_condition"]
    assert "S2 payload/GQA" in common["semantically_paired_but_nonidentical"]
    assert "lifecycle/status" in common["semantically_paired_but_nonidentical"]
    assert manifest["next_authorized_activity"] == "array-only wrapper-interface planning and common-equivalence disposition"
    assert "run DC/CACTI" in manifest["prohibited_actions"]
    assert "composition-only" in SKELETON.read_text(encoding="utf-8")


def test_candidate_selection_is_live_linked_and_nonphysical() -> None:
    review = REVIEW.read_text(encoding="utf-8")
    assert "Synthesis-top candidate selection (2026-10-25)" in HANDOFF.read_text(encoding="utf-8")
    for required in (
        "conditional_paired_control_top_candidates_selected",
        "RouteAKVSubsystemTop` is expressly **not** a candidate",
        "single-record",
        "Pre-DC closure conditions",
        "does not authorize Chisel changes, physical macro selection, DC/CACTI, or PPA",
    ):
        assert required in review
