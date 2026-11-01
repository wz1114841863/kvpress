from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAMetadataAdmissionBridge.scala"
INTERFACES = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/interfaces/RouteAInterfaces.scala"
M2 = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala"
DIAGNOSIS = ROOT / "analysis/dc_control_realization_diagnosis_20261101.md"


def test_metadata_admission_keeps_group_summary_not_duplicate_binding_ledger() -> None:
    bridge = BRIDGE.read_text(encoding="utf-8")
    assert "val groupMembers = Reg" not in bridge
    assert "val groupMappingRef = Reg" in bridge
    assert "val groupMappingOwner = Reg" in bridge
    assert "groupMappingRef(layer) === binding.m2_group_opaque_address_ref" in bridge
    assert "groupMappingOwner(layer) === binding.m2_group_owner" in bridge
    assert "groupMappingRef(preparationLayer) === preparation.opaque_address_ref" in bridge
    assert "groupMappingOwner(preparationLayer) === preparation.owner" in bridge


def test_m2_operand_and_owner_validate_only_consumed_group_facts() -> None:
    interfaces = INTERFACES.read_text(encoding="utf-8")
    operand = interfaces.split("final class MetadataAppendOperand", 1)[1].split("}\n", 1)[0]
    assert "val member_mask = UInt(64.W)" in operand
    assert "val opaque_mapping_ref" in operand
    assert "val mapping_owner" in operand
    assert "val members = Vec" not in operand

    m2 = M2.read_text(encoding="utf-8")
    assert "operand.member_mask === expectedMemberMask(operand.valid_records)" in m2
    assert "operand.members(" not in m2


def test_diagnosis_preserves_scope_and_cost_boundary() -> None:
    diagnosis = DIAGNOSIS.read_text(encoding="utf-8")
    for required in (
        "645,012 sequential bits",
        "R3/P3 membership owner",
        "not a zero-cost memory proxy",
        "same-constraint successor DC run",
        "not a PPA result",
    ):
        assert required in diagnosis
