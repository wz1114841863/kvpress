#!/usr/bin/env python3
"""Validate the hash-bound RTL3.5-C cross-language packet-binding manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from kvpress.rtl3_5c_partial_packet_fixture import encoded_fixture_fields, load_fixture_fields


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(manifest_path: Path, repository_root: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "implemented_static_cross_language_packet_binding_pre_production_top":
        raise ValueError("RTL3.5-C manifest has an unexpected status")
    if manifest["binding"] != {
        "python_owner": "route_a_functional_attention_partial_provider",
        "chisel_boundary": "route_a_source_service_packet_adapter -> route_a_merge_boundary",
        "transport": "versioned static shared fixture only",
    }:
        raise ValueError("RTL3.5-C binding differs from the approved boundary")
    fixture = repository_root / manifest["fixture_path"]
    if load_fixture_fields(fixture) != encoded_fixture_fields():
        raise ValueError("RTL3.5-C fixture differs from the frozen Python provider output")
    for relative_path, expected in manifest["source_sha256"].items():
        actual = _sha256(repository_root / relative_path)
        if actual != expected:
            raise ValueError(f"hash mismatch for {relative_path}: {actual} != {expected}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl3_5c_cross_language_packet_binding_manifest.json"), help="hash-bound RTL3.5-C manifest path")
    parser.add_argument("--repository-root", type=Path, default=Path("."), help="repository root containing source paths")
    args = parser.parse_args()
    validate(args.manifest, args.repository_root)
    print("PASS: RTL3.5-C cross-language packet-binding manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
