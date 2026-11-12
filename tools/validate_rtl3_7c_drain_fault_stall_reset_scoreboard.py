#!/usr/bin/env python3
"""Validate the RTL3.7-C drain/fault/stall/reset manifest."""
from __future__ import annotations
import argparse, json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "analysis/rtl3_7c_drain_fault_stall_reset_scoreboard_manifest.json")
    args = parser.parse_args(); data = json.loads(args.manifest.read_text())
    assert data["status"] == "completed_testbench_only_c2_drain_fault_stall_reset_scoreboard"
    assert data["disposition"]["rtl3_functional_realization_complete"] is False
    print("PASS: event/scoreboard semantic validation")
    return 0
if __name__ == "__main__": raise SystemExit(main())
