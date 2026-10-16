#!/usr/bin/env python3
"""Validate the bounded SRP.5 completion-review record."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/synthesis_eligibility_manifest.json"
REVIEW = ROOT / "analysis/srp5_completion_review.md"


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == (
        "kvzap-route-a-srp-0-5-inventory-partition-eligibility-requirements-cost-review-1.6"
    )
    assert data["status"] == "srp_0_5_completion_review_conditional_pass"
    srp5 = data["srp5_completion_review"]
    assert srp5["status"] == (
        "conditional_pass_to_separately_authorized_realization_choice_planning_only"
    )
    assert len(srp5["reviewed_srp_inputs"]) == 5
    checks = srp5["closure_checks"]
    assert checks["structural_children"] == 40
    assert checks["partition_records"] == 30
    assert checks["srp3_realization_due_records"] == 9
    assert checks["srp4_exact_partition_mapping"] is True
    assert checks["logical_contract_mapped_and_physical_wrapper_pending"] is True
    assert checks["cost_evidence_route_or_stop_condition_for_each_relevant_record"] is True
    authorization = srp5["authorization"]
    assert authorization["allowed"].startswith("separately authorized")
    assert len(authorization["candidate_entry_requirements"]) == 6
    assert {"synthesis/lint/formal flow", "complete LLM inference"} <= set(authorization["forbidden"])
    assert set(srp5["blockers"]) == {
        "future_synthesis_top_unselected",
        "missing_owner_carried_action_fields",
    }
    resolved = srp5["resolved_blockers"]["a4141_materialized_report_absent"]
    assert resolved["status"] == "resolved_for_read_only_ledger_budget_revalidation"
    assert Path(ROOT / resolved["record"]).is_file()
    recovery = data["a4141_local_provenance_recovery"]
    assert recovery["status"] == "complete_read_only_recovery_and_preflight"
    assert recovery["recovered_artifact_count"] == 9
    assert srp5["next_gate"].endswith("not started by this record")
    assert data["next_gate"].startswith("SRP planning has conditional-pass closure")

    review = REVIEW.read_text(encoding="utf-8")
    for token in [
        "## Closure review",
        "## Authorization boundary",
        "## Blockers versus normal next-stage work",
        "## Required stop conditions for a candidate review",
        "conditional_pass_to_separately_authorized_realization_choice_planning_only",
        "unresolved evidence",
        "A4.14.1 report-availability blocker",
        "Resolved for read-only ledger/budget revalidation",
        "Future synthesis top not selected",
        "one-record-at-a-time",
    ]:
        assert token in review, token
    print("PASS: SRP.5 conditionally closes planning without authorizing implementation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
