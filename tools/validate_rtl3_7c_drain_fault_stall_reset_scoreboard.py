#!/usr/bin/env python3
"""Validate the hash-bound RTL3.7-C drain/fault/stall/reset manifest."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from kvpress.rtl2_historical_provenance import replay_frozen_manifest


ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "analysis/rtl3_7c_drain_fault_stall_reset_scoreboard_manifest.json")
    parser.add_argument("--provenance", type=Path, default=ROOT / "analysis/rtl3_9_c4_p0_event_scoreboard_historical_provenance.json")
    args = parser.parse_args(); data = json.loads(args.manifest.read_text())
    assert data["status"] == "completed_testbench_only_c2_drain_fault_stall_reset_scoreboard"
    assert data["disposition"]["rtl3_functional_realization_complete"] is False
    revision, count = replay_frozen_manifest(root=ROOT, manifest_path=args.manifest, provenance_path=args.provenance, record_id="rtl3_7c_drain_fault_stall_reset")
    print(f"PASS: RTL3.7-C drain/fault/stall/reset manifest replayed at {revision} ({count} hashes)")
    return 0
if __name__ == "__main__": raise SystemExit(main())
