from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "analysis/measurement_dut_cut_freeze_20261025.json"
BOM = ROOT / "analysis/measurement_boundary_bom.json"
HANDOFF = ROOT / "analysis/route_a_current_handoff.md"


def test_dual_measurement_cut_freeze_hashes_and_actual_top_inventory() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert freeze["schema_version"] == "kvzap-dual-measurement-cut-freeze-1.0"
    assert freeze["status"] == "functional_measurement_cut_frozen"
    assert freeze["source_anchor"]["git_commit"] == "fc06fdbc763325e55638f6cc164cf251b424a2f2"
    assert freeze["source_anchor"]["excluded_dirty_paths"] == [".gitignore"]

    for relative, expected in freeze["source_sha256"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, relative

    for dut in freeze["dut_tops"].values():
        source = (ROOT / dut["source"]).read_text(encoding="utf-8")
        for port in dut["outer_interfaces"]:
            assert f"val {port}" in source, (dut["class"], port)
        for instance in dut["instances"]:
            assert f"new {instance}(p)" in source, (dut["class"], instance)


def test_dual_measurement_cut_freeze_maps_each_bom_record_once() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    bom = json.loads(BOM.read_text(encoding="utf-8"))
    expected = {partition_id for row in bom["records"] for partition_id in row["partition_ids"]}
    categories = freeze["cost_classification"]
    actual = set().union(*categories.values())
    assert len(expected) == 30
    assert actual == expected
    assert sum(len(values) for values in categories.values()) == len(actual)
    assert freeze["direct_pending_limit"]["valid_count"] == 1
    assert "multi-record" in freeze["direct_pending_limit"]["prohibited_inference"]


def test_dual_measurement_cut_freeze_is_live_linked_and_nonphysical() -> None:
    review = (ROOT / "analysis/measurement_dut_cut_freeze_20261025.md").read_text(encoding="utf-8")
    assert "Dual-DUT measurement-cut freeze (2026-10-25)" in HANDOFF.read_text(encoding="utf-8")
    for required in (
        "functional measurement-cut freeze",
        "does **not** declare the present Chisel classes a fully equivalent",
        "single-record",
        "does not select a macro/wrapper/controller/numeric",
        "separate realization-preparation review",
    ):
        assert required in review
