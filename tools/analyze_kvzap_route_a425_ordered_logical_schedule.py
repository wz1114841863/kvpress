"""A4.2.5 modeled ordered-logical-event schedule study; never a timing trace."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


A425_SCHEMA = "kvzap-route-a425-ordered-logical-schedule-1.0"
A424_SCHEMA = "kvzap-route-a424-ordered-logical-event-gate-1.0"
A422_SCHEMA = "kvzap-route-a422-scheduler-merge-placement-1.0"
A423_SCHEMA = "kvzap-route-a423-scheduler-merge-service-sensitivity-1.0"
SOURCES = ("hot", "pending", "packed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.2.5 modeled Route-A ordered-logical-event schedule study; "
            "no model execution, timestamps, or hardware timing claim."
        )
    )
    parser.add_argument("--ordered-event-manifest", type=Path, required=True)
    parser.add_argument("--placement-report", type=Path, required=True)
    parser.add_argument("--service-sensitivity-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_complete(path: Path, schema: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != schema or payload.get("status") != "complete":
        raise ValueError(f"not a completed {schema} artifact: {path}")
    return payload


def require_true(payload: dict[str, Any], names: tuple[str, ...], label: str) -> None:
    missing = [name for name in names if payload.get("observational_guards", {}).get(name) is not True]
    if missing:
        raise ValueError(f"{label} lacks required guards: {missing}")


def event_path(manifest_path: Path, manifest: dict[str, Any]) -> Path:
    artifact = manifest.get("logical_event_artifact", {})
    name = artifact.get("path")
    if not isinstance(name, str) or not name:
        raise ValueError("A424 lacks logical event artifact path")
    path = manifest_path.parent / name
    if not path.is_file():
        raise FileNotFoundError(path)
    if artifact.get("sha256") != sha256(path):
        raise ValueError("A424 logical event artifact SHA-256 mismatch")
    return path


def load_events(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle if line.strip()]
    if not events:
        raise ValueError("ordered logical event artifact is empty")
    return events


def _decision_by_source(event: dict[str, Any]) -> dict[str, dict[str, Any]]:
    decisions = event.get("source_decisions")
    if not isinstance(decisions, list) or [item.get("source") for item in decisions] != list(SOURCES):
        raise ValueError("each event must record ordered hot/pending/packed decisions")
    result: dict[str, dict[str, Any]] = {}
    for item in decisions:
        source = item["source"]
        outcome = item.get("outcome")
        records = item.get("record_count")
        if outcome not in {"partial", "skip"} or not isinstance(records, int) or records < 0:
            raise ValueError("source decision outcome/record count is malformed")
        if (outcome == "partial") != (records > 0):
            raise ValueError("partial/skip decision must agree with record count")
        result[source] = item
    return result


def validate_events(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Validate A424's logical order without treating it as a service timeline."""
    source_counts: dict[str, Counter[str]] = {source: Counter() for source in SOURCES}
    coverage: dict[int, set[int]] = defaultdict(set)
    count = 0
    for expected_sequence, event in enumerate(events):
        if event.get("logical_event_sequence") != expected_sequence:
            raise ValueError("logical_event_sequence must be contiguous and zero based")
        if event.get("merge_after_source_decisions") is not True:
            raise ValueError("each event must record exactly one post-source merge marker")
        if any("timestamp" in str(key).lower() for key in event):
            raise ValueError("A4.2.5 rejects timestamp-bearing logical events")
        layer, kv_head, query_head, cache_position = (
            event.get("layer"), event.get("kv_head"), event.get("query_head"), event.get("cache_position")
        )
        if not all(isinstance(value, int) and value >= 0 for value in (layer, kv_head, query_head, cache_position)):
            raise ValueError("event layer/head/position fields must be non-negative integers")
        coverage[layer].add(kv_head)
        for source, decision in _decision_by_source(event).items():
            source_counts[source][decision["outcome"]] += 1
        count += 1
    return {
        "event_count": count,
        "merge_marker_count": count,
        "source_outcome_counts": {
            source: {"partial": source_counts[source]["partial"], "skip": source_counts[source]["skip"]}
            for source in SOURCES
        },
        "observed_layer_kv_head_coverage": [
            {"layer": layer, "kv_heads": sorted(heads)} for layer, heads in sorted(coverage.items())
        ],
    }


