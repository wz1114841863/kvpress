#!/usr/bin/env python3
"""Validate the RTL3.6-A active replay provenance-repair record."""
from __future__ import annotations

import argparse
from pathlib import Path

from kvpress.rtl3_6a_active_replay_provenance_repair import load_and_validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl3_6a_active_replay_provenance_repair_manifest.json"), help="RTL3.6-A hash-bound repair manifest")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_and_validate(root / args.manifest, root)
    print("PASS: RTL3.6-A active replay provenance repair verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
