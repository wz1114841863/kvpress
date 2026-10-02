from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_typed_delivery_router_manifest import (
    RTL2TypedDeliveryRouterError,
    load_manifest,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl2_0d_typed_delivery_router_manifest.json"
VALIDATOR = ROOT / "tools/validate_rtl2_typed_delivery_router_manifest.py"


def test_exact_read_fragment_and_write_terminal_endpoints_are_frozen():
    manifest = load_manifest(MANIFEST)
    validate_manifest(manifest)
    assert {record["candidate_class"] for record in manifest["read_targets"]} == {
        "pack_read",
        "s2_full",
        "s2_packed",
        "direct_pending",
    }
    assert {record["candidate_class"] for record in manifest["write_targets"]} == {
        "pack_write",
        "descriptor_maintenance",
    }
    assert "data_512b" in manifest["typed_read_fragment"]["fields"]


def test_router_cannot_drop_read_data_or_collapse_write_durability():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["typed_read_fragment"]["fields"].remove("data_512b")
    with pytest.raises(RTL2TypedDeliveryRouterError, match="complete R1 data fields"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["write_targets"][0]["durable_rule"] = "status==OK"
    with pytest.raises(RTL2TypedDeliveryRouterError, match="write durable rule differs"):
        validate_manifest(manifest)


def test_stale_rejection_and_s2_sidecar_distinction_are_required():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["registry_resolution"]["reject_without_endpoint_mutation"].remove("stale_epoch")
    with pytest.raises(RTL2TypedDeliveryRouterError, match="stale rejection"):
        validate_manifest(manifest)

    manifest = copy.deepcopy(load_manifest(MANIFEST))
    next(record for record in manifest["read_targets"] if record["candidate_class"] == "s2_packed")["requires_sidecar"] = False
    with pytest.raises(RTL2TypedDeliveryRouterError, match="S2 sidecar distinction"):
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
    assert "RTL2.0d typed delivery-router manifest passed" in result.stdout
