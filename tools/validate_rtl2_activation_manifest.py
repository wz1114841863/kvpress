#!/usr/bin/env python3
"""Validate the no-model RTL2.0 producer/consumer activation inventory."""

from __future__ import annotations

import argparse
from pathlib import Path

from kvpress.rtl2_activation_manifest import load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "analysis" / "rtl2_0_activation_manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="RTL2.0 activation manifest to validate")
    args = parser.parse_args()
    validate_manifest(load_manifest(args.manifest))
    print(f"RTL2.0 activation manifest passed: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
