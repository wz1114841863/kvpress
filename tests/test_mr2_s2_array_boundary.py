from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/common/RouteACommonSkeletons.scala"
CONTRACT = ROOT / "analysis/mr2_s2_array_boundary_contract.md"


def test_mr2_s2_array_boundary_keeps_arrays_out_of_s2_control_wrapper() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    assert "final class RouteAS2PayloadSidecarArrayBoundary" in text
    assert 'override def desiredName: String = "route_a_s2_payload_sidecar_array_boundary"' in text
    boundary, wrapper = text.split("final class RouteAS2GqaSourceWrapper", 1)
    assert "val payload = Mem(slots * 512" in boundary
    assert "val sidecar = Mem(slots * 64" in boundary
    assert "val storage = Module(new RouteAS2PayloadSidecarArrayBoundary(p))" in wrapper
    assert "val payloadStore = Mem(" not in wrapper
    assert "val sidecarStore = Mem(" not in wrapper
    for required in (
        "class S2PayloadArrayWriteRequest",
        "class S2PayloadArrayWriteAck",
        "class S2PayloadArrayReadRequest",
        "class S2PayloadArrayReadResponse",
        "class S2SidecarArrayWriteRequest",
        "class S2SidecarArrayWriteAck",
        "class S2SidecarArrayReadRequest",
        "class S2SidecarArrayReadResponse",
        "storage.io.payload_write_req",
        "storage.io.payload_write_ack",
        "storage.io.payload_read_req",
        "storage.io.payload_read_rsp",
        "storage.io.sidecar_write_req",
        "storage.io.sidecar_write_ack",
        "storage.io.sidecar_read_req",
        "storage.io.sidecar_read_rsp",
        "payloadWriteAwaitAck",
        "sidecarWriteAwaitAck",
        "payloadReadOutstanding",
        "sidecarReadOutstanding",
    ):
        assert required in text
    assert "storage.io.payload_write_enable" not in wrapper
    assert "storage.io.sidecar_write_enable" not in wrapper


def test_mr2_s2_contract_records_array_only_and_retained_control_boundary() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    for required in (
        "array-only",
        "RouteAS2GqaSourceWrapper`",
        "s2_payload_fragment_in.fire",
        "s2_sidecar_fragment_in.fire",
        "s2_payload_read_req_in.fire",
        "s2_sidecar_read_req_in.fire",
        "not an SRAM macro",
    ):
        assert required in text
