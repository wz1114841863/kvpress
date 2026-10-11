#!/usr/bin/env python3
"""Validate the hash-bound RTL3.8.1 packed-activation binding record."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("analysis/rtl3_8_1_packed_activation_binding_manifest.json"),
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text())
    assert data["status"] == "complete_functional_owner_binding_not_yet_functional_top_replacement"
    assert data["implemented_retirement_boundaries"] == ["I0", "I1", "I2", "I3"]
    assert data["disposition"]["verification_ingress_retired_from_functional_top"] is False
    assert data["disposition"]["physical_or_numeric_realization_complete"] is False
    for relative_path, expected in data["source_sha256"].items():
        actual = hashlib.sha256((args.repository_root / relative_path).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"hash mismatch for {relative_path}: {actual} != {expected}")
    print(f"PASS: RTL3.8.1 packed-activation binding manifest verified ({len(data['source_sha256'])} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
