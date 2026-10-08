#!/usr/bin/env python3
"""Validate the RTL2.6.1 no-model event field-provenance binding."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from kvpress.rtl2_6_1_event_binding import load_binding, validate_binding, validate_source_hashes

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, default=ROOT / "analysis/rtl2_6_1_event_binding_manifest.json")
    parser.add_argument("--schema", type=Path, default=ROOT / "analysis/rtl2_scoreboard_event_schema.json")
    args = parser.parse_args()
    binding = load_binding(args.binding)
    validate_binding(binding, json.loads(args.schema.read_text(encoding="utf-8")))
    validate_source_hashes(binding, ROOT)
    print(f"RTL2.6.1 event field-provenance binding passed: {args.binding}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
