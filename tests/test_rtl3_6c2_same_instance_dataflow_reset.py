from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.validate_rtl3_6c2_same_instance_dataflow_reset import validate


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl3_6c2_same_instance_dataflow_reset_manifest.json"
VALIDATOR = ROOT / "tools/validate_rtl3_6c2_same_instance_dataflow_reset.py"


def test_manifest_preserves_testbench_only_two_r1_boundary() -> None:
    validate(MANIFEST, ROOT)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["boundary"]["source_read"].startswith("RTL3.2 association owner")
    assert manifest["disposition"]["rtl3_functional_realization_complete"] is False


def test_validator_has_help_and_default_pass() -> None:
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "PASS:" in result.stdout
