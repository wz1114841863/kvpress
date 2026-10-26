from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala"
CONTRACT = ROOT / "analysis/mr2_r5_availability_array_boundary_contract.md"


def test_mr2_r5_availability_state_is_isolated_from_page_manager_control() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    assert "final class RouteAR5AvailabilityArrayBoundary" in text
    assert 'override def desiredName: String = "route_a_r5_availability_array_boundary"' in text
    boundary, page_manager = text.split("final class RouteAPageManager", 1)
    assert "val allocated = RegInit(VecInit(Seq.fill(entries)(false.B)))" in boundary
    assert "val generations = RegInit(VecInit(Seq.fill(entries)" in boundary
    assert "val availabilityStorage = Module(new RouteAR5AvailabilityArrayBoundary(p))" in page_manager
    assert "val allocated = RegInit(VecInit(Seq.fill(p.r5AllocatorEntries)(false.B)))" not in page_manager
    assert "val generations = RegInit(VecInit(Seq.fill(p.r5AllocatorEntries)" not in page_manager
    assert "availabilityStorage.io.availability_lookup_req.valid := scanAllowed" in page_manager
    assert "availabilityStorage.io.allocation_update.valid := true.B" in page_manager
    assert "availabilityStorage.io.reclaim_generation_update.valid := true.B" in page_manager
    assert "availabilityStorage.io.allocation_update_ack.valid" in page_manager
    assert "availabilityStorage.io.reclaim_generation_update_ack.valid" in page_manager
    assert "allocated_view" not in page_manager
    assert "generation_view" not in page_manager


def test_mr2_r5_contract_records_array_only_and_retained_control_boundary() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    for required in (
        "array-only",
        "RouteAPageManager` remains the unique owner",
        "page_allocation_req_in.fire",
        "reclaim_delivery_in.fire",
        "external descriptor-service proxy",
        "explicitly not an R5 local",
        "SRAM-array proxy",
        "must first be replaced by a production owner",
    ):
        assert required in text
