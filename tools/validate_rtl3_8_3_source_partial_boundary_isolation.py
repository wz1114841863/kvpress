#!/usr/bin/env python3
"""Validate the hash-bound RTL3.8.3 source/partial boundary record."""
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
        default=Path("analysis/rtl3_8_3_source_partial_boundary_isolation_manifest.json"),
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text())
    assert data["status"] == "complete_i5_i6_ingress_isolation_partial_boundary_i7_i8_open"
    assert data["implemented_retirement_boundaries"] == ["I5", "I6"]
    disposition = data["disposition"]
    assert disposition["verification_p3_and_direct_ingress_retired"] is True
    assert disposition["partial_provider_boundary_connected"] is True
    assert disposition["live_r3_direct_work_producers_complete"] is False
    assert disposition["source_payload_lease_export_complete"] is False
    assert disposition["numeric_or_physical_realization_complete"] is False
    for relative_path, expected in data["source_sha256"].items():
        actual = hashlib.sha256((args.repository_root / relative_path).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"hash mismatch for {relative_path}: {actual} != {expected}")
    print(f"PASS: RTL3.8.3 source/partial boundary manifest verified ({len(data['source_sha256'])} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
