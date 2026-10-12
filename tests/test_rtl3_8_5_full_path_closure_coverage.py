from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_8_5_full_path_closure_coverage.py"


def test_rtl3_8_5_aggregate_manifest_validator_and_help_pass() -> None:
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, check=False, capture_output=True, text=True)
    assert help_result.returncode == 0
    assert "RTL3.8.5 aggregate coverage manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASS: RTL3.8.5" in result.stdout
