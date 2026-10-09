#!/usr/bin/env python3
"""Validate the RTL3.2 functional packed-read provenance manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("analysis/rtl3_2_packed_read_functional_integration_manifest.json"),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / args.manifest).read_text())
    assert manifest["status"] == "complete_testbench_composed_functional_packed_payload_path_with_explicit_sidecar_boundary"
    assert manifest["owner"] == "route_a_packed_read_association_owner"
    for relative, expected in manifest["source_sha256"].items():
        actual = sha256(root / relative)
        assert actual == expected, f"SHA-256 mismatch for {relative}: {actual} != {expected}"
    print("RTL3.2 functional packed-read integration provenance passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
