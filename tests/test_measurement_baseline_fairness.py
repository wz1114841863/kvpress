from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_measurement_baseline_fairness.py"


def test_mbr1_paired_full_kv_fairness_plan_is_complete_and_bounded():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True
    )
    assert "paired Full-KV fairness plan" in result.stdout
