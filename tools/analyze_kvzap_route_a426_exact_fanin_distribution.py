"""A4.2.6 exact fan-in accounting from A424 logical events; no timing model."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a423_scheduler_merge_service_sensitivity import fan_in_bounds
from tools.analyze_kvzap_route_a425_ordered_logical_schedule import (
    A424_SCHEMA,
    SOURCES,
    _active_sources,
    event_path,
    load_complete,
    load_events,
    require_true,
    validate_events,
    verify_manifest_event_summary,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


A426_SCHEMA = "kvzap-route-a426-exact-fanin-distribution-1.0"
A423_SCHEMA = "kvzap-route-a423-scheduler-merge-service-sensitivity-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.2.6 exact Route-A logical event fan-in accounting; no model execution or timing claim."
    )
    parser.add_argument("--ordered-event-manifest", type=Path, required=True)
    parser.add_argument("--service-sensitivity-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def combination_label(active_sources: list[str]) -> str:
    if not active_sources:
        raise ValueError("A4.2.6 requires at least one active source per merge")
    return "+".join(active_sources)


def summarize_exact_fanin(events: list[dict[str, Any]]) -> dict[str, Any]:
    fan_in = Counter()
    combinations = Counter()
    by_group: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)
    group_events = Counter()
    for event in events:
        active = _active_sources(event)
        name = {1: "one_active_source", 2: "two_active_sources", 3: "three_active_sources"}.get(len(active))
        if name is None:
            raise ValueError("Route-A event has unsupported source fan-in")
        fan_in[name] += 1
        combinations[combination_label(active)] += 1
        group = (event["layer"], event["kv_head"])
        group_events[group] += 1
        by_group[group][name] += 1
    total = sum(fan_in.values())
    if total != len(events):
        raise AssertionError("fan-in accounting does not cover every event")
    source_rows = []
    for group in sorted(group_events):
        row = {"layer": group[0], "kv_head": group[1], "event_count": group_events[group]}
        for name in ("one_active_source", "two_active_sources", "three_active_sources"):
            row[name] = by_group[group][name]
        source_rows.append(row)
    return {
        "event_count": total,
        "exact_fan_in_event_counts": {
            name: fan_in[name] for name in ("one_active_source", "two_active_sources", "three_active_sources")
        },
        "exact_active_source_combinations": dict(sorted(combinations.items())),
        "layer_kv_head_fan_in_rows": source_rows,
        "groups_with_three_source_event": sum(row["three_active_sources"] > 0 for row in source_rows),
        "three_source_event_fraction": fan_in["three_active_sources"] / total,
    }


def h32_marginals(a423: dict[str, Any]) -> tuple[int, dict[str, int]]:
    rows = [row for row in a423.get("report", {}).get("rows", []) if row.get("horizon") == "h32"]
    if not rows:
        raise ValueError("A423 lacks h32 rows")
    first = rows[0]
    merges = first.get("merge_decisions")
    marginal = first.get("marginal_source_partial_counts")
    if not isinstance(merges, int) or not isinstance(marginal, dict):
        raise ValueError("A423 h32 marginal accounting is malformed")
    if set(marginal) != set(SOURCES) or not all(isinstance(value, int) for value in marginal.values()):
        raise ValueError("A423 h32 source marginals are malformed")
    if any(row.get("merge_decisions") != merges or row.get("marginal_source_partial_counts") != marginal for row in rows):
        raise ValueError("A423 h32 rows disagree on marginal accounting")
    return merges, marginal


def verify_against_a423(*, exact: dict[str, Any], a424_validation: dict[str, Any], a423: dict[str, Any]) -> dict[str, Any]:
    merges, marginals = h32_marginals(a423)
    if exact["event_count"] != merges:
        raise ValueError("A424 event count differs from A423 h32 merge count")
    observed = a424_validation["source_outcome_counts"]
    for source in SOURCES:
        if observed[source]["partial"] != marginals[source]:
            raise ValueError(f"A424 {source} partial accounting differs from A423 h32 marginal")
    bounds = fan_in_bounds(
        merge_calls=merges,
        packed_partials=marginals["packed"],
        pending_partials=marginals["pending"],
    )
    lower = bounds["minimum_three_source_overlap"]
    upper = bounds["maximum_three_source_overlap"]
    for name, count in exact["exact_fan_in_event_counts"].items():
        if not min(lower[name], upper[name]) <= count <= max(lower[name], upper[name]):
            raise ValueError(f"exact {name} count lies outside A423 marginal bound")
    return {
        "a423_h32_marginal_source_partial_counts": marginals,
        "a423_fan_in_bounds": bounds,
        "exact_counts_within_a423_bounds": True,
    }


def validate_scope(a424: dict[str, Any], a423: dict[str, Any]) -> None:
    config = a424.get("config", {})
    scope = a423.get("report", {}).get("scope", {})
    expected = {
        "threshold": -4.0,
        "hot_window_tokens": 128,
        "page_tokens": 64,
        "admission_budget_retained_tokens_per_layer_call": 512,
    }
    actual = {
        "threshold": config.get("threshold"),
        "hot_window_tokens": config.get("window_size"),
        "page_tokens": config.get("page_tokens"),
        "admission_budget_retained_tokens_per_layer_call": config.get("admission_budget"),
    }
    if actual != expected or any(scope.get(key) != value for key, value in expected.items()):
        raise ValueError("A424/A423 policy scope differs from the required Route-A point")


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a424 = load_complete(args.ordered_event_manifest, A424_SCHEMA)
    a423 = load_complete(args.service_sensitivity_report, A423_SCHEMA)
    require_true(a424, (
        "logical_event_has_no_timestamps", "ordered_event_all_layer_all_kv_head_coverage",
        "ordered_event_source_decisions_partition_merges", "trace_on_forced_logits_close",
        "trace_on_independent_tokens_equal_trace_off",
    ), "A424")
    require_true(a423, (
        "a4168_accounting_verified", "a422_placement_contract_verified", "marginal_fan_in_bounds_conserved",
        "no_service_timeline_inferred", "no_model_execution",
    ), "A423")
    validate_scope(a424, a423)
    events_file = event_path(args.ordered_event_manifest, a424)
    events = load_events(events_file)
    validation = validate_events(events)
    if validation["event_count"] != a424.get("logical_event_artifact", {}).get("event_count"):
        raise ValueError("A424 manifest/event-line count mismatch")
    verify_manifest_event_summary(a424, validation)
    exact = summarize_exact_fanin(events)
    a423_comparison = verify_against_a423(exact=exact, a424_validation=validation, a423=a423)
    config = {
        "ordered_event_manifest": str(args.ordered_event_manifest),
        "ordered_event_manifest_sha256": sha256(args.ordered_event_manifest),
        "ordered_logical_event_file": str(events_file),
        "ordered_logical_event_file_sha256": sha256(events_file),
        "service_sensitivity_report": str(args.service_sensitivity_report),
        "service_sensitivity_report_sha256": sha256(args.service_sensitivity_report),
    }
    report = {
        "evidence_classification": {
            "a424": "functional logical-observation artifact with timestamp-free event structure",
            "a423": "modeled marginal fan-in/service sensitivity input",
            "this_study": "no-model exact event-structure accounting for one fixed workload",
        },
        "event_validation": validation,
        "exact_fan_in": exact,
        "a423_comparison": a423_comparison,
        "boundaries": [
            "This report accounts for the accepted A424 logical event structure at one fixed Qwen3-8B request. It executes no model and records no timing.",
            "Exact active-source combinations do not reveal source service/completion order, reduction arrival, physical queue occupancy, FIFO depth, engine utilization, cycles, latency, or throughput.",
            "The A423 comparison only checks that observed exact fan-in lies inside its marginal inclusion-exclusion bounds; it does not calibrate or select a service model, placement, scheduler, or hardware parameter.",
            "No result is HBM traffic, energy, area, frequency, hardware acceleration, RTL readiness, or a cross-workload/cross-model claim.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a426_exact_fanin_distribution_report.json"
    manifest = {
        "schema_version": A426_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "report": report,
        "observational_guards": {
            "a424_semantic_and_logical_event_guards_verified": True,
            "a424_event_accounting_matches_independent_summary": True,
            "a423_marginal_bounds_verified": True,
            "exact_fan_in_within_a423_bounds": True,
            "policy_scope_verified": True,
            "no_hardware_parameter_selected": True,
            "no_model_execution": True,
        },
        "boundaries": report["boundaries"],
    }
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.2.6 exact logical fan-in accounting completed: {output}")


if __name__ == "__main__":
    main()
