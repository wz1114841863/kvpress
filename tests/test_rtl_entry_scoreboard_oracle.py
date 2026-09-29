from pathlib import Path
import subprocess, sys
ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "validate_rtl_entry_scoreboard_oracle.py"
def test_scoreboard_oracle_manifest_is_complete():
    result = subprocess.run([sys.executable, str(TOOL)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "manifest passed" in result.stdout
