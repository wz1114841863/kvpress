#!/usr/bin/env python3
"""Validate the hash-bound RTL3.6-C2 dataflow/reset-epoch manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


STATUS = "completed_testbench_only_composed_dataflow_reset_epoch_witness"
REQUIRED_BOUNDARY = {
    "composition": "testbench-only same-instance R3 publication through C1 typed source delivery, static R4 terminal, R6 retirement, and same-R5 reclaim",
    "publication_to_service_join": "existing verification-only identity/page/slot association",
    "source_read": "RTL3.2 association owner plus typed R2/R1 endpoint chain",
    "sidecar": "RTL3.6-C1 copied-allocation handle-keyed fixture transport",
    "reset": "both test-harness R1 wrappers require fresh external init_ack; unmatched old response is consumed-and-suppressed",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(manifest_path: Path, repository_root: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != STATUS or manifest.get("boundary") != REQUIRED_BOUNDARY:
        raise ValueError("RTL3.6-C2 status or boundary drift")
    required = {
        "real publication precedes S2 service join",
        "S2Packed uses published-metadata eligibility",
        "sidecar is copied-allocation fixture data only",
        "S2 READY requires payload and sidecar completion",
        "stale response consumed-and-suppressed before fresh init_ack",
        "no production-top activation",
    }
    if not required <= set(manifest.get("invariants", ())):
        raise ValueError("RTL3.6-C2 invariant inventory drift")
    if manifest.get("disposition") != {
        "rtl3_6c2_composed_dataflow_reset_epoch_closed": True,
        "rtl3_functional_realization_complete": False,
        "next_required_gate": "rtl3_completion_cross_owner_review_02",
    }:
        raise ValueError("RTL3.6-C2 disposition drift")
    for relative_path, expected in manifest.get("source_sha256", {}).items():
        actual = _sha256(repository_root / relative_path)
        if actual != expected:
            raise ValueError(f"hash mismatch for {relative_path}: {actual} != {expected}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl3_6c2_same_instance_dataflow_reset_manifest.json"), help="hash-bound RTL3.6-C2 manifest path")
    parser.add_argument("--repository-root", type=Path, default=Path("."), help="repository root containing source paths")
    args = parser.parse_args()
    validate(args.manifest, args.repository_root)
    print("PASS: RTL3.6-C2 same-instance dataflow/reset-epoch manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
