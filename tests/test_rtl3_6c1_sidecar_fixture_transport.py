from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.validate_rtl3_6c1_sidecar_fixture_transport import validate


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl3_6c1_sidecar_fixture_transport_manifest.json"
VALIDATOR = ROOT / "tools/validate_rtl3_6c1_sidecar_fixture_transport.py"


def test_manifest_validator_accepts_the_frozen_c1_owner_boundary() -> None:
    validate(MANIFEST, ROOT)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["fixture"]["sidecar_handle"] == "0xaa"
    assert manifest["fixture"]["records"] == ["0x900", "0x901"]


def test_validator_has_a_help_surface_and_passes_by_default() -> None:
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "PASS:" in result.stdout
