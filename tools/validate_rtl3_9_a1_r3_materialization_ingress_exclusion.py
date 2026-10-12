#!/usr/bin/env python3
"""Validate the RTL3.9-A1 R3 materialization/ingress-exclusion manifest."""

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
    parser.add_argument("--manifest", type=Path, default=ROOT / "analysis/rtl3_9_a1_r3_materialization_ingress_exclusion_manifest.json", help="RTL3.9-A1 manifest to validate (default: repository manifest)")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "kvzap-route-a-rtl3-9-a1-r3-materialization-ingress-exclusion-1.0"
    assert manifest["status"] == "complete_pre_activation_materialization_and_ingress_contract"
    assert manifest["owner"] == {"sole_materializer": "route_a_m2_p3_wrapper", "top_role": "composition_only", "a0_binding_owner": "pending_payload_storage_owner"}
    work = manifest["work_provenance"]
    assert work["fixed_c2_semantics"] == {"source_kind": "pending", "candidate_class": "pack_read", "expected_fragment_count": 8}
    assert work["submission_key"]["advance"] == "exactly_once_on_accepted_work"
    assert work["submission_key"]["not_a"] == ["r2_winner_decision", "global_queue_index", "physical_fifo", "permanent_schedule"]
    assert work["eligibility_snapshot"]["baseline_offer_rule"] == "all_named_logical_predicates_true_only"
    assert manifest["baseline"]["active_work_per_live_stage"] == 1
    assert manifest["baseline"]["permanent_architecture_schedule"] is False
    ingress = manifest["sidecar_and_ingress_exclusion"]
    assert ingress["sidecar_owner"] == "route_a_m2_p3_wrapper"
    assert ingress["payload_simultaneous_offer"] == "assert_fail_closed_no_priority"
    assert ingress["sidecar_simultaneous_offer"] == "assert_fail_closed_no_priority"
    disposition = manifest["disposition"]
    assert disposition["top_p3_pack_read_work_still_inactive"] is True
    assert disposition["p3_packed_write_still_inert"] is True
    assert disposition["rtl3_9_a_functional_activation_complete"] is False
    for relative, expected in manifest["source_sha256"].items():
        actual = sha256(ROOT / relative)
        assert actual == expected, f"hash mismatch: {relative}: {actual} != {expected}"
    print(f"PASS: RTL3.9-A1 materialization/ingress-exclusion manifest verified ({len(manifest['source_sha256'])} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
