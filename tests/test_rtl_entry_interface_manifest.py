from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl_entry_manifest import RTLEntryManifestError, load_manifest, validate_manifest, validate_markdown_matrix


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis" / "rtl_entry_interface_manifest.json"
VALIDATOR = ROOT / "tools" / "validate_rtl_entry_interface_manifest.py"
MATRIX = ROOT / "analysis" / "rtl_entry_port_parameter_contract.md"


def test_ports_bound_manifest_is_valid_and_matches_the_markdown_matrix():
    manifest = load_manifest(MANIFEST)
    validate_manifest(manifest, require_interface_signals=True)
    validate_markdown_matrix(manifest, MATRIX)
    assert len(manifest["interface_records"]["signals"]) == 27
    assert manifest["interface_records"]["status"] == "complete_gate_rtl0_step_2"


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


def test_unknown_parameter_source_is_rejected():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["interface_records"]["signals"][0]["fields"][0]["parameter_source"] = "analysis/not_a_contract.md"
    with pytest.raises(RTLEntryManifestError, match="parameter source does not exist"):
        validate_manifest(manifest)


def test_markdown_drift_is_rejected(tmp_path: Path):
    manifest = load_manifest(MANIFEST)
    stale = tmp_path / "matrix.md"
    stale.write_text(MATRIX.read_text(encoding="utf-8").replace("if_r1_core_mem_rsp", "if_stale"), encoding="utf-8")
    with pytest.raises(RTLEntryManifestError, match="Markdown interface matrix differs"):
        validate_markdown_matrix(manifest, stale)


def test_validator_cli_supports_help_and_default_manifest():
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout and "--markdown-matrix" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "manifest passed" in result.stdout
