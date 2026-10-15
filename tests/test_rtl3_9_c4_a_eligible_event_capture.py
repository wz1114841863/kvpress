from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_c4_a_eligible_event_capture.py"


def test_c4_a_binds_only_page_free_from_its_actual_release():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "binds only R5 page-free" in result.stdout
    assert "accepted old-PageRef release" in result.stdout
