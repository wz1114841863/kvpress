#!/usr/bin/env python3
"""Validate the audit-only RTL3.9-C4-P1 C3b event provenance matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_CLASSES = {
    "exact_accepted_outward_observation",
    "exact_accepted_outward_observation_existing_binding",
    "exact_internal_owner_fire_missing_harness_observer",
    "internal_owner_fire_not_exported",
    "internal_owner_fire_incomplete_schema_fields",
    "partial_outward_observation",
    "nonhandshake_owner_state",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix", type=Path,
        default=ROOT / "analysis/rtl3_9_c4_p1_c3b_event_provenance_matrix.json",
        help="C4-P1 matrix to validate",
    )
    parser.add_argument(
        "--schema", type=Path,
        default=ROOT / "analysis/rtl2_scoreboard_event_schema.json",
        help="immutable RTL2 event schema",
    )
    args = parser.parse_args(argv)
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    assert matrix["schema_version"] == "kvzap-route-a-rtl3-9-c4-p1-c3b-event-provenance-matrix-1.0"
    assert matrix["status"] == "complete_audit_only_no_event_capture_authorized"
    schema_events = [record["event"] for record in schema["event_records"]]
    rows = matrix["rows"]
    assert [row["event"] for row in rows] == schema_events
    assert all(row["evidence_class"] in ALLOWED_CLASSES for row in rows)
    assert all(row["capture_authorized"] is False for row in rows)
    by_event = {row["event"]: row for row in rows}
    assert by_event["metadata_publish_commit"]["evidence_class"] == "partial_outward_observation"
    assert by_event["authority_transition"]["evidence_class"] == "exact_accepted_outward_observation"
    assert by_event["attention_terminal"]["evidence_class"] == "exact_accepted_outward_observation_existing_binding"
    assert by_event["page_free"]["evidence_class"] == "exact_internal_owner_fire_missing_harness_observer"
    assert by_event["retire_ack"]["evidence_class"] == "exact_accepted_outward_observation_existing_binding"
    disposition = matrix["disposition"]
    assert disposition["c4_p1_complete"] is True
    assert disposition["c4_functional_event_capture_complete"] is False
    assert disposition["rtl3_completion_review_authorized"] is False
    assert disposition["physical_or_numeric_claim"] is False
    print(f"PASS: RTL3.9-C4-P1 audited {len(rows)} immutable event records; no capture is authorized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
