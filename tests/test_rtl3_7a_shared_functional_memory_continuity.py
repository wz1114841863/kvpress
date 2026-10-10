from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.validate_rtl3_7a_shared_functional_memory_continuity import validate


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl3_7a_shared_functional_memory_continuity_manifest.json"
VALIDATOR = ROOT / "tools/validate_rtl3_7a_shared_functional_memory_continuity.py"


def test_manifest_preserves_shared_store_and_open_owner_boundaries() -> None:
    validate(MANIFEST, ROOT)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["boundary"]["store_owner"] == "testbench_route_a_functional_memory_store"
    assert "not a deployed physical address format" in manifest["boundary"]["object_key"]
    assert manifest["disposition"]["rtl3_functional_realization_complete"] is False


def test_validator_has_help_and_default_pass() -> None:
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "PASS:" in result.stdout
