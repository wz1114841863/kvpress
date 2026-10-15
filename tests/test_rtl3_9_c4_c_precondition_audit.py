from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_c4_c_precondition_audit.py"


def test_c4_c_keeps_negative_event_prefixes_fail_closed():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "allowed-prefix/forbidden-suffix event criteria" in result.stdout
