#!/usr/bin/env python3
"""Validate the hash-bound RTL3.8.3 source/partial boundary record."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def git_bytes(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], check=False, capture_output=True)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace").strip()
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("analysis/rtl3_8_3_source_partial_boundary_isolation_manifest.json"),
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument(
        "--provenance", type=Path,
        default=ROOT / "analysis/rtl3_8_3_source_partial_boundary_isolation_historical_provenance.json",
        help="immutable RTL3.8.3 source-revision provenance record",
    )
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
    provenance = json.loads(args.provenance.read_text())
    assert provenance["schema_version"] == "kvzap-route-a-rtl3-8-3-historical-provenance-1.0"
    assert provenance["manifest_sha256"] == hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    revision = provenance["frozen_source_commit"]
    assert git_bytes(args.repository_root, "rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip() == revision
    assert subprocess.run(["git", "-C", str(args.repository_root), "merge-base", "--is-ancestor", revision, "HEAD"], check=False).returncode == 0
    for relative_path, expected in data["source_sha256"].items():
        actual = hashlib.sha256(git_bytes(args.repository_root, "show", f"{revision}:{relative_path}")).hexdigest()
        if actual != expected:
            raise ValueError(f"frozen hash mismatch for {relative_path}: {actual} != {expected}")
    print(f"PASS: RTL3.8.3 source/partial frozen manifest replayed at {revision} ({len(data['source_sha256'])} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
