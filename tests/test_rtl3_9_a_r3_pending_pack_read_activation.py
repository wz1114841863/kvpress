from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_a_r3_pending_pack_read_activation.py"

def test_rtl3_9_a_manifest_validator_and_help_pass() -> None:
    assert subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, check=False, capture_output=True, text=True).returncode == 0
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASS: RTL3.9-A" in result.stdout
