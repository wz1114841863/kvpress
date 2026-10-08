"""No-model validator for RTL2.6.5e's same-instance retained-path witness."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


VERSION = "kvzap-route-a-rtl2-6-5e-same-instance-witness-1.0"
STATUS = "implemented_directed_tested_no_model_functional_completion"
ALL_EVENTS = (
    "request_accept", "fragment_deliver", "write_commit", "descriptor_durable",
    "metadata_publish_commit", "authority_transition", "source_deliverable",
    "consumer_partial_commit", "source_release", "merge_request",
    "attention_terminal", "descriptor_invalidate", "page_free", "retire_ack",
)


class RTL265eReviewError(ValueError):
    """The final witness/re-review record would exceed its testbench evidence."""


def load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL265eReviewError("RTL2.6.5e manifest root must be an object")
    return value


def validate(manifest: Mapping[str, Any], capture: Mapping[str, Any], prior_review: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != VERSION or manifest.get("status") != STATUS:
        raise RTL265eReviewError("unexpected RTL2.6.5e version/status")
    witness = manifest.get("same_instance_witness")
    expected = {
        "r3_pack_read_to_publication": True,
        "publication_to_s2_service": True,
        "s2_four_consumer_to_r4_terminal": True,
        "same_r5_durable_reclaim_to_retire_ack": True,
        "stale_association_fail_closed": True,
        "bounded_terminal_ready_low_nonmutation": True,
    }
    if witness != expected:
        raise RTL265eReviewError("same-instance witness obligations drift")
    if tuple(capture.get("captured_event_order", ())) != ALL_EVENTS:
        raise RTL265eReviewError("accepted-carrier replay lacks immutable event coverage")
    if set(capture.get("replay_cases", ())) != {"success_all_fourteen_event_types", "fault_fail_closed", "stale_response_rejected", "bounded_legal_ready_low"}:
        raise RTL265eReviewError("accepted-carrier replay case coverage drift")
    prior = prior_review.get("disposition", {})
    if prior.get("next_required_closure") != "testbench_same_instance_real_owner_retained_transaction_witness":
        raise RTL265eReviewError("RTL2.6.5e does not close the prior review's exact gap")
    disposition = manifest.get("disposition", {})
    if disposition.get("rtl2_production_transaction_dataflow_complete") is not True:
        raise RTL265eReviewError("same-instance closure must state its narrow functional disposition")
    if disposition.get("scope") != "testbench_only_functional_transaction_dataflow":
        raise RTL265eReviewError("completion disposition must remain testbench-only")
    forbidden = set(manifest.get("forbidden", ()))
    if not {"production-top bridge", "numeric datapath claim", "timing throughput or PPA claim", "new A4 DSE"} <= forbidden:
        raise RTL265eReviewError("RTL2.6.5e evidence boundary drift")


def validate_hashes(manifest: Mapping[str, Any], root: str | Path) -> None:
    base = Path(root).resolve()
    hashes = manifest.get("source_sha256")
    if not isinstance(hashes, Mapping) or not hashes:
        raise RTL265eReviewError("RTL2.6.5e must hash-bind sources")
    for relative, expected in hashes.items():
        path = (base / str(relative)).resolve()
        if base not in path.parents or not path.is_file() or not isinstance(expected, str) or len(expected) != 64:
            raise RTL265eReviewError("invalid RTL2.6.5e source hash")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RTL265eReviewError(f"hash-bound source drift: {relative}")


def load_and_validate(manifest_path: str | Path, capture_path: str | Path, prior_review_path: str | Path, root: str | Path) -> None:
    manifest = load(manifest_path)
    validate(manifest, load(capture_path), load(prior_review_path))
    validate_hashes(manifest, root)
