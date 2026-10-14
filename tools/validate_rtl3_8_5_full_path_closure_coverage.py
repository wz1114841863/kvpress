#!/usr/bin/env python3
"""Validate the current aggregate RTL3.8.5 full-path coverage record."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_bytes(*args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(ROOT), *args], check=False, capture_output=True)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace").strip()
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "analysis/rtl3_8_5_full_path_closure_coverage_manifest.json",
        help="RTL3.8.5 aggregate coverage manifest to validate (default: repository manifest)",
    )
    parser.add_argument(
        "--provenance", type=Path,
        default=ROOT / "analysis/rtl3_8_5_full_path_closure_coverage_historical_provenance.json",
        help="immutable RTL3.8.5 source-revision provenance record",
    )
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text())
    assert manifest["schema_version"] == "kvzap-route-a-rtl3-8-5-full-path-closure-coverage-1.0"
    assert manifest["status"] == "complete_directed_functional_path_coverage_pre_final_rtl3_review"
    coverage = manifest["coverage"]
    assert coverage["nonempty_source_presence_masks"] == [1, 2, 3, 4, 5, 6, 7]
    assert coverage["gqa_consumers"] == [0, 1, 2, 3]
    assert all(coverage[key] is True for key in [
        "success_terminal", "numeric_fault_terminal", "packet_ready_low", "work_ready_low",
        "stale_response_fail_closed", "destructive_reset",
    ])
    disposition = manifest["disposition"]
    assert disposition["test_only_completion_observer"] is True
    assert disposition["live_r3_direct_source_work_producers_complete"] is False
    assert disposition["chisel_numeric_r4_complete"] is False
    assert disposition["rtl3_final_review_authorized"] is False
    provenance = json.loads(args.provenance.read_text())
    assert provenance["schema_version"] == "kvzap-route-a-rtl3-8-5-historical-provenance-1.0"
    assert provenance["manifest_sha256"] == sha256(args.manifest)
    revision = provenance["frozen_source_commit"]
    assert git_bytes("rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip() == revision
    assert subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", revision, "HEAD"], check=False).returncode == 0
    for relative, expected in manifest["source_sha256"].items():
        actual = hashlib.sha256(git_bytes("show", f"{revision}:{relative}")).hexdigest()
        assert actual == expected, f"frozen hash mismatch: {relative}: {actual} != {expected}"
    print(f"PASS: RTL3.8.5 full-path frozen manifest replayed at {revision} ({len(manifest['source_sha256'])} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
