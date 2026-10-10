#!/usr/bin/env python3
"""Validate the hash-bound RTL3.7-B terminal/release/retire manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


STATUS = "completed_testbench_only_terminal_release_retire_ordering"
REQUIRED_DISPOSITION = {
    "rtl3_7b_terminal_release_retire_ordering_closed": True,
    "rtl3_functional_realization_complete": False,
    "next_required_gate": "rtl3_completion_cross_owner_review_03",
}
REQUIRED_INVARIANTS = {
    "every exact endpoint terminal is forwarded to S2",
    "only the final endpoint terminal creates one packed-read association terminal",
    "association release must be accepted before a matching runtime retirement can reach R6",
    "missing or mismatched identities cannot pass the testbench-only retire gate",
    "R6/R5 retain global drain, durable reclaim, and retire acknowledgement ownership",
    "no production-top or global-collector topology change",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(manifest_path: Path, repository_root: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != STATUS:
        raise ValueError("RTL3.7-B status drift")
    if not REQUIRED_INVARIANTS <= set(manifest.get("invariants", ())):
        raise ValueError("RTL3.7-B invariant inventory drift")
    if manifest.get("disposition") != REQUIRED_DISPOSITION:
        raise ValueError("RTL3.7-B disposition drift")
    boundary = manifest.get("boundary", {})
    if boundary.get("scope") != "testbench-only association release-to-retire ordering":
        raise ValueError("RTL3.7-B scope drift")
    if boundary.get("production_top") != "unchanged":
        raise ValueError("RTL3.7-B production-top boundary drift")
    hashes = manifest.get("source_sha256", {})
    if not hashes:
        raise ValueError("RTL3.7-B source hash inventory is empty")
    for relative_path, expected in hashes.items():
        actual = _sha256(repository_root / relative_path)
        if actual != expected:
            raise ValueError(f"hash mismatch for {relative_path}: {actual} != {expected}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=Path("analysis/rtl3_7b_terminal_release_global_drain_manifest.json"),
                        help="hash-bound RTL3.7-B manifest path")
    parser.add_argument("--repository-root", type=Path, default=Path("."),
                        help="repository root containing source paths")
    args = parser.parse_args()
    validate(args.manifest, args.repository_root)
    print("PASS: RTL3.7-B terminal/release/retire manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
