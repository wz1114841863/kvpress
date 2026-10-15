from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_c4_c_negative_event_witness.py"


def test_c4_c_has_only_negative_host_replay_rules():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "stale/mismatch" in result.stdout
    assert "numeric-fault" in result.stdout
    assert "reset" in result.stdout
