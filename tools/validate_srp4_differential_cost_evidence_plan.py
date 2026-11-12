#!/usr/bin/env python3
"""Validate the bounded SRP.4 differential-cost evidence plan."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/synthesis_eligibility_manifest.json"


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == (
        "kvzap-route-a-srp-0-5-inventory-partition-eligibility-requirements-cost-review-1.6"
    )
    assert data["status"] == "srp_0_5_completion_review_conditional_pass"
    srp4 = data["srp4_differential_cost_evidence_plan"]
    assert srp4["status"] == "complete_evidence_planning_only"
    all_partition_ids = {item["id"] for item in data["partition_records"]}
    rows = srp4["cost_mapping_rows"]
    mapped_ids = [partition_id for row in rows for partition_id in row["partition_ids"]]
    assert len(mapped_ids) == len(all_partition_ids)
    assert len(set(mapped_ids)) == len(mapped_ids)
    assert set(mapped_ids) == all_partition_ids
    # The saved common-S2 row uses this more specific, non-cancellable role.
    allowed_coverage = set(srp4["mapping_status_values"]) | {"paired_access_role_mapped_not_cancellable"}
    assert all(row["coverage"] in allowed_coverage for row in rows)
    assert {"P1", "P2", "P3", "P4", "gate", "excluded"} <= {
        row["priority"] for row in rows
    }
    integration = next(row for row in rows if row["id"] == "integration_shell")
    assert integration["coverage"] == "deferred_until_future_top_selection"
    assert integration["deferred_cost_required"] is True
    m2 = next(row for row in rows if row["id"] == "m2_fixed_and_control_entry")
    assert len(m2["accounted_subterms"]) == 2
    assert len(m2["omitted_subterms"]) == 4
    assert "queue/staging" in m2["omitted_subterms"][0]
    assert "unresolved evidence" in srp4["unobservable_action_policy"]
    assert srp4["next_gate"] == "SRP.5 Completion Review; not started by this record."
    assert "srp5_completion_review" in data
    assert data["next_gate"].startswith("SRP planning has conditional-pass closure")

    print(f"PASS: SRP.4 maps all {len(all_partition_ids)} partition records without recomputing A4 cost")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
