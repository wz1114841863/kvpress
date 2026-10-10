#!/usr/bin/env python3
"""Validate the hash-bound RTL3 cross-owner review 03 disposition."""
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
        default=Path("analysis/rtl3_completion_cross_owner_review_03_manifest.json"),
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text())
    assert data["status"] == "reviewed_no_pass_remaining_functional_source_replacement"
    assert data["disposition"]["rtl3_functional_realization_complete"] is False
    for name, expected in data["source_sha256"].items():
        actual = hashlib.sha256((args.repository_root / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"hash mismatch for {name}: {actual} != {expected}")
    print("PASS: RTL3 completion cross-owner review 03 manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