def verify_manifest_event_summary(a424: dict[str, Any], validation: dict[str, Any]) -> None:
    """Bind the parsed gzip accounting to A424's accepted independent run."""
    summary = a424.get("diagnostic", {}).get("trace_on_independent", {}).get("logical_event_summary", {})
    if summary.get("event_count") != validation["event_count"]:
        raise ValueError("A424 independent event summary count differs from gzip")
    if summary.get("merge_event_count") != validation["merge_marker_count"]:
        raise ValueError("A424 independent merge summary differs from gzip")
    expected_sources = summary.get("by_source", {})
    for source in SOURCES:
        expected = expected_sources.get(source, {})
        observed = validation["source_outcome_counts"][source]
        if expected.get("partial_attention_events") != observed["partial"]:
            raise ValueError(f"A424 {source} partial summary differs from gzip")
        if expected.get("empty_source_skip_events") != observed["skip"]:
            raise ValueError(f"A424 {source} skip summary differs from gzip")
    if summary.get("observed_layer_kv_heads") != validation["observed_layer_kv_head_coverage"]:
        raise ValueError("A424 layer/KV-head coverage summary differs from gzip")


def _event_group(event: dict[str, Any]) -> tuple[int, int]:
    return int(event["layer"]), int(event["kv_head"])


def _active_sources(event: dict[str, Any]) -> list[str]:
    cached = event.get("_a425_active_sources")
    if cached is not None:
        return list(cached)
    decisions = _decision_by_source(event)
    return [source for source in SOURCES if decisions[source]["outcome"] == "partial"]


