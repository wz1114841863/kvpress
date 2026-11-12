from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala"


def test_mr2_p3_array_boundary_keeps_storage_out_of_r3_control_wrapper() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    assert "final class RouteAP3StageArrayBoundary" in text
    assert 'override def desiredName: String = "route_a_p3_stage_array_boundary"' in text
    wrapper = text.split("final class RouteAM2P3Wrapper", 1)[1]
    assert "val stageStorage = Module(new RouteAP3StageArrayBoundary(p))" in wrapper
    assert "val stagePayload = Mem(" not in wrapper
    assert "val stageSidecar = Mem(" not in wrapper
    assert "stageStorage.io.payload_write_req.valid := true.B" in wrapper
    assert "stageStorage.io.payload_write_ack.ready := payloadWritePending" in wrapper
    assert "stageStorage.io.sidecar_write_req.valid := true.B" in wrapper
    assert "stageStorage.io.sidecar_write_ack.ready := sidecarWritePending" in wrapper
    assert "stageStorage.io.payload_read_req.valid := packedWriteState === WriteReadRequest" in wrapper
    assert "stageStorage.io.payload_read_rsp.ready := packedWriteState === WriteReadResponse" in wrapper
    assert "P3 payload read response must match the parent-selected packed-write fragment" in wrapper
    assert "P3 payload write acknowledgement must match the parent-selected request" in wrapper
