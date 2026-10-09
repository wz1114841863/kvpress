import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl3_0_replacement_owner import RTL30ReplacementOwnerError, load, validate, validate_hashes


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl3_0_replacement_owner_manifest.json"
VALIDATOR = ROOT / "tools/validate_rtl3_0_replacement_owner.py"


def payload():
    return load(MANIFEST)


def test_replacement_map_is_complete_but_does_not_authorize_behavioral_rtl3():
    manifest = payload()
    validate(manifest)
    assert manifest["disposition"]["rtl3_0_replacement_map_complete"] is True
    assert manifest["disposition"]["rtl3_behavioral_activation_authorized"] is False


def test_replacement_map_rejects_hidden_memory_authority_or_storage_owner_mac():
    manifest = payload()
    bad = copy.deepcopy(manifest)
    bad["replacement_records"][0]["replacement"]["authority"] = "authoritative"
    with pytest.raises(RTL30ReplacementOwnerError, match="memory environment authority"):
        validate(bad)
    bad = copy.deepcopy(manifest)
    bad["replacement_records"][2]["forbidden"].remove("hidden attention MAC in a storage owner")
    with pytest.raises(RTL30ReplacementOwnerError, match="storage owner"):
        validate(bad)


def test_stop_inventory_and_r4_observable_contract_cannot_drift():
    manifest = payload()
    bad = copy.deepcopy(manifest)
    bad["stop_for_review"].pop()
    with pytest.raises(RTL30ReplacementOwnerError, match="stop-for-review inventory"):
        validate(bad)
    bad = copy.deepcopy(manifest)
    bad["replacement_records"][3]["replacement"]["observable_contract"] = "unconstrained"
    with pytest.raises(RTL30ReplacementOwnerError, match="observable"):
        validate(bad)


def test_hashes_and_cli_are_reproducible():
    manifest = payload()
    validate_hashes(manifest, ROOT)
    bad = copy.deepcopy(manifest)
    bad["source_sha256"]["analysis/architecture_spec.md"] = "0" * 64
    with pytest.raises(RTL30ReplacementOwnerError, match="hash-bound"):
        validate_hashes(bad, ROOT)
    assert "--manifest" in subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
    assert "passed" in subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True).stdout
