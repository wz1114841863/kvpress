#!/usr/bin/env python3
"""Validate the hash-bound RTL3.7-A shared functional-memory continuity manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


STATUS = "completed_testbench_only_shared_functional_memory_continuity"
REQUIRED_BOUNDARY = {
    "store_owner": "testbench_route_a_functional_memory_store",
    "object_key": "testbench-only (opaque address_ref, existing expected_fragment_count); not a deployed physical address format",
    "publication_endpoint": "testbench_route_a_functional_memory_environment bound at the real R3/R5 R1 external port",
    "source_endpoint": "testbench_route_a_functional_memory_environment bound at the C2 source-read R1 external port",
    "continuity_rule": "C2 descriptor payload handle is the accepted R3 eight-fragment packed-write address_ref; both endpoints use the same testbench-only object store",
    "unclosed": "C2 grants remain verification facts; C1 sidecar and RTL3.6-B/R4 static fixtures remain; no terminal-release/global-drain closure",
}
REQUIRED_DISPOSITION = {
    "rtl3_7a_shared_functional_memory_continuity_closed": True,
    "rtl3_functional_realization_complete": False,
    "next_required_gate": "rtl3_7b_terminal_release_and_global_drain_closure",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(manifest_path: Path, repository_root: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != STATUS or manifest.get("boundary") != REQUIRED_BOUNDARY:
        raise ValueError("RTL3.7-A status or boundary drift")
    required = {
        "one successful R3 eight-fragment packed write materializes only at its accepted terminal",
        "C2 reads the exact R3 durable payload object rather than an independently injected payload",
        "a one-fragment descriptor object cannot overwrite an eight-fragment payload object at the same opaque address_ref in the testbench store",
        "no production common-memory/controller or physical-address claim",
    }
    if not required <= set(manifest.get("invariants", ())):
        raise ValueError("RTL3.7-A invariant inventory drift")
    if manifest.get("disposition") != REQUIRED_DISPOSITION:
        raise ValueError("RTL3.7-A disposition drift")
    hashes = manifest.get("source_sha256", {})
    if not hashes:
        raise ValueError("RTL3.7-A source hash inventory is empty")
    for relative_path, expected in hashes.items():
        actual = _sha256(repository_root / relative_path)
        if actual != expected:
            raise ValueError(f"hash mismatch for {relative_path}: {actual} != {expected}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl3_7a_shared_functional_memory_continuity_manifest.json"), help="hash-bound RTL3.7-A manifest path")
    parser.add_argument("--repository-root", type=Path, default=Path("."), help="repository root containing source paths")
    args = parser.parse_args()
    validate(args.manifest, args.repository_root)
    print("PASS: RTL3.7-A shared functional-memory continuity manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
