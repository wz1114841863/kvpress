from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala"
CONTRACT = ROOT / "analysis/mr2_m2_array_boundary_contract.md"


def test_mr2_m2_entry_arrays_are_owned_only_by_the_named_boundary() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    assert "final class RouteAM2EntryArrayBoundary" in text
    assert 'override def desiredName: String = "route_a_m2_entry_array_boundary"' in text
    boundary, owner = text.split("final class RouteAM2ProductionControlOwner", 1)
    for required in (
        "val headReplicaA = RegInit",
        "val headReplicaB = RegInit",
        "val span = RegInit",
        "val publication_commit = Input(Valid",
        "val handoff_release = Input(Valid",
        "assert(headReplicaA(index).asUInt === headReplicaB(index).asUInt)",
    ):
        assert required in boundary
    assert "val entryStorage = Module(new RouteAM2EntryArrayBoundary(p))" in owner
    assert "val metadataHeadReplicaA = RegInit" not in owner
    assert "val metadataHeadReplicaB = RegInit" not in owner
    assert "val metadataSpan = RegInit" not in owner
    assert "entryStorage.io.publication_commit.valid := true.B" in owner
    assert "entryStorage.io.handoff_release.valid := true.B" in owner


def test_mr2_m2_contract_records_array_only_and_retained_control_boundary() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    for required in (
        "array-only",
        "RouteAM2EntryArrayBoundary",
        "288 logical head keys",
        "614 logical",
        "metadata_publish_commit",
        "post-R6 all-member handoff",
        "metadataSlotOccupied",
        "metadataSlotGeneration",
        "not an SRAM macro",
    ):
        assert required in text
