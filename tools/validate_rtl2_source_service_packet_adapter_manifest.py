#!/usr/bin/env python3
"""Validate the no-model RTL2.0f source-service packet-adapter contract."""
from __future__ import annotations

import argparse
from pathlib import Path

from kvpress.rtl2_source_service_packet_adapter_manifest import load_manifest, validate_manifest

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "analysis/rtl2_0f_source_service_packet_adapter_manifest.json",
        help="RTL2.0f source-service packet-adapter manifest",
    )
    args = parser.parse_args()
    validate_manifest(load_manifest(args.manifest))
    print(f"RTL2.0f source-service packet-adapter manifest passed: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
