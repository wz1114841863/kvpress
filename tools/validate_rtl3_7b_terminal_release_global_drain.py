#!/usr/bin/env python3
"""Validate the hash-bound RTL3.7-B terminal/release/retire manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


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


def _git_bytes(repository_root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repository_root), *args], check=False, capture_output=True)
    if result.returncode != 0:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def validate(manifest_path: Path, provenance_path: Path, repository_root: Path) -> None:
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
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance.get("schema_version") != "kvzap-route-a-rtl3-7-b-historical-provenance-1.0":
        raise ValueError("RTL3.7-B provenance schema drift")
    if provenance.get("manifest_sha256") != _sha256(manifest_path):
        raise ValueError("RTL3.7-B provenance manifest hash drift")
    revision = provenance.get("frozen_source_commit", "")
    if _git_bytes(repository_root, "rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip() != revision:
        raise ValueError("RTL3.7-B frozen source commit is not immutable")
    if subprocess.run(["git", "-C", str(repository_root), "merge-base", "--is-ancestor", revision, "HEAD"], check=False).returncode != 0:
        raise ValueError("current HEAD does not retain the frozen RTL3.7-B source commit")
    hashes = manifest.get("source_sha256", {})
    if not hashes:
        raise ValueError("RTL3.7-B source hash inventory is empty")
    for relative_path, expected in hashes.items():
        actual = hashlib.sha256(_git_bytes(repository_root, "show", f"{revision}:{relative_path}")).hexdigest()
        if actual != expected:
            raise ValueError(f"frozen hash mismatch for {relative_path}: {actual} != {expected}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=Path("analysis/rtl3_7b_terminal_release_global_drain_manifest.json"),
                        help="hash-bound RTL3.7-B manifest path")
    parser.add_argument("--repository-root", type=Path, default=Path("."),
                        help="repository root containing source paths")
    parser.add_argument("--provenance", type=Path,
                        default=Path("analysis/rtl3_7b_terminal_release_global_drain_historical_provenance.json"),
                        help="immutable RTL3.7-B source-revision provenance record")
    args = parser.parse_args()
    validate(args.manifest, args.provenance, args.repository_root)
    print("PASS: RTL3.7-B terminal/release/retire frozen manifest replayed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
