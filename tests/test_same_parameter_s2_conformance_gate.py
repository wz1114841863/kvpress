from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FULL_KV = ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/FullKVMeasurementDutSpec.scala"
ROUTE_A = ROOT / "hardware/route_a/chisel/src/test/scala/kvpress/routea/rtl2/RouteAPackedS2ReadPathSpec.scala"


def test_paired_s2_regressions_use_the_same_anchor_parameter_vector() -> None:
    full_kv = FULL_KV.read_text(encoding="utf-8")
    route_a = ROUTE_A.read_text(encoding="utf-8")
    for parameter in (
        "candidateOrdinalWidth = 4",
        "candidateIdWidth = 4",
        "r2CandidateSlotsPerClass = 2",
        "coreMemoryAddressRefWidth = 64",
        "coreMemoryFragmentCountWidth = 10",
        "coreMemoryFragmentIndexWidth = 9",
        "sourceDeliveryOpaqueWidth = 2",
        "transactionGroupTagWidth = 2",
        "p3StageGenerationWidth = 2",
    ):
        assert parameter in full_kv
        assert parameter.replace(" = ", "=") in route_a


def test_paired_s2_gate_does_not_claim_common_cost_cancellation() -> None:
    freeze = (ROOT / "analysis/successor_synthesis_source_port_filelist_freeze_20261028.md").read_text(encoding="utf-8")
    assert "cannot support payload or\nadapter cost cancellation" in freeze
    assert "one explicit 9-bit parameter vector" in freeze
