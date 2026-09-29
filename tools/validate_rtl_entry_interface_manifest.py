#!/usr/bin/env python3
"""Validate the no-model Gate-RTL0 hierarchy/owner interface manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from kvpress.rtl_entry_manifest import RTLEntryManifestError, load_manifest, validate_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the Gate-RTL0 hierarchy/owner manifest; no model, GPU, timing, or RTL claim."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("analysis/rtl_entry_interface_manifest.json"),
        help="Path to the Gate-RTL0 JSON manifest (default: %(default)s).",
    )
    parser.add_argument(
        "--require-interface-signals",
        action="store_true",
        help="Require nonempty full port records; not valid for the hierarchy-only first step.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        validate_manifest(load_manifest(args.manifest), require_interface_signals=args.require_interface_signals)
    except (OSError, ValueError, RTLEntryManifestError) as error:
        raise SystemExit(f"manifest validation failed: {error}") from error
    print(f"Gate-RTL0 hierarchy/owner manifest passed: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
