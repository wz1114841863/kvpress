from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala"
CONTRACT = ROOT / "analysis/mr2_p3_array_boundary_contract.md"


def test_mr2_p3_array_boundary_keeps_storage_out_of_r3_control_wrapper() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    assert "final class RouteAP3StageArrayBoundary" in text
    assert 'override def desiredName: String = "route_a_p3_stage_array_boundary"' in text
    wrapper = text.split("final class RouteAM2P3Wrapper", 1)[1]
    assert "val stageStorage = Module(new RouteAP3StageArrayBoundary(p))" in wrapper
    assert "val stagePayload = Mem(" not in wrapper
    assert "val stageSidecar = Mem(" not in wrapper
    assert "stageStorage.io.payload_write_enable := true.B" in wrapper
    assert "stageStorage.io.sidecar_write_enable := true.B" in wrapper
    assert "stageStorage.io.payload_read_data" in wrapper


def test_mr2_p3_contract_records_array_only_and_retained_control_boundary() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    for required in (
        "array-only",
        "RouteAM2P3Wrapper` remains the sole owner",
        "p3_pending_fragment_in.fire",
        "p3_sidecar_bind_in.fire",
        "packed-write",
        "not a macro",
    ):
        assert required in text
