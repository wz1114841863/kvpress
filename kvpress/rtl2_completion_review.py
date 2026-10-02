"""No-model validation for the RTL2.0 pre-behavior completion review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kvpress.rtl2_activation_manifest import REQUIRED_AMENDMENTS, load_manifest, validate_manifest
from kvpress.rtl2_scoreboard_event_schema import load_schema, validate_schema


REVIEW_VERSION = "kvzap-route-a-rtl2-0-completion-review-1.0"
REVIEW_STATUS = "rtl2_0_completion_review_pass_historical_pre_behavior"
REQUIRED_LABELS = frozenset({"no model/GPU", "no PPA claim", "no RTL correctness claim", "no new A4 DSE"})


class RTL2CompletionReviewError(ValueError):
    """Raised when the completion review ceases to be a narrow pre-behavior PASS."""


def load_review(path: str | Path) -> dict[str, Any]:
    """Load one explicit review manifest."""
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RTL2CompletionReviewError("review root must be a JSON object")
    return loaded


def validate_review(review: dict[str, Any], activation: dict[str, Any], schema: dict[str, Any], root: str | Path = ".") -> None:
    """Validate the review inventory; it intentionally proves no datapath behavior."""
    root_path = Path(root)
    try:
        validate_manifest(activation)
        validate_schema(schema, activation)
    except ValueError as error:
        raise RTL2CompletionReviewError(f"review input is invalid: {error}") from error
    if review.get("schema_version") != REVIEW_VERSION or review.get("status") != REVIEW_STATUS:
        raise RTL2CompletionReviewError("unexpected RTL2.0 completion-review version or status")
    if review.get("activation_manifest") != "analysis/rtl2_0_activation_manifest.json":
        raise RTL2CompletionReviewError("review must bind the RTL2.0 activation manifest")
    if review.get("scoreboard_schema") != "analysis/rtl2_scoreboard_event_schema.json":
        raise RTL2CompletionReviewError("review must bind the versioned RTL2 scoreboard schema")

    checks = _object(review, "review_checks")
    if checks.get("all_seven_amendments_closed") is not True or checks.get("top_composition_only") is not True:
        raise RTL2CompletionReviewError("review must close all amendments and retain a composition-only top")
    if checks.get("behavioral_activation_started") is not False:
        raise RTL2CompletionReviewError("completion review must remain before behavioral activation")
    if checks.get("next_authorized_phase") != "rtl2_1a_only":
        raise RTL2CompletionReviewError("completion review may authorize only RTL2.1a")

    top_rule = _object(activation, "top_rule")
    if top_rule.get("composition_only") is not True:
        raise RTL2CompletionReviewError("activation manifest no longer describes a composition-only top")
    if set(_string_list(checks, "top_forbidden_owners")) != set(_string_list(top_rule, "forbidden")):
        raise RTL2CompletionReviewError("review top exclusions differ from the activation manifest")
    if not isinstance(review.get("reviewed_commit"), str) or not review["reviewed_commit"]:
        raise RTL2CompletionReviewError("historical completion review must identify its reviewed commit")
    top_source = review.get("top_source")
    if not isinstance(top_source, str) or not top_source:
        raise RTL2CompletionReviewError("review must name the historically inspected top source")
    # This review is deliberately a pre-behavior snapshot.  Do not compare its
    # former tie-offs to a later live top: later phase contracts own such
    # changes.  Keep the recorded list so the review remains auditable.
    _string_list(review, "required_pre_behavior_tie_offs")

    closures = _records(review, "amendment_closures")
    closure_by_id = _unique_by_id(closures)
    if frozenset(closure_by_id) != REQUIRED_AMENDMENTS:
        raise RTL2CompletionReviewError("review amendment set differs from the exact seven RTL2.0 amendments")
    activation_by_id = _unique_by_id(_records(activation, "required_amendments"))
    for amendment_id, closure in closure_by_id.items():
        activation_record = activation_by_id[amendment_id]
        if closure.get("closure_status") != activation_record.get("closure_status") or closure.get("artifact") != activation_record.get("closure_artifact"):
            raise RTL2CompletionReviewError(f"review closure differs from activation manifest: {amendment_id}")
        artifact = closure.get("artifact")
        if not isinstance(artifact, str) or not (root_path / artifact).is_file():
            raise RTL2CompletionReviewError(f"review closure artifact does not exist: {amendment_id}")

    if review.get("required_event_count") != len(_records(activation, "event_records")):
        raise RTL2CompletionReviewError("review event count differs from activation inventory")
    if review.get("required_carrier_count") != len(_records(activation, "carrier_records")):
        raise RTL2CompletionReviewError("review carrier count differs from activation inventory")
    disposition = _object(review, "disposition")
    if disposition.get("rtl2_0_pass") is not True or "RTL2.1a" not in disposition.get("pass_scope", ""):
        raise RTL2CompletionReviewError("review PASS must be narrow and explicitly limited to RTL2.1a")
    if not REQUIRED_LABELS.issubset(set(_string_list(review, "evidence_labels"))):
        raise RTL2CompletionReviewError("review evidence labels must preserve no-model/no-PPA/no-RTL boundaries")


def load_and_validate(review_path: str | Path, activation_path: str | Path, schema_path: str | Path, root: str | Path = ".") -> None:
    """Load the review and all its bound artifacts."""
    validate_review(load_review(review_path), load_manifest(activation_path), load_schema(schema_path), root)


def _object(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise RTL2CompletionReviewError(f"{key} must be a JSON object")
    return value


def _records(parent: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = parent.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RTL2CompletionReviewError(f"{key} must be a list of objects")
    return value


def _string_list(parent: dict[str, Any], key: str) -> list[str]:
    value = parent.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise RTL2CompletionReviewError(f"{key} must be a nonempty string list")
    return value


def _unique_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        identifier = record.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in result:
            raise RTL2CompletionReviewError("review record must have one unique id")
        result[identifier] = record
    return result
