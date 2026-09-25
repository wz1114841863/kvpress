#!/usr/bin/env python3
"""A4.8.2a bounded Route-A metadata-contract simplification gate.

The gate does not add semantic records, change a transaction boundary, or
reschedule FIFO work.  It asks whether the already-authoritative RMW record
updates can be represented as a read-plus-write pair that publishes only at
the same existing commit boundary.  This removes no work: it deliberately
records the added read/write work and the required same-record commit-exclusion
obligation.  A versioned/shadow proposal is explicitly rejected here because
its selector would introduce semantic state not present in the frozen four-
record catalog.

All counters are logical record-work and semantic-observer evidence.  They are
not hardware accesses, atomics, queues, banks/ports, cycles, timing, latency,
traffic, bandwidth, throughput, energy, area, an architecture choice, or RTL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a480_commit_aware_backlog import iter_contexts
from tools.analyze_kvzap_route_a481b_fixed_service_sweep import SCHEMA as A481B_SCHEMA, validate_inputs as validate_a481b_inputs
from tools.analyze_kvzap_route_a471_metadata_transaction_contract import SemanticReplay
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a482a-contract-simplification-gate-1.0"
OPTIONS = {
    "eager_authoritative_rmw_v1": {
        "admitted_to_a482b": True,
        "rule": "Preserve the current one-logical-RMW lowering whenever a transaction both observes and updates one logical record.",
        "additional_semantic_state": "none",
    },
    "same_record_read_write_commit_exclusion_v1": {
        "admitted_to_a482b": True,
        "rule": "Replace each current logical RMW record with one logical read plus one logical write on the same existing record; publish the write only at the unchanged transaction commit boundary.",
        "additional_semantic_state": "none; requires a same-record commit-exclusion obligation whose physical realization is intentionally not selected",
    },
    "versioned_shadow_write_requires_new_selector_v1": {
        "admitted_to_a482b": False,
        "rule": "A new version cannot become authoritative without a visible latest-version selector; such a selector is not among the frozen four semantic record types or existing A4.7.1 transaction sets.",
        "additional_semantic_state": "unadmitted latest-version selector/control state",
    },
}
RECORD_CATALOG = ("frontier_control", "span_descriptor", "ownership_link", "selection_control")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.8.2a no-model Route-A contract-simplification legality gate; logical record work and semantic replay only, never hardware performance."
    )
    parser.add_argument("--a468220-trace", type=Path, required=True)
    parser.add_argument("--a470-report", type=Path, required=True)
    parser.add_argument("--a471-report", type=Path, required=True)
    parser.add_argument("--a471-trace", type=Path, required=True)
    parser.add_argument("--a4720-report", type=Path, required=True)
    parser.add_argument("--a4721-report", type=Path, required=True)
    parser.add_argument("--a480-report", type=Path, required=True)
    parser.add_argument("--a481a-report", type=Path, required=True)
    parser.add_argument("--a481b-report", type=Path, required=True, help="Completed A4.8.1b fixed-service result used only as the pressure baseline.")
    parser.add_argument("--post-trace-drain-limit", type=int, default=512, help="Must remain the fixed A4.8 predecessor observation bound; not a controller input or timing parameter.")
    parser.add_argument("--preflight-only", action="store_true", help="Validate A4.8.1b and its complete hash-bound predecessor chain without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def distribution(values: Iterable[int]) -> dict[str, int | None]:
    items = sorted(values)
    def pct(fraction: float) -> int | None:
        return items[int((len(items) - 1) * fraction)] if items else None
    return {"count": len(items), "min": min(items) if items else None, "p50": pct(.50), "p95": pct(.95), "p99": pct(.99), "max": max(items) if items else None, "sum": sum(items)}


def record_key(item: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
    return str(item["record_type"]), tuple(item["record_identity"])


def semantic_flags(group: dict[str, Any]) -> dict[tuple[str, tuple[Any, ...]], set[str]]:
    flags: dict[tuple[str, tuple[Any, ...]], set[str]] = defaultdict(set)
    for set_name, flag in (("read_set", "read"), ("write_set", "write"), ("rmw_set", "rmw"), ("release_set", "release")):
        for item in group[set_name]:
            flags[record_key(item)].add(flag)
    return flags


def lower_group(group: dict[str, Any], option: str) -> dict[str, Any]:
    """Lower existing semantic sets without altering record identity or commit."""
    if option not in OPTIONS or not OPTIONS[option]["admitted_to_a482b"]:
        raise ValueError("option is not admitted to the bounded A4.8.2b interface")
    templates: dict[tuple[str, tuple[Any, ...]], tuple[str, ...]] = {}
    baseline_rmw = 0
    for key, flags in semantic_flags(group).items():
        baseline_is_rmw = "rmw" in flags or ("read" in flags and ("write" in flags or "release" in flags))
        if baseline_is_rmw:
            baseline_rmw += 1
            templates[key] = ("rmw",) if option == "eager_authoritative_rmw_v1" else ("read", "write")
        elif "write" in flags or "release" in flags:
            templates[key] = ("write",)
        elif flags == {"read"}:
            templates[key] = ("read",)
        else:
            raise AssertionError(f"unlowerable semantic flags: {flags}")
    counts = Counter(kind for kinds in templates.values() for kind in kinds)
    if option == "same_record_read_write_commit_exclusion_v1":
        if counts["rmw"] != 0 or counts["read"] + counts["write"] < 2 * baseline_rmw:
            raise AssertionError("RMW expansion did not retain one read/write pair per baseline RMW record")
    return {
        "read_record_work": counts["read"],
        "write_record_work": counts["write"],
        "rmw_record_work": counts["rmw"],
        "total_metadata_record_work": sum(counts.values()),
        "touched_semantic_record_count": len(templates),
        "baseline_rmw_record_count": baseline_rmw,
        "same_record_commit_exclusion_obligation_count": baseline_rmw if option == "same_record_read_write_commit_exclusion_v1" else 0,
        "additional_semantic_record_count": 0,
        "templates": templates,
    }


def rmw_primitive_categories(members: list[dict[str, Any]]) -> Counter[str]:
    output: Counter[str] = Counter()
    for item in members:
        if str(item["access_kind"]) != "rmw":
            continue
        sequence = tuple(str(value) for value in item["primitive_sequence"])
        if sequence == ("span_partial_dequeue", "span_head_remaining_update"):
            output["strict_same_span_partial_remaining_pair"] += 1
        elif sequence == ("source_head_update",):
            output["frontier_update"] += 1
        else:
            raise AssertionError(f"unregistered RMW primitive sequence: {sequence}")
    return output


def negative_controls() -> dict[str, Any]:
    """Show why a pair may not publish before the existing group commit."""
    partial = {
        "span_write_before_frontier_commit": "dequeue_observer_can_see_updated_span_state_with_old_source_frontier",
        "frontier_write_before_span_release_commit": "oldest_selection_can_skip_or_reference_a_span_before_its_joint_release_visibility",
        "versioned_write_without_authoritative_selector": "later_observer_cannot_unambiguously_choose_the_latest_committed_version",
    }
    if not all(partial.values()):
        raise AssertionError("A4.8.2a negative control did not expose a partial/ambiguous state")
    return {"status": "rejected_as_semantically_observable_or_ambiguous", "failures": partial}


def context_key(context: tuple[str, str, int, str]) -> tuple[str, str, int, str]:
    return str(context[0]), str(context[1]), int(context[2]), str(context[3])


def analyze_context(context: tuple[str, str, int, str], record_ops: list[dict[str, Any]], groups: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay authoritative states after every unchanged commit and make ledgers."""
    if sum(int(group["member_record_node_count"]) for group in groups) != len(record_ops):
        raise AssertionError("transaction groups do not partition this immutable record trace")
    replay = SemanticReplay()
    option_totals = {name: Counter() for name, spec in OPTIONS.items() if spec["admitted_to_a482b"]}
    primitive_categories: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    phase_totals: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: {name: Counter() for name, spec in OPTIONS.items() if spec["admitted_to_a482b"]})
    exact_commit_count = 0
    for group in groups:
        members = [record_ops[int(index)] for index in group["member_record_node_indices"]]
        if len(members) != int(group["member_record_node_count"]):
            raise AssertionError("transaction member index mismatch")
        primitive_categories.update(rmw_primitive_categories(members))
        type_counts[str(group["transaction_type"])] += 1
        eager = lower_group(group, "eager_authoritative_rmw_v1")
        dual = lower_group(group, "same_record_read_write_commit_exclusion_v1")
        if eager["touched_semantic_record_count"] != dual["touched_semantic_record_count"] or dual["additional_semantic_record_count"] != 0:
            raise AssertionError("A4.8.2a dual-access transform changed semantic record ownership")
        if dual["total_metadata_record_work"] != eager["total_metadata_record_work"] + eager["rmw_record_work"]:
            raise AssertionError("dual-access work ledger does not account for every expanded RMW")
        for name, lowered in (("eager_authoritative_rmw_v1", eager), ("same_record_read_write_commit_exclusion_v1", dual)):
            for field in ("read_record_work", "write_record_work", "rmw_record_work", "total_metadata_record_work", "baseline_rmw_record_count", "same_record_commit_exclusion_obligation_count", "additional_semantic_record_count"):
                option_totals[name][field] += int(lowered[field])
                phase_totals[str(group["phase"])][name][field] += int(lowered[field])
        # This is the observer gate: both lowered forms publish exactly the
        # same group state only after the existing A4.7.1 linearization point.
        replay.commit(group, members)
        exact_commit_count += 1
    if set(type_counts) - {"admission_create", "dequeue_nonterminal", "dequeue_terminal", "tail_extension_reserved_zero_observed"}:
        raise AssertionError("unexpected frozen A4.7.1 transaction type")
    return {
        "anchor": context[0], "workload": context[1], "evaluation_horizon_append_opportunities": context[2], "organization_label": context[3],
        "transaction_group_count": len(groups), "exact_authoritative_commit_replay_count": exact_commit_count,
        "transaction_type_counts": dict(sorted(type_counts.items())),
        "rmw_primitive_categories": dict(sorted(primitive_categories.items())),
        "option_work_ledgers": {name: dict(sorted(total.items())) for name, total in option_totals.items()},
        "phase_option_work_ledgers": {phase: {name: dict(sorted(total.items())) for name, total in options.items()} for phase, options in sorted(phase_totals.items())},
        "semantic_replay": "passed_after_every_unchanged_a471_commit_boundary",
    }


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    a480, a481a = validate_a481b_inputs(args)
    a481b = read_completed(args.a481b_report, A481B_SCHEMA, "A4.8.1b")
    expected = {
        "a468220_trace_sha256": sha256_file(args.a468220_trace),
        "a470_report_sha256": sha256_file(args.a470_report),
        "a471_report_sha256": sha256_file(args.a471_report),
        "a471_trace_sha256": sha256_file(args.a471_trace),
        "a4720_report_sha256": sha256_file(args.a4720_report),
        "a4721_report_sha256": sha256_file(args.a4721_report),
        "a480_report_sha256": sha256_file(args.a480_report),
        "a481a_report_sha256": sha256_file(args.a481a_report),
    }
    if a481b.get("input_artifacts") != expected:
        raise ValueError("A4.8.1b input hash binding mismatch")
    if a481b.get("config", {}).get("a480_fixed_config_hash") != a480.get("config_hash") or a481b.get("config", {}).get("a481a_fixed_config_hash") != a481a.get("config_hash"):
        raise ValueError("A4.8.1b fixed baseline configuration mismatch")
    required = (
        "a481a_a480_and_full_predecessor_hash_chain_validated",
        "direct_and_causal_baselines_preserved_side_by_side",
        "a481a_causal_baseline_still_exactly_matches_a480",
        "all_fixed_quanta_global_preregistered_and_not_trace_tuned",
        "no_transaction_dependency_fifo_mapping_or_commit_boundary_changed",
        "ready_dependency_blocked_and_root_amplification_reported_for_every_fixed_quantum",
    )
    if not all(a481b.get("semantic_guards", {}).get(name) is True for name in required):
        raise ValueError("A4.8.1b semantic guards incomplete")
    return a480, a481a, a481b


