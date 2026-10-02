#!/usr/bin/env python3
"""Validate the no-model RTL2.0 pre-behavior completion review."""

from __future__ import annotations

import argparse
from pathlib import Path

from kvpress.rtl2_completion_review import load_and_validate


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=ROOT / "analysis" / "rtl2_0_completion_review_manifest.json", help="RTL2.0 completion-review manifest")
    parser.add_argument("--activation-manifest", type=Path, default=ROOT / "analysis" / "rtl2_0_activation_manifest.json", help="review-pass RTL2.0 activation manifest")
    parser.add_argument("--scoreboard-schema", type=Path, default=ROOT / "analysis" / "rtl2_scoreboard_event_schema.json", help="versioned RTL2 scoreboard schema")
    args = parser.parse_args()
    load_and_validate(args.review, args.activation_manifest, args.scoreboard_schema, ROOT)
    print(f"RTL2.0 completion review passed: {args.review}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
