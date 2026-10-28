from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "analysis/paired_control_projection_profile_20261028.json"
SOURCE = ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/params/RouteASynthesisControlProjectionProfile.scala"


def test_profile_is_complete_bounded_and_not_a_test_anchor() -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert profile["status"] == "bounded_control_profile_selected_not_physical"
    assert profile["parameters"]["r5AllocatorEntries"] == 146880
    assert profile["parameters"]["r5StreamSlots"] == 288
    assert profile["parameters"]["coreMemoryFragmentIndexWidth"] == 9
    assert profile["parameters"]["coreMemoryFragmentCountWidth"] == 10
    assert profile["parameters"]["sourceDeliveryOpaqueWidth"] == 4
    assert "DC" in profile["nonclaims"][0]


def test_scala_profile_has_no_test_only_encoding_dependency() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "object RouteASynthesisControlProjectionProfile" in source
    assert "RouteAR6Encoding.testOnlyAnchor" not in source
    assert "r5AllocatorEntries = 146880" in source
    assert "r5StreamSlots = 288" in source
