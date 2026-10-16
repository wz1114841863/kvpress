from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_measurement_realization_candidate_proposal.py"


def test_mbr1a_candidate_preparation_is_bounded_and_approval_gated():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True
    )
    assert "candidate preparation remains bounded" in result.stdout
