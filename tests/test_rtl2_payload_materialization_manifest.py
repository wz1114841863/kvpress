from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_payload_materialization_manifest import (
    RTL2PayloadMaterializationError,
    load_manifest,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis" / "rtl2_0a_payload_materialization_manifest.json"
VALIDATOR = ROOT / "tools" / "validate_rtl2_payload_materialization_manifest.py"


def test_payload_interface_preserves_the_frozen_anchor_and_sole_hot_owner():
    manifest = load_manifest(MANIFEST)
    validate_manifest(manifest)
    assert manifest["anchor_payload_contract"]["fragments_per_record"] == 8
    assert manifest["required_follow_on"]["behavioral_phase"] == "rtl2_1a"


def test_payload_fragment_cannot_be_reinterpreted_as_authority_or_address():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    ingress = next(record for record in manifest["transactions"] if record["id"] == "frontend_hot_payload_fragment")
    ingress["authority_effect"] = "hot_to_pending"
    with pytest.raises(RTL2PayloadMaterializationError, match="may not transfer authority"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["anchor_payload_contract"]["forbidden_interpretations"].remove("payload_ref is a physical address")
    with pytest.raises(RTL2PayloadMaterializationError, match="exclude address/macro interpretation"):
        validate_manifest(manifest)


def test_maturity_egress_requires_group_identity_and_materialization_ordering():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    response = next(record for record in manifest["transactions"] if record["id"] == "hot_mature_payload_fragment")
    response["fields"].remove("group_member_ordinal")
    with pytest.raises(RTL2PayloadMaterializationError, match="identity field omitted"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["environment_assumptions"] = ["payload is generally available"]
    with pytest.raises(RTL2PayloadMaterializationError, match="materialization-before-maturity"):
        validate_manifest(manifest)


def test_validator_cli_supports_help_and_default_manifest():
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "RTL2.0a payload-materialization manifest passed" in result.stdout
