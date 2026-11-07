"""Exercise the native clock-report gate without invoking EDA tools."""
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


@pytest.mark.parametrize("row,accepted", [
    ("kvzap_control_clk 2.00 {0 1} {clock}", True),
    ("kvzap_control_clk\n 2.00 {0 1} {clock}", True),
    ("kvzap_control_clk 2.00 {0 1} p {clock}", False),
    ("kvzap_control_clk 2.00 {0 1} f {clock}", False),
    ("kvzap_control_clk 3.00 {0 1} {clock}", False),
    ("kvzap_control_clk 2.00 {0 1.5} {clock}", False),
    ("kvzap_control_clk 2.00 {0 1} {other}", False),
    ("", False),
])
def test_saved_clock_report(row, accepted):
    tcl = shutil.which("tclsh")
    if not tcl:
        pytest.skip("tclsh is unavailable")
    source = (Path(__file__).resolve().parents[1] /
              "hardware/route_a/dc/diagnose_rd1_pm1_saved_setup.tcl").read_text()
    procedure = source.split("if {[catch {", 1)[0]
    # Tcl receives the row as an ordinary argv value, without source interpolation.
    program = procedure + "\nputs [catch {kvzap_require_saved_ideal_clock_report [lindex $argv 0]}]\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tcl") as f:
        f.write(program)
        f.flush()
        result = subprocess.run([tcl, f.name, row], capture_output=True, text=True, check=True)
    assert result.stderr == ""
    assert result.stdout.strip() == ("0" if accepted else "1")
