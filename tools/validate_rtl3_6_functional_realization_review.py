#!/usr/bin/env python3
"""Validate the RTL3.6 functional-realization completion-review record."""
from __future__ import annotations

import argparse
from pathlib import Path

from kvpress.rtl3_6_functional_realization_review import load_and_validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl3_6_functional_realization_completion_review_manifest.json"), help="RTL3.6 hash-bound review manifest")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_and_validate(root / args.manifest, root)
    print("PASS: RTL3.6 completion review recorded precise no-PASS live-composition disposition")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
