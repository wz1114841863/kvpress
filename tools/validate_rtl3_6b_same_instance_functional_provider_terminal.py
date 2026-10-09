#!/usr/bin/env python3
"""Validate the hash-bound RTL3.6-B static fixture composition manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from kvpress.rtl3_6b_functional_provider_terminal_fixture import (
    FIXTURE_PATH,
    encoded_fixture_fields,
    load_fixture_fields,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(manifest_path: Path, repository_root: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "completed_testbench_only_static_functional_provider_terminal_composition":
        raise ValueError("RTL3.6-B manifest has an unexpected status")
    if manifest["binding"] != {
        "packet_owner": "route_a_functional_attention_partial_provider",
        "packet_boundary": "route_a_source_service_packet_adapter -> route_a_merge_boundary accepted-packet egress",
        "terminal_owner": "route_a_functional_r4_merge_provider",
        "transport": "versioned static shared fixture only",
        "terminal_route": "route_a_merge_boundary -> route_a_lifecycle_adapter -> same-child r5 reclaim",
    }:
        raise ValueError("RTL3.6-B binding differs from the frozen test-only boundary")
    fixture = repository_root / manifest["fixture_path"]
    if fixture != repository_root / FIXTURE_PATH:
        raise ValueError("RTL3.6-B manifest names an unexpected fixture")
    if load_fixture_fields(fixture) != encoded_fixture_fields():
        raise ValueError("RTL3.6-B fixture differs from functional-provider/R4-oracle output")
    for relative_path, expected in manifest["source_sha256"].items():
        actual = _sha256(repository_root / relative_path)
        if actual != expected:
            raise ValueError(f"hash mismatch for {relative_path}: {actual} != {expected}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("analysis/rtl3_6b_same_instance_functional_provider_terminal_manifest.json"),
        help="hash-bound RTL3.6-B manifest path",
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."), help="repository root containing source paths")
    args = parser.parse_args()
    validate(args.manifest, args.repository_root)
    print("PASS: RTL3.6-B static functional provider/terminal composition manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
