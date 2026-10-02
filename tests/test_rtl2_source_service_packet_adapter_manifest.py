from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_source_service_packet_adapter_manifest import (
    RTL2SourceServicePacketAdapterError,
    load_manifest,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl2_0f_source_service_packet_adapter_manifest.json"
VALIDATOR = ROOT / "tools/validate_rtl2_source_service_packet_adapter_manifest.py"


def test_exact_source_owner_plan_and_r4_packet_boundaries_are_frozen():
    manifest = load_manifest(MANIFEST)
    validate_manifest(manifest)
    assert manifest["canonical_source_order"]["ordered_kinds"] == ["hot", "pending", "packed"]
    assert len(manifest["source_owners"]) == 3


def test_adapter_cannot_reorder_or_create_plan_or_absent_packet():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["canonical_source_order"]["ordered_kinds"] = ["pending", "hot", "packed"]
    with pytest.raises(RTL2SourceServicePacketAdapterError, match="canonical source order differs"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["accepted_plan_copy"]["forbidden"].remove("adapter plan creation")
    with pytest.raises(RTL2SourceServicePacketAdapterError, match="accepted plan boundary differs"):
        validate_manifest(manifest)


def test_packet_structure_and_commit_release_owners_cannot_be_weakened():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["source_packet_ingress"]["offer_rule"] = "any source may offer"
    with pytest.raises(RTL2SourceServicePacketAdapterError, match="source offer presence/fragment rule differs"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["commit_release_association"]["rule"] = "adapter consumes ConsumerPartialCommit"
    with pytest.raises(RTL2SourceServicePacketAdapterError, match="commit/release owner boundary differs"):
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
    assert "RTL2.0f source-service packet-adapter manifest passed" in result.stdout
