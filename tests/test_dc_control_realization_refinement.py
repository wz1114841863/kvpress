from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAMetadataAdmissionBridge.scala"
INTERFACES = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/interfaces/RouteAInterfaces.scala"
M2 = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala"
MEASUREMENT_DUT = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAMeasurementDut.scala"
MEASUREMENT_R3_SPEC = ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/RouteAMeasurementDutR3Spec.scala"
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


def test_functional_measurement_dormant_r5_service_is_fully_driven() -> None:
    dut = MEASUREMENT_DUT.read_text(encoding="utf-8")
    assert "inactive(io.functional_r5_descriptor_service.request)" in dut
    assert "io.functional_r5_descriptor_service.response.ready := false.B" in dut


def test_r3_simulator_root_keeps_the_complete_production_dut_child() -> None:
    spec = MEASUREMENT_R3_SPEC.read_text(encoding="utf-8")
    assert "final class RouteAMeasurementDutR3Harness" in spec
    assert "val dut = Module(new RouteAMeasurementDut(p))" in spec
    assert "simulate(new RouteAMeasurementDutR3Harness(p))" in spec
    assert "functional_sidecar_registry_allocate_in" not in spec.split("val io = IO", 1)[1].split("})", 1)[0]
