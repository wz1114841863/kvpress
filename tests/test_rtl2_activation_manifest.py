from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_activation_manifest import RTL2ActivationManifestError, load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis" / "rtl2_0_activation_manifest.json"
VALIDATOR = ROOT / "tools" / "validate_rtl2_activation_manifest.py"


def test_rtl2_0_inventory_names_all_required_events_and_does_not_false_pass():
    manifest = load_manifest(MANIFEST)
    validate_manifest(manifest)
    assert len(manifest["event_records"]) == 14
    assert len(manifest["carrier_records"]) == 20
    assert manifest["review_disposition"]["rtl2_0_pass"] is False
    assert manifest["scoreboard_schema"]["state"] == "required_before_first_behavioral_activation"


def test_write_terminal_and_metadata_commit_cannot_be_collapsed_into_one_untyped_path():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    write = next(record for record in manifest["event_records"] if record["event"] == "write_commit")
    write["carrier_ids"] = ["r1_to_r3_packed_write_terminal"]
    with pytest.raises(RTL2ActivationManifestError, match="distinguish R3 payload and R5 descriptor terminals"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    publish = next(record for record in manifest["event_records"] if record["event"] == "metadata_publish_commit")
    publish["carrier_ids"] = ["r3_publication_ack_to_r6"]
    with pytest.raises(RTL2ActivationManifestError, match="retain both frozen nested outputs"):
        validate_manifest(manifest)


def test_inert_carrier_without_amendment_and_premature_pass_are_rejected():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    carrier = next(record for record in manifest["carrier_records"] if record["id"] == "admission_to_r3_p3_claim")
    carrier["amendment_id"] = None
    with pytest.raises(RTL2ActivationManifestError, match="inactive carrier lacks an explicit amendment"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["review_disposition"]["rtl2_0_pass"] = True
    with pytest.raises(RTL2ActivationManifestError, match="must not pass"):
        validate_manifest(manifest)


def test_validator_cli_supports_help_and_default_manifest():
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "RTL2.0 activation manifest passed" in result.stdout
