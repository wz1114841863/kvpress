from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/baseline/FullKVS2Completion.scala"
TOP = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/top/FullKVMeasurementDut.scala"


def test_full_kv_s2_payload_wrapper_keeps_parent_ownership() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    boundary, parent = text.split("final class FullKVS2GqaSourceWrapper", 1)
    assert "final class FullKVS2PayloadArrayBoundary" in boundary
    assert 'override def desiredName: String = "full_kv_s2_payload_array_boundary"' in boundary
    assert "val payload = Mem(slots * fragmentsPerSlot" in boundary
    for required in (
        "val storage = Module(new FullKVS2PayloadArrayBoundary(p))",
        "payloadWriteAwaitAck",
        "payloadReadOutstanding",
        "storage.io.write_ack",
        "storage.io.read_rsp",
        "state(payloadReadSlot) === ready",
        "source_release_out",
        "fault_terminal_out",
    ):
        assert required in parent
    assert "val payload = Mem(" not in parent


def test_full_kv_measurement_top_uses_real_payload_access_boundary() -> None:
    text = TOP.read_text(encoding="utf-8")
    assert "val full_kv_payload_read_req_in" in text
    assert "val full_kv_payload_read_rsp_out" in text
    assert "s2.io.payload_read_req_in <> io.full_kv_payload_read_req_in" in text
    assert "io.full_kv_payload_read_rsp_out <> s2.io.payload_read_rsp_out" in text
