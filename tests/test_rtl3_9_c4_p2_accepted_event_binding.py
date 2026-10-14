from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_c4_p2_accepted_event_binding.py"


def test_c4_p2_is_narrow_and_fail_closed():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "exactly three selected accepted events" in result.stdout
    assert "remain excluded" in result.stdout
