from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_full_kv_baseline_path_audit.py"


def test_full_kv_baseline_path_audit_and_w0_scope_are_bounded():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True
    )
    assert "Full-KV path gaps and W0 Chisel scope" in result.stdout