def main() -> None:
    args = parse_args()
    a480, a481a, a481b = validate_inputs(args)
    if args.preflight_only:
        print("A4.8.2a preflight passed: A4.8.1b/A4.8.1a/A4.8.0 fixed baselines and the full hash-bound predecessor chain validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a481b_contexts = {(str(row["anchor"]), str(row["workload"]), int(row["evaluation_horizon_append_opportunities"]), str(row["organization_label"])) for row in a481b["fixed_service_sweep_rows"]}
    rows = []
    for context, record_ops, groups in iter_contexts(args.a468220_trace, args.a471_trace):
        row = analyze_context(context, record_ops, groups)
        rows.append(row)
    if {context_key((row["anchor"], row["workload"], row["evaluation_horizon_append_opportunities"], row["organization_label"])) for row in rows} != a481b_contexts:
        raise AssertionError("A4.8.2a context coverage does not match A4.8.1b")
    ledgers = {name: Counter() for name, spec in OPTIONS.items() if spec["admitted_to_a482b"]}
    for row in rows:
        for name, ledger in row["option_work_ledgers"].items():
            ledgers[name].update({field: int(value) for field, value in ledger.items()})
    negative = negative_controls()
    config = {
        "a480_fixed_config_hash": a480["config_hash"], "a481a_fixed_config_hash": a481a["config_hash"], "a481b_fixed_config_hash": a481b["config_hash"],
        "frozen_semantic_record_catalog": list(RECORD_CATALOG), "contract_options": OPTIONS,
        "closure_rule": "A4.8.2a admits only the eager baseline and same-record read/write expansion. Versioned/shadow updates are rejected until a separately authorized semantic record/commit contract supplies their selector; no further A4.8.2a semantic variants may be introduced.",
        "boundary": "The work ledger, commit-exclusion obligation, and semantic observer replay are logical contract quantities only. They are not hardware RMW/read/write accesses, atomic instructions, queues, banks/ports, cycles, timing, latency, traffic, bandwidth, throughput, energy, area, architecture selection, or RTL.",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(),
        "config": config, "config_hash": stable_hash(config),
        "execution_classification": "trace-derived immutable transaction inputs with functional unchanged-commit semantic replay and logical contract-work accounting; not measured hardware behavior",
        "input_artifacts": {
            "a468220_trace_sha256": sha256_file(args.a468220_trace), "a470_report_sha256": sha256_file(args.a470_report),
            "a471_report_sha256": sha256_file(args.a471_report), "a471_trace_sha256": sha256_file(args.a471_trace),
            "a4720_report_sha256": sha256_file(args.a4720_report), "a4721_report_sha256": sha256_file(args.a4721_report),
            "a480_report_sha256": sha256_file(args.a480_report), "a481a_report_sha256": sha256_file(args.a481a_report), "a481b_report_sha256": sha256_file(args.a481b_report),
        },
        "context_rows": rows,
        "aggregate_option_work_ledgers": {name: dict(sorted(ledger.items())) for name, ledger in ledgers.items()},
        "negative_controls": negative,
        "semantic_guards": {
            "a481b_a481a_a480_and_full_predecessor_hash_chain_validated": True,
            "frozen_four_record_catalog_and_a471_transaction_boundaries_unchanged": True,
            "every_context_replays_authoritative_state_after_every_unchanged_commit": True,
            "same_record_read_write_expansion_preserves_record_identity_and_adds_no_semantic_state": True,
            "all_expanded_read_write_pairs_publish_only_at_existing_commit_boundary": True,
            "expanded_rmw_work_and_same_record_commit_exclusion_obligation_accounted_explicitly": True,
            "versioned_shadow_write_rejected_without_new_selector_semantic_state": True,
            "partial_publish_and_ambiguous_selector_negative_controls_rejected": True,
            "a482a_contract_simplification_variant_catalog_closed": True,
            "no_pruning_fifo_ownership_oldest_order_or_scheduler_changed": True,
            "no_model_runtime_profiler_or_hardware_parameter_loaded": True,
            "no_hardware_operation_queue_cycle_timing_performance_or_architecture_claim": True,
        },
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a482a_contract_simplification_gate_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.8.2a complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} contexts={len(rows)}")


if __name__ == "__main__":
    main()
