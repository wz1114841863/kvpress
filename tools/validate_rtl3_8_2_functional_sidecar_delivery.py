#!/usr/bin/env python3
"""Validate the hash-bound RTL3.8.2 functional-sidecar delivery record."""
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
        default=Path("analysis/rtl3_8_2_functional_sidecar_delivery_manifest.json"),
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text())
    assert data["status"] == "complete_i4_functional_sidecar_delivery_i5_i8_open"
    assert data["implemented_retirement_boundaries"] == ["I4"]
    disposition = data["disposition"]
    assert disposition["functional_sidecar_delivery_complete"] is True
    assert disposition["verification_sidecar_ingress_retired_from_functional_top"] is True
    assert disposition["sidecar_uses_existing_registry_r2_r1_path"] is True
    assert disposition["i5_i8_functional_replacement_complete"] is False
    assert disposition["physical_or_numeric_realization_complete"] is False
    for relative_path, expected in data["source_sha256"].items():
        actual = hashlib.sha256((args.repository_root / relative_path).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"hash mismatch for {relative_path}: {actual} != {expected}")
    print(f"PASS: RTL3.8.2 functional-sidecar manifest verified ({len(data['source_sha256'])} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
