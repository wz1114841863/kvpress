from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_2_0_delivery_context_reconciliation import (
    RTL22DeliveryContextReconciliationError,
    load_manifest,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis" / "rtl2_2_0_delivery_context_reconciliation_manifest.json"
VALIDATOR = ROOT / "tools" / "validate_rtl2_2_0_delivery_context_reconciliation.py"


def test_reconciliation_binds_historical_inputs_and_defers_storage_behavior() -> None:
    manifest = load_manifest(MANIFEST)
    validate_manifest(manifest, ROOT)
    assert manifest["historical_annotation_correction"]["reconciled_activation"] == "rtl2_2"
    assert manifest["scoreboard_binding"]["current_state"] == "schema_declared_adapter_behavior_deferred"


def test_reconciliation_rejects_historical_rewrite_or_early_s2_direct_activation() -> None:
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["historical_annotation_correction"]["historical_artifact_mutation"] = True
    with pytest.raises(RTL22DeliveryContextReconciliationError, match="historical artifact"):
        validate_manifest(manifest, ROOT)
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    direct = next(item for item in manifest["producer_activation_boundary"] if item["logical_class"] == "direct_pending")
    direct["activation"] = "rtl2_2"
    with pytest.raises(RTL22DeliveryContextReconciliationError, match="S2/direct deferral"):
        validate_manifest(manifest, ROOT)


def test_validator_cli_supports_help_and_default_manifest() -> None:
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "RTL2.2.0 delivery-context reconciliation manifest passed" in result.stdout
