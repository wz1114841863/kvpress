from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_srp5_completion_review.py"


def test_srp5_review_remains_conditional_and_non_implementing():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "conditionally closes planning" in result.stdout
