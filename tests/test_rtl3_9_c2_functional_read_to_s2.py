import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_c2_functional_read_to_s2.py"


def test_rtl3_9_c2_functional_read_to_s2_preflight() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, check=False,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "RTL3.9-C2 functional read-to-S2" in result.stdout
