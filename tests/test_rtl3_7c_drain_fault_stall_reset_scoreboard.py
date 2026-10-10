import sys
from pathlib import Path
from tools.validate_rtl3_7c_drain_fault_stall_reset_scoreboard import main

def test_rtl3_7c_manifest_is_hash_bound(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["validate_rtl3_7c_drain_fault_stall_reset_scoreboard.py"])
    assert main() == 0
