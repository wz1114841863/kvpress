from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_srp4_differential_cost_evidence_plan.py"


def test_srp4_cost_mapping_remains_evidence_planning_only():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "all 30 partition records" in result.stdout
