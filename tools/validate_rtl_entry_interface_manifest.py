#!/usr/bin/env python3
"""Validate the no-model Gate-RTL0 hierarchy/owner interface manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from kvpress.rtl_entry_manifest import RTLEntryManifestError, load_manifest, validate_manifest, validate_markdown_matrix


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
        help="Require the complete ports-bound manifest state.",
    )
    parser.add_argument(
        "--markdown-matrix",
        type=Path,
        default=Path("analysis/rtl_entry_port_parameter_contract.md"),
        help="Reviewed Markdown port matrix to compare when ports are bound (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = load_manifest(args.manifest)
        validate_manifest(manifest, require_interface_signals=args.require_interface_signals)
        if manifest["status"] != "hierarchy_owner_frozen_ports_pending":
            validate_markdown_matrix(manifest, args.markdown_matrix)
    except (OSError, ValueError, RTLEntryManifestError) as error:
        raise SystemExit(f"manifest validation failed: {error}") from error
    print(f"Gate-RTL0 hierarchy/owner manifest passed: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