def normalize_events_for_schedule(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retain only validated scheduling keys, avoiding repeated JSON interpretation."""
    return [
        {
            "logical_event_sequence": event["logical_event_sequence"],
            "layer": event["layer"],
            "kv_head": event["kv_head"],
            "_a425_active_sources": tuple(_active_sources(event)),
        }
        for event in events
    ]


def _common_schedule_summary(
    *, events: list[dict[str, Any]], source_work_units: float, merge_work_units: float, submission_work_units: float
) -> dict[str, Any]:
    partials = Counter(source for event in events for source in _active_sources(event))
    return {
        "logical_event_count": len(events),
        "logical_merge_count": len(events),
        "logical_partial_state_count_by_source": dict(partials),
        "logical_partial_state_count": sum(partials.values()),
        "logical_empty_source_outcome_count": len(events) * len(SOURCES) - sum(partials.values()),
        "declared_source_service_work_units_per_partial": source_work_units,
        "declared_merge_work_units_per_merge": merge_work_units,
        "declared_logical_submission_spacing_work_units": submission_work_units,
    }


def simulate_co_located(
    *, events: list[dict[str, Any]], source_work_units: float, merge_work_units: float, submission_work_units: float
) -> dict[str, Any]:
    """Model local source-plus-merge ownership in virtual work positions only."""
    availability: dict[tuple[int, int], float] = defaultdict(float)
    max_submit_to_complete = 0.0
    max_completion = 0.0
    for event in events:
        submission = event["logical_event_sequence"] * submission_work_units
        group = _event_group(event)
        start = max(float(submission), availability[group])
        completion = start + len(_active_sources(event)) * source_work_units + merge_work_units
        availability[group] = completion
        max_submit_to_complete = max(max_submit_to_complete, completion - submission)
        max_completion = max(max_completion, completion)
    result = _common_schedule_summary(
        events=events, source_work_units=source_work_units, merge_work_units=merge_work_units,
        submission_work_units=submission_work_units,
    )
    result.update({
        "organization": "co_located_logical_owner",
        "logical_partial_state_exports": 0,
        "declared_transfer_work_units_per_export": "not_applicable_local_merge",
        "declared_reduction_dispatch_work_units_per_merge": "not_applicable_local_merge",
        "model_completion_work_position": max_completion,
        "model_max_submission_to_merge_complete_work_units": max_submit_to_complete,
        "model_max_partial_ready_to_merge_start_work_units": "not_applicable_local_merge",
        "interpretation": "Each (layer, KV head) logical owner serializes active source decisions then its local merge. Work positions are declared model units, not cycles, timestamps, or latency.",
    })
    return result


def simulate_split_source(
    *,
    events: list[dict[str, Any]],
    source_work_units: float,
    merge_work_units: float,
    transfer_work_units: float,
    reduction_dispatch_work_units: float,
    submission_work_units: float,
) -> dict[str, Any]:
    """Model independent source lanes and a local reduction dependency in work units."""
    source_availability: dict[tuple[int, int, str], float] = defaultdict(float)
    reducer_availability: dict[tuple[int, int], float] = defaultdict(float)
    exports = 0
    max_submit_to_complete = 0.0
    max_ready_to_merge_start = 0.0
    max_completion = 0.0
    for event in events:
        submission = event["logical_event_sequence"] * submission_work_units
        group = _event_group(event)
        ready_positions: list[float] = []
        for source in _active_sources(event):
            lane = (group[0], group[1], source)
            source_start = max(float(submission), source_availability[lane])
            ready = source_start + source_work_units + transfer_work_units
            source_availability[lane] = ready
            ready_positions.append(ready)
            exports += 1
        if not ready_positions:
            raise AssertionError("A424 hot partial invariant should ensure one active source")
        partial_ready = max(ready_positions)
        merge_start = max(partial_ready, reducer_availability[group])
        completion = merge_start + reduction_dispatch_work_units + merge_work_units
        reducer_availability[group] = completion
        max_ready_to_merge_start = max(max_ready_to_merge_start, merge_start - partial_ready)
        max_submit_to_complete = max(max_submit_to_complete, completion - submission)
        max_completion = max(max_completion, completion)
    result = _common_schedule_summary(
        events=events, source_work_units=source_work_units, merge_work_units=merge_work_units,
        submission_work_units=submission_work_units,
    )
    result.update({
        "organization": "split_source_logical_dependency",
        "logical_partial_state_exports": exports,
        "declared_transfer_work_units_per_export": transfer_work_units,
        "declared_reduction_dispatch_work_units_per_merge": reduction_dispatch_work_units,
        "model_completion_work_position": max_completion,
        "model_max_submission_to_merge_complete_work_units": max_submit_to_complete,
        "model_max_partial_ready_to_merge_start_work_units": max_ready_to_merge_start,
        "interpretation": "Each non-empty source exports an abstract partial-softmax state to a local reduction dependency. Work positions are declared model units, not cycles, timestamps, queue occupancy, or latency.",
    })
    return result


def validate_scope(a424: dict[str, Any], a422: dict[str, Any]) -> None:
    config = a424.get("config", {})
    scope = a422.get("report", {}).get("scope", {})
    expected = {
        "threshold": -4.0, "hot_window_tokens": 128, "page_tokens": 64,
        "admission_budget_retained_tokens_per_layer_call": 512,
    }
    actual = {
        "threshold": config.get("threshold"), "hot_window_tokens": config.get("window_size"),
        "page_tokens": config.get("page_tokens"),
        "admission_budget_retained_tokens_per_layer_call": config.get("admission_budget"),
    }
    if actual != expected or any(scope.get(key) != value for key, value in expected.items()):
        raise ValueError("A424/A422 policy scope differs from the required Route-A point")


def validate_prior_bindings(a422_path: Path, a422: dict[str, Any], a423: dict[str, Any]) -> None:
    if a423.get("config", {}).get("placement_report_sha256") != sha256(a422_path):
        raise ValueError("A423 is not bound to the supplied A422 placement report")
    for key, label in (
        ("cross_horizon_accounting_sha256", "A4168"),
        ("observed_resource_contract_sha256", "A4200"),
        ("contract_sensitivity_matrix_sha256", "A4201"),
    ):
        if not a422.get("config", {}).get(key):
            raise ValueError(f"A422 lacks {label} provenance")


def build_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for submission in (0.0, 1.0, 4.0):
        for source_work in (1.0, 4.0):
            for merge_work in (1.0, 4.0):
                co_located = simulate_co_located(
                    events=events, source_work_units=source_work, merge_work_units=merge_work,
                    submission_work_units=submission,
                )
                for transfer_work in (0.0, 1.0, 4.0):
                    for dispatch_work in (0.0, 1.0, 4.0):
                        split = simulate_split_source(
                            events=events, source_work_units=source_work, merge_work_units=merge_work,
                            transfer_work_units=transfer_work, reduction_dispatch_work_units=dispatch_work,
                            submission_work_units=submission,
                        )
                        rows.append({
                            "declared_logical_submission_spacing_work_units": submission,
                            "declared_source_service_work_units_per_partial": source_work,
                            "declared_merge_work_units_per_merge": merge_work,
                            "declared_transfer_work_units_per_export": transfer_work,
                            "declared_reduction_dispatch_work_units_per_merge": dispatch_work,
                            "co_located": co_located,
                            "split_source": split,
                            "split_minus_co_located_model_completion_work_position": (
                                split["model_completion_work_position"] - co_located["model_completion_work_position"]
                            ),
                            "interpretation": "The delta compares only these declared virtual work schedules. It is not a latency, throughput, or hardware-placement result.",
                        })
    return rows


def build_report(*, events: list[dict[str, Any]], event_validation: dict[str, Any]) -> dict[str, Any]:
    scheduled_events = normalize_events_for_schedule(events)
    return {
        "evidence_classification": {
            "a424_ordered_events": "functional logical-observation artifact with trace-derived event structure; no timestamps",
            "a422_a423": "modeled placement and marginal fan-in/service contract inputs",
            "this_study": "modeled declared-work dependency schedule",
        },
        "method": {
            "recorded_order_use": "Use A424 only as a total logical submission order. Submission spacing is an explicit sensitivity axis because the recorder has no time or completion events.",
            "co_located_organization": "One logical (layer, KV head) owner serializes non-empty hot/pending/packed source decisions and then merges locally.",
            "split_source_organization": "Non-empty source decisions use independent logical lanes keyed by (layer, KV head, source), then export A422 partial-softmax state to a local reduction dependency keyed by (layer, KV head).",
            "partial_state_interface": ["partial max", "partial normalization state", "partial value accumulator", "valid/empty"],
            "not_modeled": "No recorded source completion, reduction arrival, memory service, controller behavior, or physical queue is introduced.",
        },
        "sensitivity_axes": {
            "logical_submission_spacing_work_units": [0.0, 1.0, 4.0],
            "source_service_work_units_per_partial": [1.0, 4.0],
            "merge_work_units_per_merge": [1.0, 4.0],
            "partial_state_transfer_work_units_per_export": [0.0, 1.0, 4.0],
            "reduction_dispatch_work_units_per_merge": [0.0, 1.0, 4.0],
        },
        "event_validation": event_validation,
        "rows": build_rows(scheduled_events),
        "boundaries": [
            "This is a modeled declared-work study over an ordered logical invocation artifact. It executes no model and records no measured runtime.",
            "Logical submission order is not source service/completion order, reduction arrival order, Python/CUDA/hardware time, or a real scheduler trace.",
            "Work positions and dependency waits are abstract model quantities, not cycles, latency, throughput, queue occupancy, FIFO depth, reducer count, or controller timing.",
            "No result is HBM traffic, energy, area, frequency, hardware acceleration, final scheduler/placement selection, hardware sizing, or RTL readiness.",
        ],
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a424 = load_complete(args.ordered_event_manifest, A424_SCHEMA)
    a422 = load_complete(args.placement_report, A422_SCHEMA)
    a423 = load_complete(args.service_sensitivity_report, A423_SCHEMA)
    require_true(a424, (
        "logical_event_has_no_timestamps", "ordered_event_all_layer_all_kv_head_coverage",
        "ordered_event_source_decisions_partition_merges", "trace_on_forced_logits_close",
        "trace_on_independent_tokens_equal_trace_off",
    ), "A424")
    require_true(a422, (
        "a4168_accounting_verified", "a4200_observed_contract_verified", "a4201_modeled_range_verified",
        "co_located_and_split_interfaces_explicit", "no_model_execution",
    ), "A422")
    require_true(a423, (
        "a4168_accounting_verified", "a422_placement_contract_verified", "marginal_fan_in_bounds_conserved",
        "no_service_timeline_inferred", "no_model_execution",
    ), "A423")
    validate_scope(a424, a422)
    validate_prior_bindings(args.placement_report, a422, a423)
    events_file = event_path(args.ordered_event_manifest, a424)
    events = load_events(events_file)
    validation = validate_events(events)
    if validation["event_count"] != a424.get("logical_event_artifact", {}).get("event_count"):
        raise ValueError("A424 manifest/event-line count mismatch")
    verify_manifest_event_summary(a424, validation)
    report = build_report(events=events, event_validation=validation)
    config = {
        "ordered_event_manifest": str(args.ordered_event_manifest),
        "ordered_event_manifest_sha256": sha256(args.ordered_event_manifest),
        "ordered_logical_event_file": str(events_file),
        "ordered_logical_event_file_sha256": sha256(events_file),
        "placement_report": str(args.placement_report),
        "placement_report_sha256": sha256(args.placement_report),
        "service_sensitivity_report": str(args.service_sensitivity_report),
        "service_sensitivity_report_sha256": sha256(args.service_sensitivity_report),
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a425_ordered_logical_schedule_report.json"
    manifest = {
        "schema_version": A425_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "report": report,
        "observational_guards": {
            "a424_semantic_and_logical_event_guards_verified": True, "a422_a423_provenance_verified": True,
            "policy_scope_verified": True, "logical_event_sequence_and_source_merge_partition_verified": True,
            "logical_event_accounting_matches_a424_independent_summary": True,
            "logical_events_have_no_timestamps": True, "declared_work_axes_explicit": True,
            "no_hardware_parameter_selected": True, "no_model_execution": True,
        },
        "boundaries": report["boundaries"],
    }
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.2.5 modeled ordered logical schedule completed: {output}")


if __name__ == "__main__":
    main()
