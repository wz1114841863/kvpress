import subprocess
import sys
from pathlib import Path


def test_rtl3_7b_terminal_release_global_drain_manifest_is_historically_replayed() -> None:
    root = Path(__file__).resolve().parents[1]
    validator = root / "tools/validate_rtl3_7b_terminal_release_global_drain.py"
    result = subprocess.run([sys.executable, str(validator)], cwd=root, check=False,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "frozen manifest replayed" in result.stdout
