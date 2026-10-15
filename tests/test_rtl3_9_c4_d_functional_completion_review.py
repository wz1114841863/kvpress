from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_c4_d_functional_completion_review.py"


def test_c4_d_review_is_bounded_to_existing_functional_evidence():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "bounded" in result.stdout
    assert "functional-subsystem review" in result.stdout
