#!/usr/bin/env python3
"""Validate the hash-bound RTL3.6-C1 sidecar-fixture transport manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


STATUS = "completed_testbench_only_named_sidecar_fixture_transport"
EXPECTED_BOUNDARY = {
    "allocation_owner": "route_a_packed_read_association_owner",
    "tap": "testbench_route_a_rtl3_6c_allocation_sidecar_tap",
    "transport_owner": "testbench_route_a_rtl3_6c_sidecar_fixture_transport",
    "sidecar_sink": "route_a_s2_gqa_source_wrapper",
    "transport": "testbench fixture keyed by copied descriptor-sidecar handle only",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(manifest_path: Path, repository_root: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != STATUS or manifest.get("boundary") != EXPECTED_BOUNDARY:
        raise ValueError("RTL3.6-C1 status or owner boundary drift")
    required = {
        "no payload-derived sidecar",
        "unknown handle or count fails closed",
        "stale identity page or generation fails closed",
        "manual sidecar ingress ready-low in fixture mode",
        "no production-top activation",
    }
    if not required <= set(manifest.get("invariants", ())):
        raise ValueError("RTL3.6-C1 invariant inventory drift")
    disposition = manifest.get("disposition")
    if disposition != {
        "rtl3_6c1_sidecar_transport_closed": True,
        "rtl3_functional_realization_complete": False,
        "next_required_closure": "rtl3_6c2_same_instance_complete_dataflow_and_reset_epoch_composition",
    }:
        raise ValueError("RTL3.6-C1 disposition drift")
    for relative_path, expected in manifest.get("source_sha256", {}).items():
        actual = _sha256(repository_root / relative_path)
        if actual != expected:
            raise ValueError(f"hash mismatch for {relative_path}: {actual} != {expected}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl3_6c1_sidecar_fixture_transport_manifest.json"), help="hash-bound RTL3.6-C1 manifest path")
    parser.add_argument("--repository-root", type=Path, default=Path("."), help="repository root containing source paths")
    args = parser.parse_args()
    validate(args.manifest, args.repository_root)
    print("PASS: RTL3.6-C1 sidecar fixture transport manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
