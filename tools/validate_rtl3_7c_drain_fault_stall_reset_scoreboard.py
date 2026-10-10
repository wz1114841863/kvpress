#!/usr/bin/env python3
"""Validate the hash-bound RTL3.7-C drain/fault/stall/reset manifest."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl3_7c_drain_fault_stall_reset_scoreboard_manifest.json"))
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(); data = json.loads(args.manifest.read_text())
    assert data["status"] == "completed_testbench_only_c2_drain_fault_stall_reset_scoreboard"
    assert data["disposition"]["rtl3_functional_realization_complete"] is False
    for name, expected in data["source_sha256"].items():
        actual = hashlib.sha256((args.repository_root / name).read_bytes()).hexdigest()
        if actual != expected: raise ValueError(f"hash mismatch for {name}")
    print("PASS: RTL3.7-C drain/fault/stall/reset manifest verified")
    return 0
if __name__ == "__main__": raise SystemExit(main())
