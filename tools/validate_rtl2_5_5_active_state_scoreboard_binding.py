#!/usr/bin/env python3
"""Validate the narrow RTL2.5.5 reclaim/retire scoreboard binding."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from kvpress.rtl2_reclaim_scoreboard_binding import load_binding, validate_binding, validate_source_hashes
ROOT = Path(__file__).resolve().parents[1]
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, default=ROOT / "analysis/rtl2_5_5_active_state_scoreboard_binding.json")
    parser.add_argument("--schema", type=Path, default=ROOT / "analysis/rtl2_scoreboard_event_schema.json")
    parser.add_argument("--phase-overlay", type=Path, default=ROOT / "analysis/rtl2_scoreboard_event_phase_reconciliation_01.json")
    args = parser.parse_args(); binding = load_binding(args.binding)
    validate_binding(binding, json.loads(args.schema.read_text()), json.loads(args.phase_overlay.read_text())); validate_source_hashes(binding, ROOT)
    print(f"RTL2.5.5 active-state scoreboard binding passed: {args.binding}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
