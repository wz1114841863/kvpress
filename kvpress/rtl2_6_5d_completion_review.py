"""No-model RTL2.6.5d cross-owner completion review.

The review is deliberately stricter than a list of individually passing
sub-slices.  A production-transaction-dataflow disposition needs one
same-instance, real-owner trace from the retained R3 read/publication path
through S2/source/terminal and retirement/reclaim.  A testbench event trace
may validate field/oracle semantics but may not silently replace that witness.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


REVIEW_VERSION = "kvzap-route-a-rtl2-6-5d-cross-owner-completion-review-1.0"
REVIEW_STATUS = "review_completed_no_pass_missing_same_instance_real_owner_trace"
REQUIRED_EVENTS = (
    "request_accept", "fragment_deliver", "write_commit", "descriptor_durable",
    "metadata_publish_commit", "authority_transition", "source_deliverable",
    "consumer_partial_commit", "source_release", "merge_request",
    "attention_terminal", "descriptor_invalidate", "page_free", "retire_ack",
)


class RTL265dCompletionReviewError(ValueError):
    """The completion review would overstate cross-owner integration evidence."""


def load_review(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL265dCompletionReviewError("RTL2.6.5d review root must be an object")
    return value


def _event_names(schema: Mapping[str, Any]) -> tuple[str, ...]:
    records = schema.get("event_records")
    if not isinstance(records, list):
        raise RTL265dCompletionReviewError("immutable RTL2 event schema lacks records")
    names = tuple(record.get("event") for record in records if isinstance(record, Mapping))
    if names != REQUIRED_EVENTS:
        raise RTL265dCompletionReviewError("immutable RTL2 event order differs from the completion review")
    return names


def validate_review(review: Mapping[str, Any], schema: Mapping[str, Any], capture_manifest: Mapping[str, Any]) -> None:
    if review.get("schema_version") != REVIEW_VERSION or review.get("status") != REVIEW_STATUS:
        raise RTL265dCompletionReviewError("unexpected RTL2.6.5d review version/status")
    events = _event_names(schema)
    if tuple(capture_manifest.get("captured_event_order", ())) != events:
        raise RTL265dCompletionReviewError("RTL2.6.5c capture does not preserve all immutable events")
    if capture_manifest.get("status") != "testbench_accepted_carrier_capture_and_oracle_replay":
        raise RTL265dCompletionReviewError("RTL2.6.5c capture status drift")

    evidence = review.get("evidence")
    if not isinstance(evidence, list) or len(evidence) != 4:
        raise RTL265dCompletionReviewError("review requires the four named closure evidence records")
    records = {item.get("id"): item for item in evidence if isinstance(item, Mapping)}
    expected = {"rtl2_6_5a2", "rtl2_6_4", "rtl2_6_5b", "rtl2_6_5c"}
    if set(records) != expected:
        raise RTL265dCompletionReviewError("review evidence set drift")
    if records["rtl2_6_5a2"].get("scope") != "real_r3_pack_read_to_atomic_publication":
        raise RTL265dCompletionReviewError("R3 publication evidence scope drift")
    if records["rtl2_6_4"].get("scope") != "real_publication_to_s2_to_fault_terminal":
        raise RTL265dCompletionReviewError("publication/S2/terminal evidence scope drift")
    if records["rtl2_6_5b"].get("scope") != "real_terminal_to_reclaim_to_retire_ack":
        raise RTL265dCompletionReviewError("terminal/reclaim evidence scope drift")
    if records["rtl2_6_5c"].get("scope") != "accepted_carrier_event_capture_and_python_replay":
        raise RTL265dCompletionReviewError("event replay evidence scope drift")
    if not all(item.get("passed") is True for item in records.values()):
        raise RTL265dCompletionReviewError("review cannot use an unpassed closure input")

    bridge = review.get("same_instance_real_owner_trace")
    if not isinstance(bridge, Mapping):
        raise RTL265dCompletionReviewError("review lacks same-instance trace assessment")
    if bridge.get("present") is not False:
        raise RTL265dCompletionReviewError("review may not invent the missing same-instance trace")
    required_gap = "r3_publication_to_s2_service_to_terminal_to_reclaim_same_instance"
    if bridge.get("missing_link") != required_gap:
        raise RTL265dCompletionReviewError("same-instance gap must remain explicit")

    disposition = review.get("disposition")
    if not isinstance(disposition, Mapping):
        raise RTL265dCompletionReviewError("review lacks disposition")
    if disposition.get("rtl2_production_transaction_dataflow_complete") is not False:
        raise RTL265dCompletionReviewError("missing same-instance trace cannot authorize RTL2 completion")
    if disposition.get("next_required_closure") != "testbench_same_instance_real_owner_retained_transaction_witness":
        raise RTL265dCompletionReviewError("review must name the exact remaining closure")
    forbidden = set(review.get("forbidden", ()))
    if not {"production-top bridge", "numeric datapath claim", "timing throughput or PPA claim", "new A4 DSE"} <= forbidden:
        raise RTL265dCompletionReviewError("review forbidden boundary drift")


def validate_source_hashes(review: Mapping[str, Any], root: str | Path) -> None:
    base = Path(root).resolve()
    sources = review.get("source_sha256")
    if not isinstance(sources, Mapping) or not sources:
        raise RTL265dCompletionReviewError("review must hash-bind its sources")
    for relative, expected in sources.items():
        path = (base / str(relative)).resolve()
        if base not in path.parents or not path.is_file() or not isinstance(expected, str) or len(expected) != 64:
            raise RTL265dCompletionReviewError("invalid review source hash")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RTL265dCompletionReviewError(f"hash-bound source drift: {relative}")


def load_and_validate(review_path: str | Path, schema_path: str | Path, capture_manifest_path: str | Path, root: str | Path) -> None:
    review = load_review(review_path)
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    capture_manifest = json.loads(Path(capture_manifest_path).read_text(encoding="utf-8"))
    validate_review(review, schema, capture_manifest)
    validate_source_hashes(review, root)
