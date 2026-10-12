from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_a1_r3_materialization_ingress_exclusion.py"


def test_rtl3_9_a1_manifest_validator_and_help_pass() -> None:
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, check=False, capture_output=True, text=True)
    assert help_result.returncode == 0
    assert "RTL3.9-A1" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASS: RTL3.9-A1" in result.stdout
