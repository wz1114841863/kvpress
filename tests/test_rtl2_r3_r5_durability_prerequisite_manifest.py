from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_r3_r5_durability_prerequisite_manifest import (
    RTL2R3R5DurabilityPrerequisiteError,
    load_manifest,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl2_0e_r3_r5_durability_prerequisite_manifest.json"
VALIDATOR = ROOT / "tools/validate_rtl2_r3_r5_durability_prerequisite_manifest.py"


def test_exact_r5_to_r3_durability_result_and_atomic_boundary_are_frozen():
    manifest = load_manifest(MANIFEST)
    validate_manifest(manifest)
    assert manifest["result_type"]["producer"] == "route_a_page_manager"
    assert manifest["result_type"]["consumer"] == "route_a_m2_p3_wrapper"
    assert manifest["logical_operation_mask"]["width_bits"] == 2


def test_success_cannot_omit_tail_dependency_or_become_visibility():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["logical_operation_mask"]["bits"][1]["required_rule"] = "optional"
    with pytest.raises(RTL2R3R5DurabilityPrerequisiteError, match="tail-link requirement differs"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["success_rule"]["effect"] = "descriptor visible"
    with pytest.raises(RTL2R3R5DurabilityPrerequisiteError, match="success rule differs"):
        validate_manifest(manifest)


def test_fault_stale_and_ready_low_rules_cannot_be_weakened():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["fault_rule"]["one_way_rule"] = "fault may recover"
    with pytest.raises(RTL2R3R5DurabilityPrerequisiteError, match="fault rule differs"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["rejection_and_stall"]["reject_without_mutation"].remove("stale page generation")
    with pytest.raises(RTL2R3R5DurabilityPrerequisiteError, match="stale/mismatch rejection"):
        validate_manifest(manifest)


def test_validator_cli_supports_help_and_default_manifest():
    help_result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "--manifest" in help_result.stdout
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "RTL2.0e R3/R5 durability-prerequisite manifest passed" in result.stdout
