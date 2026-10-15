from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_c4_b_event_replay.py"


def test_c4_b_is_host_only_and_bounded():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "four accepted events" in result.stdout
    assert "two-cycle legal stalls" in result.stdout
