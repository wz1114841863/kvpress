#!/usr/bin/env python3
"""Validate the bounded SRP.4 differential-cost evidence plan."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/synthesis_eligibility_manifest.json"
PLAN = ROOT / "analysis/srp4_differential_cost_evidence_plan.md"


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == (
        "kvzap-route-a-srp-0-4-inventory-partition-eligibility-requirements-cost-plan-1.4"
    )
    assert data["status"] == "srp_0_4_differential_cost_evidence_planning_complete"
    srp4 = data["srp4_differential_cost_evidence_plan"]
    assert srp4["status"] == "complete_evidence_planning_only"
    provenance = srp4["a4141_provenance"]
    assert provenance["accepted_report_sha256"] == (
        "0f43ec6dc30912210e4c565ebdd57554b02b7ca3f22326a498924e4cf1f2fdcb"
    )
    assert provenance["live_tree_report_status"].startswith("absent;")
    assert Path(ROOT / provenance["accepted_hash_verification_record"]).is_file()

    all_partition_ids = {item["id"] for item in data["partition_records"]}
    rows = srp4["cost_mapping_rows"]
    mapped_ids = [partition_id for row in rows for partition_id in row["partition_ids"]]
    assert len(mapped_ids) == len(all_partition_ids) == 30
    assert len(set(mapped_ids)) == len(mapped_ids)
    assert set(mapped_ids) == all_partition_ids
    assert {row["coverage"] for row in rows} == set(srp4["mapping_status_values"])
    assert {"P1", "P2", "P3", "P4", "gate", "excluded"} <= {
        row["priority"] for row in rows
    }
    assert srp4["next_gate"] == "SRP.5 Completion Review; not started by this record."
    assert data["next_gate"].startswith("SRP.5 Completion Review")

    plan = PLAN.read_text(encoding="utf-8")
    for token in [
        "## Accounting authority and provenance limit",
        "## Differential cost mapping",
        "## Priority and lowest-cost validation sequence",
        "## SRP.4 completion boundary",
        "M2 queue/staging",
        "P3 stage",
        "R5 descriptor maintenance",
        "R4 numeric/partial state",
        "Payload and metadata service coordinates remain non-additive.",
        "does **not** claim to have re-hashed",
        "does not rerun A4",
    ]:
        assert token in plan, token
    assert "synthesis" not in plan.split("## SRP.4 completion boundary", 1)[1]
    print("PASS: SRP.4 maps all 30 partition records without recomputing A4 cost")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
