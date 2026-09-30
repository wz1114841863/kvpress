from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl1_i_integration_manifest import RTL1IManifestError, load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis" / "rtl1_i_interface_manifest.json"
VALIDATOR = ROOT / "tools" / "validate_rtl1_i_integration_manifest.py"


def test_i0_manifest_freezes_all_cross_owner_associations_without_behavioral_rtl():
    manifest = load_manifest(MANIFEST)
    validate_manifest(manifest)
    assert manifest["hierarchy_control"]["rtl1_i0_behavioral_modules_added"] is False
    assert len(manifest["top_inert_inventory"]) == 19
    assert len(manifest["association_records"]) == 6


def test_publication_membership_cannot_degrade_to_a_contiguous_span():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    publication = next(record for record in manifest["association_records"] if record["id"] == "publication_membership_and_authority_observation")
    publication["identity_fields"].remove("entry_id")
    with pytest.raises(RTL1IManifestError, match="per-record entry association"):
        validate_manifest(manifest)


def test_r4_sideband_cannot_modify_the_frozen_packet_header():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    r4 = next(record for record in manifest["association_records"] if record["id"] == "r4_source_instance_sideband")
    r4["forbidden"].remove("modify frozen 128-bit R4 header")
    with pytest.raises(RTL1IManifestError, match="preserve the frozen packet header"):
        validate_manifest(manifest)


def test_validator_cli_supports_help_and_default_manifest():
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "integration manifest passed" in result.stdout
