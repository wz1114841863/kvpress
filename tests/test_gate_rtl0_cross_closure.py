from pathlib import Path
import subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
def test_gate_rtl0_cross_closure():
    result=subprocess.run([sys.executable, str(ROOT/"tools/validate_gate_rtl0_cross_closure.py")],cwd=ROOT,text=True,capture_output=True,check=True)
    assert "cross-closure passed" in result.stdout
