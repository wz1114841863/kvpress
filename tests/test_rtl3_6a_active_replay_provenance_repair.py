from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl3_6a_active_replay_provenance_repair import (
    RTL36AProvenanceRepairError,
    load,
    validate,
    validate_hashes,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl3_6a_active_replay_provenance_repair_manifest.json"
VALIDATOR = ROOT / "tools" / "validate_rtl3_6a_active_replay_provenance_repair.py"


def test_active_bindings_are_hash_current_without_changing_event_semantics():
    manifest = load(MANIFEST)
    validate(manifest, ROOT)
    assert manifest["disposition"]["active_replay_provenance_repaired"] is True
    assert manifest["disposition"]["rtl3_functional_realization_complete"] is False


def test_repair_rejects_contract_expansion_and_stale_active_binding():
    manifest = load(MANIFEST)
    bad = copy.deepcopy(manifest)
    bad["audit"]["analysis/rtl2_4_3_attention_terminal_scoreboard_binding.json"]["semantic_contract_changed"] = True
    with pytest.raises(RTL36AProvenanceRepairError, match="audit"):
        validate(bad, ROOT)
    bad = copy.deepcopy(manifest)
    bad["disposition"]["rtl3_functional_realization_complete"] = True
    with pytest.raises(RTL36AProvenanceRepairError, match="no-PASS"):
        validate(bad, ROOT)
    bad = copy.deepcopy(manifest)
    bad["source_sha256"]["analysis/rtl3_6a_active_replay_provenance_repair_contract.md"] = "0" * 64
    with pytest.raises(RTL36AProvenanceRepairError, match="hash-bound"):
        validate_hashes(bad, ROOT)


def test_rtl3_6a_validator_help_and_default_pass():
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "PASS: RTL3.6-A" in result.stdout
