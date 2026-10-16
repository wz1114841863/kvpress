#!/usr/bin/env python3
"""Validate the bounded SRP.3 realization-requirements planning record."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/synthesis_eligibility_manifest.json"
PLAN = ROOT / "analysis/srp3_realization_requirements_decision_plan.md"

EXPECTED_IDS = {
    "m2_storage_realization",
    "p3_pending_hbm_backing",
    "p3_payload_stage_page",
    "r5_availability_state",
    "r5_descriptor_hbm_region",
    "s2_common_payload_gqa_control",
    "s2_incremental_sidecar_storage",
    "r4_numeric_partial_state",
    "external_memory_service",
}


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == (
        "kvzap-route-a-srp-0-5-inventory-partition-eligibility-requirements-cost-review-1.6"
    )
    assert data["status"] == "srp_0_5_completion_review_conditional_pass"
    srp3 = data["srp3_realization_requirements_decision_planning"]
    assert srp3["status"] == "complete_requirements_planning_only"
    assert set(srp3["required_record_ids"]) == EXPECTED_IDS
    assert len(srp3["record_plans"]) == len(EXPECTED_IDS)
    assert {item["id"] for item in srp3["record_plans"]} == EXPECTED_IDS
    assert set(srp3["mapping_status_meaning"]) == {
        "logical_contract_mapped",
        "physical_wrapper_mapping_pending",
    }
    for item in srp3["record_plans"]:
        assert item["responsible_semantic_module"]
        assert item["decision_stage"].startswith("separate ")
        assert item["review_authority"] == (
            "Route-A realization-choice review with explicit human approval"
        )
        assert item["logical_contract_mapped"] is True
        assert item["logical_contract_refs"]
        assert item["physical_wrapper_mapping_pending"] is True
        assert item["evidence_route"]
        assert item["decision_gate"].startswith("separate ")
        assert item["stop"]
    due_srp3 = {
        item["id"]
        for item in data["partition_records"]
        if item["semantic_mapping_due"] == "SRP.3"
    }
    assert due_srp3 == EXPECTED_IDS
    assert srp3["next_gate"] == "SRP.4 Differential Cost Evidence Plan; not started by this record."
    assert "srp4_differential_cost_evidence_plan" in data
    assert "srp5_completion_review" in data
    assert data["next_gate"].startswith("SRP planning has conditional-pass closure")

    plan = PLAN.read_text(encoding="utf-8")
    for token in [
        "## Requirement and decision register",
        "## Decision ownership and review authority",
        "## Logical contract versus physical wrapper mapping",
        "## Evidence discipline and decision gates",
        "## Completion and next authorization",
        "`metadata_publish_commit`",
        "four-consumer release",
        "A4.14.1",
        "omitted-cost budget",
        "no memory macro, port/bank",
    ]:
        assert token in plan, token
    for record_id in EXPECTED_IDS:
        assert f"`{record_id}`" in plan, record_id
    for phrase in [
        "It selects no memory macro, port/bank",
        "PPA result, or realized DUT.",
        "It authorizes no RTL/wrapper implementation",
        "explicit human approval",
        "physical_wrapper_mapping_pending = true",
    ]:
        assert phrase in plan, phrase
    print("PASS: SRP.3 records nine realization requirements without selecting an implementation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
