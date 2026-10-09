from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools" / "validate_rtl3_5c_cross_language_packet_binding.py"


def test_rtl3_5c_manifest_validator_and_help_pass():
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "PASS: RTL3.5-C" in result.stdout
