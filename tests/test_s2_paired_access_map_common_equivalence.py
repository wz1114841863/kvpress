from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "analysis/s2_paired_access_map_common_equivalence_manifest.json"
WRAPPER = ROOT / "analysis/realization_preparation_wrapper_common_disposition_manifest.json"
ROUTE_A = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/common/RouteACommonSkeletons.scala"
FULL_KV = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/baseline/FullKVS2Completion.scala"


def test_paired_s2_payload_map_names_real_parent_to_child_paths() -> None:
    manifest = json.loads(MAP.read_text(encoding="utf-8"))
    assert manifest["status"] == "payload_access_role_mapped_not_cancellable"
    assert manifest["payload_access_roles"]["write"]["disposition"] == "logical_role_conformant"
    assert manifest["payload_access_roles"]["read"]["disposition"] == "logical_role_conformant"
    assert "source_selection_or_authority" in manifest["payload_access_roles"]["array_child_exclusions"]

    route_a = ROUTE_A.read_text(encoding="utf-8")
    full_kv = FULL_KV.read_text(encoding="utf-8")
    for required in (
        "final class RouteAS2PayloadSidecarArrayBoundary",
        "storage.io.payload_write_ack.fire",
        "storage.io.payload_read_rsp.fire",
        "slotState(payloadReadSlot) === StateReady",
    ):
        assert required in route_a
    for required in (
        "final class FullKVS2PayloadArrayBoundary",
        "storage.io.write_ack.fire",
        "storage.io.read_rsp.fire",
        "state(payloadReadSlot) === ready",
    ):
        assert required in full_kv


def test_paired_s2_map_fails_closed_on_common_cost_cancellation() -> None:
    manifest = json.loads(MAP.read_text(encoding="utf-8"))
    assert manifest["common_equivalence_disposition"] == (
        "not_cancellable_pending_same_parameter_shell_and_paired_conformance"
    )
    assert manifest["non_equivalences"]["route_a_sidecar"] == "route_a_incremental_unestimated_not_zero"
    assert "matching_9_bit_payload_geometry_in_both_synthesis_shells" in manifest[
        "required_before_any_payload_cancellation"
    ]
    assert "current_S2_cost_cancellation" in manifest["prohibited_conclusions"]

    wrapper = json.loads(WRAPPER.read_text(encoding="utf-8"))
    s2 = next(row for row in wrapper["wrapper_contracts"] if row["id"] == "s2_payload_access_v1")
    assert s2["paired_access_map"] == "analysis/s2_paired_access_map_common_equivalence_disposition.md"
    assert wrapper["next_gate"].startswith(
        "dual synthesis-top input inventory prepared at "
        "analysis/dual_synthesis_top_input_package_20261028.json"
    )
    assert "projection-generator/external-reference externalization" in wrapper["next_gate"]
