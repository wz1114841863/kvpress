"""No-model RTL2.6 completion-review entry audit.

This validator records whether the explicit RTL2 event vocabulary is actually
bound before a reviewer may claim one end-to-end retained transaction. It does
not model a controller, numeric datapath, memory timing, or PPA.
"""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
from typing import Any

REVIEW_VERSION = "kvzap-route-a-rtl2-6-entry-audit-1.0"
ENTRY_STATUS = "rtl2_6_entry_audit_incomplete_scoreboard_and_transaction_witness"
BOUND_STATE = "bound_and_emittable_in_rtl2_5_5_test_harness"
BOUND_TERMINAL_STATE = "bound_and_emittable_in_rtl2_4_3_test_harness"

class RTL26CompletionReviewError(ValueError): pass

def load_review(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise RTL26CompletionReviewError("review root must be an object")
    return value

def validate_entry_audit(review: dict[str, Any], schema: dict[str, Any], overlay: dict[str, Any]) -> None:
    if review.get("schema_version") != REVIEW_VERSION or review.get("status") != ENTRY_STATUS:
        raise RTL26CompletionReviewError("unexpected RTL2.6 entry-audit version or status")
    schema_events = [item["event"] for item in schema.get("event_records", [])]
    if review.get("required_events") != schema_events:
        raise RTL26CompletionReviewError("required events must exactly preserve the immutable schema order")
    overrides = {item["event"]: item for item in overlay.get("overrides", [])}
    actual_bound = [event for event in schema_events if overrides.get(event, {}).get("emission_state") in {BOUND_STATE, BOUND_TERMINAL_STATE}]
    if review.get("bound_events") != actual_bound:
        raise RTL26CompletionReviewError("bound event inventory drift")
    missing = [event for event in schema_events if event not in actual_bound]
    if review.get("missing_event_bindings") != missing:
        raise RTL26CompletionReviewError("missing event inventory drift")
    if review.get("complete_retained_transaction_witness") is not False:
        raise RTL26CompletionReviewError("entry audit cannot claim an absent complete retained transaction")
    ingress = review.get("remaining_verification_ingress")
    if not isinstance(ingress, list) or not ingress or not all(isinstance(item, dict) and item.get("port") and item.get("owner") and item.get("justification") for item in ingress):
        raise RTL26CompletionReviewError("every remaining verification ingress needs port, owner, and justification")
    if review.get("disposition", {}).get("rtl2_production_transaction_dataflow_complete") is not False:
        raise RTL26CompletionReviewError("incomplete entry audit may not authorize RTL2 completion")

def validate_source_hashes(review: dict[str, Any], root: str | Path) -> None:
    root = Path(root)
    hashes = review.get("source_sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise RTL26CompletionReviewError("entry audit must hash-bind its reviewed sources")
    for relative, expected in hashes.items():
        if not isinstance(relative, str) or not isinstance(expected, str) or len(expected) != 64:
            raise RTL26CompletionReviewError("invalid source hash record")
        actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise RTL26CompletionReviewError(f"hash-bound source drift: {relative}")

def load_and_validate(review_path: str | Path, schema_path: str | Path, overlay_path: str | Path, root: str | Path) -> None:
    review = load_review(review_path)
    validate_entry_audit(review, json.loads(Path(schema_path).read_text(encoding="utf-8")), json.loads(Path(overlay_path).read_text(encoding="utf-8")))
    validate_source_hashes(review, root)
