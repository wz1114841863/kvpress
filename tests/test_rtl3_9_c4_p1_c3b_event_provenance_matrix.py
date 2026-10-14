from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_c4_p1_c3b_event_provenance_matrix.py"


def test_c4_p1_matrix_is_complete_and_fail_closed():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "14 immutable event records" in result.stdout
    assert "no capture is authorized" in result.stdout
