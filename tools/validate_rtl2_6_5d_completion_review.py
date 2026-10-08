#!/usr/bin/env python3
"""Validate the RTL2.6.5d no-model cross-owner completion review."""
from __future__ import annotations
import argparse
from pathlib import Path
from kvpress.rtl2_6_5d_completion_review import load_and_validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=Path("analysis/rtl2_6_5d_completion_review.json"))
    parser.add_argument("--schema", type=Path, default=Path("analysis/rtl2_scoreboard_event_schema.json"))
    parser.add_argument("--capture-manifest", type=Path, default=Path("analysis/rtl2_6_5c_event_capture_replay_manifest.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_and_validate(root / args.review, root / args.schema, root / args.capture_manifest, root)
    print("RTL2.6.5d cross-owner completion review passed with no-PASS disposition")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
