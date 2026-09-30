#!/usr/bin/env python3
"""Validate the no-model RTL1-I cross-owner integration manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from kvpress.rtl1_i_integration_manifest import load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "analysis" / "rtl1_i_interface_manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="RTL1-I integration manifest to validate")
    args = parser.parse_args()
    validate_manifest(load_manifest(args.manifest))
    print(f"RTL1-I integration manifest passed: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
