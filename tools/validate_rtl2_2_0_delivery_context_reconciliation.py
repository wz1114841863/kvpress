#!/usr/bin/env python3
"""Validate the no-model RTL2.2.0 delivery-context reconciliation manifest."""
from __future__ import annotations

import argparse
from pathlib import Path

from kvpress.rtl2_2_0_delivery_context_reconciliation import load_manifest, validate_manifest

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "analysis" / "rtl2_2_0_delivery_context_reconciliation_manifest.json",
        help="RTL2.2.0 delivery-context reconciliation manifest",
    )
    args = parser.parse_args()
    validate_manifest(load_manifest(args.manifest), ROOT)
    print(f"RTL2.2.0 delivery-context reconciliation manifest passed: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
