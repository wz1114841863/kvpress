from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl_entry_manifest import RTLEntryManifestError, load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis" / "rtl_entry_interface_manifest.json"
VALIDATOR = ROOT / "tools" / "validate_rtl_entry_interface_manifest.py"


def test_hierarchy_owner_manifest_is_valid_and_ports_are_explicitly_pending():
    manifest = load_manifest(MANIFEST)
    validate_manifest(manifest)
    assert manifest["interface_records"]["signals"] == []
    assert manifest["interface_records"]["status"] == "ports_pending_gate_rtl0_step_2"


def test_duplicate_owner_resource_is_rejected():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["owner_claims"].append(copy.deepcopy(manifest["owner_claims"][0]))
    with pytest.raises(RTLEntryManifestError, match="duplicate owner resource"):
        validate_manifest(manifest)


def test_missing_frozen_module_is_rejected():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["hierarchy"]["modules"] = manifest["hierarchy"]["modules"][1:]
    with pytest.raises(RTLEntryManifestError, match="module inventory differs"):
        validate_manifest(manifest)


def test_validator_cli_supports_help_and_default_manifest():
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "manifest passed" in result.stdout
