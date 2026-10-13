import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_c0_post_r6_first_use_association.py"


def test_rtl3_9_c0_post_r6_first_use_association_preflight() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, check=False,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "RTL3.9-C0 post-R6" in result.stdout
