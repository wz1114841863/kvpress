from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_1a_manifest import RTL21AManifestError, load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis" / "rtl2_1a_retained_group_admission_manifest.json"
VALIDATOR = ROOT / "tools" / "validate_rtl2_1a_manifest.py"


def test_rtl2_1a_manifest_binds_one_group_owner_and_defers_publication():
    manifest = load_manifest(MANIFEST)
    validate_manifest(manifest)
    assert manifest["anchor"]["max_group_members"] == 64
    assert manifest["authority"]["adapter_authority_owner"] is False


def test_rtl2_1a_manifest_rejects_second_group_or_early_publication_scope():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["anchor"]["max_active_groups"] = 2
    with pytest.raises(RTL21AManifestError, match="one-packer"):
        validate_manifest(manifest)
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["inactive_or_deferred"].remove("metadata_publish_commit")
    with pytest.raises(RTL21AManifestError, match="deferred scope"):
        validate_manifest(manifest)


def test_rtl2_1a_validator_cli_supports_help_and_default_manifest():
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "RTL2.1a retained-group manifest passed" in result.stdout
