from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_c4_p0_event_scoreboard_provenance.py"


def test_c4_p0_replays_all_frozen_event_scoreboard_prerequisites():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "4 frozen event/scoreboard records" in result.stdout
