from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_r4_result_stub_provider_manifest import (
    RTL2R4ResultStubProviderError,
    load_manifest,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl2_0g_r4_result_stub_provider_manifest.json"
VALIDATOR = ROOT / "tools/validate_rtl2_r4_result_stub_provider_manifest.py"


def test_r4_stub_is_testbench_only_and_exactly_maps_success_or_fault():
    manifest = load_manifest(MANIFEST)
    validate_manifest(manifest)
    assert manifest["provider"]["classification"] == "testbench_only_verification_endpoint"
    assert manifest["scenario"]["dispositions"] == ["success", "numeric_fault"]


def test_stub_cannot_create_terminal_or_numeric_implementation_claim():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["provider"]["forbidden"].remove("outward terminal bypass")
    with pytest.raises(RTL2R4ResultStubProviderError, match="prohibitions incomplete"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["provider"]["does_not_own"].remove("R4 numeric arithmetic or binary32 validation")
    with pytest.raises(RTL2R4ResultStubProviderError, match="ownership boundary incomplete"):
        validate_manifest(manifest)


def test_mutual_exclusion_reset_and_ready_low_rules_cannot_be_weakened():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["mutual_exclusion_and_lifetime"].remove("success and numeric_fault valid signals are never asserted together")
    with pytest.raises(RTL2R4ResultStubProviderError, match="lifetime rule missing"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["rejection_and_stall"]["ready_low_rule"] = "may change while stalled"
    with pytest.raises(RTL2R4ResultStubProviderError, match="ready-low nonmutation differs"):
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
    assert "RTL2.0g R4 result-stub provider manifest passed" in result.stdout
