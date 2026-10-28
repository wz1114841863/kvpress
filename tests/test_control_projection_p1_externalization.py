from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOP = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAMeasurementDut.scala"
GENERATOR = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/top/SynthesisControlProjectionGenerators.scala"
BOM_DELTA = ROOT / "analysis/control_projection_p1_bom_delta_20261028.json"


def test_route_a_projection_externalizes_only_named_functional_references() -> None:
    source = TOP.read_text(encoding="utf-8")
    assert "final class RouteAControlProjection" in source
    assert "externalizeFunctionalReferences = true" in source
    assert "RouteAR4ExternalProtocolAdapter" in source
    assert "if (externalizeFunctionalReferences)" in source
    for port in (
        "functional_sidecar_work_out",
        "functional_sidecar_payload_release_out",
        "functional_sidecar_registry_allocate_in",
        "functional_sidecar_registry_allocation_ack_out",
        "functional_sidecar_read_issue_in",
    ):
        assert f"val {port}" in source


def test_projection_generators_take_an_explicit_parameter_object() -> None:
    source = GENERATOR.read_text(encoding="utf-8")
    assert "def construct(p: RouteASkeletonParameters)" in source
    assert "testOnlyAnchor" not in source
    assert "RouteAKVSubsystemTop" not in source


def test_p1_bom_delta_keeps_every_externalized_cost_nonzero() -> None:
    delta = json.loads(BOM_DELTA.read_text(encoding="utf-8"))
    assert delta["status"] == "typed_externalization_implemented_no_cost_cancellation"
    rows = {row["id"]: row for row in delta["rows"]}
    assert rows["route_a_sidecar_externalization_adapter"]["cost_evidence_status"] == "unestimated_not_zero"
    assert rows["route_a_partial_provider_boundary"]["cost_evidence_status"] == "unestimated_not_zero"
    assert rows["route_a_r4_external_protocol_adapter"]["cost_evidence_status"] == "unestimated_not_zero"
