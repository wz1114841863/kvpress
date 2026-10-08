#!/usr/bin/env python3
"""Validate the no-model RTL2.6 completion-review entry audit."""
from __future__ import annotations
import argparse
from pathlib import Path
from kvpress.rtl2_6_completion_review import load_and_validate
ROOT = Path(__file__).resolve().parents[1]
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=ROOT / "analysis/rtl2_6_completion_review_manifest.json")
    parser.add_argument("--scoreboard-schema", type=Path, default=ROOT / "analysis/rtl2_scoreboard_event_schema.json")
    parser.add_argument("--phase-overlay", type=Path, default=ROOT / "analysis/rtl2_scoreboard_event_phase_reconciliation_01.json")
    args = parser.parse_args(); load_and_validate(args.review, args.scoreboard_schema, args.phase_overlay, ROOT)
    print(f"RTL2.6 entry audit passed: {args.review}"); return 0
if __name__ == "__main__": raise SystemExit(main())
