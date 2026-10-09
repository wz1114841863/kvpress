#!/usr/bin/env python3
"""Validate the RTL3.2-A packed-read association-owner contract."""
from __future__ import annotations

import argparse
from pathlib import Path

from kvpress.rtl3_2a_packed_read_association import load_and_validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl3_2a_packed_read_association_manifest.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_and_validate(root / args.manifest, root)
    print("RTL3.2-A packed-read association-owner contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
