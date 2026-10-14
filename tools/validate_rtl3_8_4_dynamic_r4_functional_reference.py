#!/usr/bin/env python3
"""Validate the hash-bound RTL3.8.4 R4 functional-reference protocol record."""

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
        default=ROOT / "analysis/rtl3_8_4_dynamic_r4_functional_reference_manifest.json",
        help="RTL3.8.4 manifest to validate (default: repository manifest)",
    )
    parser.add_argument(
        "--provenance", type=Path,
        default=ROOT / "analysis/rtl3_8_4_dynamic_r4_functional_reference_historical_provenance.json",
        help="immutable RTL3.8.4 source-revision provenance record",
    )
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text())
    assert manifest["schema_version"] == "kvzap-route-a-rtl3-8-4-dynamic-r4-functional-reference-1.0"
    assert manifest["status"] == "complete_i7_i8_dynamic_protocol_activation_external_oracle_bound"
    assert manifest["provider"] == {
        "owner": "route_a_functional_r4_merge_provider",
        "classification": "external_pure_software_reference_environment",
        "numeric_evaluator": "existing RTL3.3/RTL3.4-B oracle only",
    }
    disposition = manifest["disposition"]
    assert disposition["top_r4_terminal_tieoffs_retired"] is True
    assert disposition["accepted_packet_and_work_boundary_connected"] is True
    assert disposition["chisel_numeric_r4_implementation_complete"] is False
    assert disposition["same_simulation_python_chisel_cosimulation_complete"] is False
    assert disposition["rtl3_final_review_authorized"] is False
    provenance = json.loads(args.provenance.read_text())
    assert provenance["schema_version"] == "kvzap-route-a-rtl3-8-4-historical-provenance-1.0"
    assert provenance["manifest_sha256"] == sha256(args.manifest)
    revision = provenance["frozen_source_commit"]
    assert git_bytes("rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip() == revision
    assert subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", revision, "HEAD"], check=False).returncode == 0
    for relative, expected in manifest["source_sha256"].items():
        actual = hashlib.sha256(git_bytes("show", f"{revision}:{relative}")).hexdigest()
        assert actual == expected, f"frozen hash mismatch: {relative}: {actual} != {expected}"
    print(f"PASS: RTL3.8.4 dynamic R4 frozen manifest replayed at {revision} ({len(manifest['source_sha256'])} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
