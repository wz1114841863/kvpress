#!/usr/bin/env python3
"""Validate the RTL3.4-B functional-R4 provider provenance manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "analysis/rtl3_4b_functional_r4_provider_manifest.json",
        help="RTL3.4-B provenance manifest to validate (default: repository manifest)",
    )
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a-rtl3-4b-functional-r4-provider-1.0":
        raise SystemExit("unsupported RTL3.4-B manifest schema")
    if manifest.get("status") != "implemented_functional_oracle_provider_pre_rtl3_5_partial_producer":
        raise SystemExit("unexpected RTL3.4-B manifest status")
    for relative, expected in manifest["source_sha256"].items():
        actual = _sha256(ROOT / relative)
        if actual != expected:
            raise SystemExit(f"SHA-256 mismatch for {relative}: expected {expected}, got {actual}")
    print(f"PASS: RTL3.4-B manifest verified ({len(manifest['source_sha256'])} source hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
