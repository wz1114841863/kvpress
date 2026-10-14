import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_c3a_packed_source_service_terminal.py"


def test_rtl3_9_c3a_packed_source_service_terminal_preflight() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT,
                            check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "RTL3.9-C3a" in result.stdout
