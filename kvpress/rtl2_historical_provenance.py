"""Replay frozen RTL2/RTL3 source-hash records from immutable Git commits.

This helper deliberately separates historical evidence replay from mutable
descendant testbench code.  It does not validate a live RTL implementation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping


class HistoricalProvenanceError(ValueError):
    """A frozen manifest cannot be replayed from its declared Git revision."""


def replay_frozen_manifest(
    *,
    root: Path,
    manifest_path: Path,
    provenance_path: Path,
    record_id: str,
) -> tuple[str, int]:
    """Verify one immutable manifest's source hashes at its recorded commit."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    records = provenance.get("records")
    if not isinstance(records, Mapping) or record_id not in records:
        raise HistoricalProvenanceError(f"missing historical provenance record: {record_id}")
    record = records[record_id]
    if not isinstance(record, Mapping):
        raise HistoricalProvenanceError(f"malformed historical provenance record: {record_id}")
    expected_manifest = record.get("manifest")
    relative_manifest = str(manifest_path.resolve().relative_to(root.resolve()))
    if expected_manifest != relative_manifest:
        raise HistoricalProvenanceError("provenance manifest path differs from requested manifest")
    if record.get("manifest_sha256") != hashlib.sha256(manifest_path.read_bytes()).hexdigest():
        raise HistoricalProvenanceError("frozen manifest bytes differ from recorded provenance")
    revision = record.get("frozen_source_commit")
    if not isinstance(revision, str):
        raise HistoricalProvenanceError("frozen source commit is missing")
    resolved = _git_text(root, "rev-parse", "--verify", f"{revision}^{{commit}}").strip()
    if resolved != revision:
        raise HistoricalProvenanceError("frozen source commit must be a full immutable commit ID")
    ancestor = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", revision, "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestor.returncode != 0:
        raise HistoricalProvenanceError("current HEAD does not retain the frozen source commit")
    sources = manifest.get("source_sha256")
    if not isinstance(sources, Mapping) or not sources:
        raise HistoricalProvenanceError("frozen manifest lacks source_sha256")
    for relative, expected in sources.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise HistoricalProvenanceError("source_sha256 must contain string path/digest pairs")
        actual = hashlib.sha256(_git_bytes(root, "show", f"{revision}:{relative}")).hexdigest()
        if actual != expected:
            raise HistoricalProvenanceError(f"frozen hash mismatch: {relative}")
    return revision, len(sources)


def _git_text(root: Path, *args: str) -> str:
    return _git_bytes(root, *args).decode("utf-8", errors="strict")


def _git_bytes(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], check=False, capture_output=True)
    if result.returncode != 0:
        raise HistoricalProvenanceError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout
