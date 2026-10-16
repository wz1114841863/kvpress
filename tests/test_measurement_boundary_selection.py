from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_measurement_boundary_selection.py"


def test_mbr0_candidate_boundary_is_bounded_and_complete():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True
    )
    assert "bounded candidate BOM" in result.stdout
