#!/usr/bin/env python3
"""Validate the no-model RTL3.0 replacement-owner planning contract."""
from __future__ import annotations

import argparse
from pathlib import Path

from kvpress.rtl3_0_replacement_owner import load_and_validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl3_0_replacement_owner_manifest.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_and_validate(root / args.manifest, root)
    print("RTL3.0 replacement-owner planning contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
