from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_c4_a_precondition_audit.py"


def test_c4_a_remains_fail_closed_for_descriptor_fields():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "authorizes only complete terminal/page-free/retire carriers" in result.stdout
    assert "rejects descriptor-invalidate field inference" in result.stdout
