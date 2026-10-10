#!/usr/bin/env python3
"""Validate the hash-bound RTL3.8.0 ingress-retirement contract."""
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
        default=Path("analysis/rtl3_8_0_functional_closure_ingress_retirement_manifest.json"),
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text())
    assert data["status"] == "complete_planning_ingress_retirement_freeze_pre_rtl3_8_activation"
    assert data["disposition"]["rtl3_functional_realization_complete"] is False
    assert data["disposition"]["rtl3_8_behavioral_activation_authorized"] is False
    assert set(data["retirement_records"]) == {f"I{index}" for index in range(9)}
    for name, expected in data["source_sha256"].items():
        actual = hashlib.sha256((args.repository_root / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"hash mismatch for {name}: {actual} != {expected}")
    print("PASS: RTL3.8.0 functional-closure ingress-retirement manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
