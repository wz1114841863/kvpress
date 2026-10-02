#!/usr/bin/env python3
"""Validate the no-model, pre-behavior RTL2 scoreboard-event schema."""

from __future__ import annotations

import argparse
from pathlib import Path

from kvpress.rtl2_scoreboard_event_schema import load_and_validate


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=ROOT / "analysis" / "rtl2_scoreboard_event_schema.json", help="RTL2 scoreboard event schema")
    parser.add_argument("--activation-manifest", type=Path, default=ROOT / "analysis" / "rtl2_0_activation_manifest.json", help="review-pass RTL2.0 activation manifest")
    args = parser.parse_args()
    load_and_validate(args.schema, args.activation_manifest)
    print(f"RTL2 scoreboard event schema passed: {args.schema}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
