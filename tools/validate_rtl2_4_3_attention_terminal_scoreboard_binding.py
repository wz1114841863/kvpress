#!/usr/bin/env python3
"""Validate the narrow RTL2.4.3 attention-terminal scoreboard binding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kvpress.rtl2_attention_terminal_scoreboard_binding import load_binding, validate_binding, validate_source_hashes


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, default=ROOT / "analysis" / "rtl2_4_3_attention_terminal_scoreboard_binding.json", help="RTL2.4.3 binding JSON")
    parser.add_argument("--schema", type=Path, default=ROOT / "analysis" / "rtl2_scoreboard_event_schema.json", help="immutable RTL2 event schema")
    parser.add_argument("--phase-overlay", type=Path, default=ROOT / "analysis" / "rtl2_scoreboard_event_phase_reconciliation_01.json", help="active RTL2 phase overlay")
    args = parser.parse_args()
    binding = load_binding(args.binding)
    validate_binding(binding, json.loads(args.schema.read_text(encoding="utf-8")), json.loads(args.phase_overlay.read_text(encoding="utf-8")))
    validate_source_hashes(binding, ROOT)
    print(f"RTL2.4.3 attention-terminal scoreboard binding passed: {args.binding}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
