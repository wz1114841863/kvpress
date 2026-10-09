import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl3_2a_packed_read_association import (
    RTL32AssociationManifestError,
    load,
    validate,
    validate_hashes,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl3_2a_packed_read_association_manifest.json"
VALIDATOR = ROOT / "tools/validate_rtl3_2a_packed_read_association.py"


def payload():
    return load(MANIFEST)


def test_rtl32a_freezes_one_owner_and_exact_grant_inventory():
    manifest = payload()
    validate(manifest)
    assert manifest["association_owner"] == "route_a_packed_read_association_owner"
    assert manifest["resolved_rtl3_0_stop"] == "packed_read_association_owner"
    assert manifest["remaining_rtl3_0_stop"] == "partial_provider_query_position_contract blocks rtl3_5"


def test_rtl32a_rejects_event_replay_or_scheduler_scope():
    manifest = payload()
    bad = copy.deepcopy(manifest)
    bad["grant_interfaces"][1]["rule"] = "publication event cache"
    with pytest.raises(RTL32AssociationManifestError, match="live"):
        validate(bad)
    bad = copy.deepcopy(manifest)
    bad["forbidden"].remove("scheduler or page-source selection")
    with pytest.raises(RTL32AssociationManifestError, match="evidence boundary"):
        validate(bad)


def test_hashes_and_cli_are_reproducible():
    manifest = payload()
    validate_hashes(manifest, ROOT)
    bad = copy.deepcopy(manifest)
    bad["source_sha256"]["analysis/rtl3_2a_packed_read_association_contract.md"] = "0" * 64
    with pytest.raises(RTL32AssociationManifestError, match="hash-bound"):
        validate_hashes(bad, ROOT)
    assert "--manifest" in subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
    assert "passed" in subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True).stdout
