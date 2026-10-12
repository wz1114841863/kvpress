#!/usr/bin/env python3
"""Validate the RTL3.9-A0 pending-payload read-association manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=ROOT / "analysis/rtl3_9_a0_pending_payload_read_association_manifest.json",
                        help="RTL3.9-A0 manifest to validate (default: repository manifest)")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    assert manifest["schema_version"] == "kvzap-route-a-rtl3-9-a0-pending-payload-read-association-1.0"
    assert manifest["status"] == "complete_pending_payload_provenance_binding_pre_rtl3_9_a_materialization"
    assert manifest["owner"]["sole_producer"] == "pending_payload_storage_owner"
    assert manifest["atomic_join"]["inputs"] == ["AdmissionContext", "R6AuthorityTransition hot_to_pending", "PendingPayloadReadBinding"]
    gate = manifest["p3_pack_read_gate"]
    assert gate["top_work_producer_active"] is False
    assert gate["future_materializer_authorized"] is False
    assert manifest["disposition"]["p3_pack_read_work_top_tieoff_retained"] is True
    assert manifest["disposition"]["rtl3_9_a_materializer_complete"] is False
    assert manifest["disposition"]["rtl3_final_review_authorized"] is False
    for relative, expected in manifest["source_sha256"].items():
        actual = sha256(ROOT / relative)
        assert actual == expected, f"hash mismatch: {relative}: {actual} != {expected}"
    print(f"PASS: RTL3.9-A0 pending-payload association manifest verified ({len(manifest['source_sha256'])} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
