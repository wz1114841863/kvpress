#!/usr/bin/env python3
"""Replay the frozen RTL3.8.2 functional-sidecar delivery evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def git_bytes(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args], check=False, capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace").strip()
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path,
        default=ROOT / "analysis/rtl3_8_2_functional_sidecar_delivery_manifest.json",
        help="RTL3.8.2 manifest to validate",
    )
    parser.add_argument(
        "--provenance", type=Path,
        default=ROOT / "analysis/rtl3_8_2_functional_sidecar_delivery_historical_provenance.json",
        help="immutable RTL3.8.2 source-revision provenance record",
    )
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    provenance = json.loads(args.provenance.read_text(encoding="utf-8"))
    assert data["status"] == "complete_i4_functional_sidecar_delivery_i5_i8_open"
    assert data["implemented_retirement_boundaries"] == ["I4"]
    disposition = data["disposition"]
    assert disposition["functional_sidecar_delivery_complete"] is True
    assert disposition["verification_sidecar_ingress_retired_from_functional_top"] is True
    assert disposition["sidecar_uses_existing_registry_r2_r1_path"] is True
    assert disposition["i5_i8_functional_replacement_complete"] is False
    assert disposition["physical_or_numeric_realization_complete"] is False
    assert provenance["schema_version"] == "kvzap-route-a-rtl3-8-2-historical-provenance-1.0"
    assert provenance["manifest_sha256"] == hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    revision = provenance["frozen_source_commit"]
    resolved_revision = git_bytes(args.repository_root, "rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip()
    assert resolved_revision == revision, "frozen_source_commit must be a full immutable commit ID"
    ancestor = subprocess.run(
        ["git", "-C", str(args.repository_root), "merge-base", "--is-ancestor", revision, "HEAD"],
        check=False, capture_output=True,
    )
    assert ancestor.returncode == 0, "current HEAD does not retain the frozen RTL3.8.2 source commit"
    for relative_path, expected in data["source_sha256"].items():
        frozen_bytes = git_bytes(args.repository_root, "show", f"{revision}:{relative_path}")
        actual = hashlib.sha256(frozen_bytes).hexdigest()
        if actual != expected:
            raise ValueError(f"frozen hash mismatch for {relative_path}: {actual} != {expected}")
    print(
        "PASS: RTL3.8.2 functional-sidecar frozen manifest replayed "
        f"at {revision} ({len(data['source_sha256'])} hashes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
