#!/usr/bin/env python3
"""A4.8.1a no-model causal readiness and root-cause propagation audit.

This is an instrumentation-only replay of the fixed A4.8.0 causal controller.
It does not alter one transaction, dependency, FIFO relation, commit boundary,
mapping, service level, or grant decision.  It separates dependency-ready work
from dependency-blocked work and follows a deterministic shortage-root lineage
through downstream dependency blockers.

All service and delay coordinates remain logical/model quantities, never
hardware accesses, ports, cycles, bandwidth, timing, latency, throughput,
energy, area, capacity, architecture, or RTL evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a480_commit_aware_backlog import (
    BLOCKING_CAUSES,
    CANDIDATE_PROFILES,
    CONTROLLER_THRESHOLDS,
    DEFAULT_POST_TRACE_DRAIN_LIMIT,
    PHASES,
    POST_TRACE_DRAIN_PHASE,
    SCHEMA as A480_SCHEMA,
    SERVICE_LEVELS,
    CausalController,
    ScheduledTransaction,
    backlog_observables,
    blocking_cause,
    dependency_predecessors,
    distribution,
    iter_contexts,
    longest_run,
    make_scheduled_transactions,
    service_backlog,
    validate_inputs as validate_a480_inputs,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a481a-readiness-root-cause-1.0"
ROOT_CAUSES = BLOCKING_CAUSES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.8.1a no-model root-cause propagation audit over the fixed A4.8.0 causal replay; logical service/readiness only, never hardware timing or performance."
    )
    parser.add_argument("--a468220-trace", type=Path, required=True)
    parser.add_argument("--a470-report", type=Path, required=True)
    parser.add_argument("--a471-report", type=Path, required=True)
    parser.add_argument("--a471-trace", type=Path, required=True)
    parser.add_argument("--a4720-report", type=Path, required=True)
    parser.add_argument("--a4721-report", type=Path, required=True)
    parser.add_argument("--a480-report", type=Path, required=True, help="Completed fixed-controller A4.8.0 baseline to reproduce exactly.")
    parser.add_argument("--preflight-only", action="store_true", help="Validate A4.8.0 and all hash-bound predecessors without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def compact_replay(replay: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in replay.items() if key != "opportunity_rows"}


def validate_inputs(args: argparse.Namespace) -> dict[str, Any]:
    # Reuse the A4.8.0 hash/guard validation verbatim before binding its output.
    validate_a480_inputs(args)
    a480 = read_completed(args.a480_report, A480_SCHEMA, "A4.8.0")
    expected_inputs = {
        "a468220_trace_sha256": sha256_file(args.a468220_trace),
        "a470_report_sha256": sha256_file(args.a470_report),
        "a471_report_sha256": sha256_file(args.a471_report),
        "a471_trace_sha256": sha256_file(args.a471_trace),
        "a4720_report_sha256": sha256_file(args.a4720_report),
        "a4721_report_sha256": sha256_file(args.a4721_report),
    }
    if a480.get("input_artifacts") != expected_inputs:
        raise ValueError("A4.8.0 input hash binding mismatch")
    expected_levels = [{"name": name, "abstract_quantum_per_bank_per_operation_per_logical_opportunity": quantum} for name, quantum in SERVICE_LEVELS]
    config = a480.get("config", {})
    if config.get("candidate_profiles") != list(CANDIDATE_PROFILES) or config.get("service_levels") != expected_levels or config.get("causal_counter_thresholds") != CONTROLLER_THRESHOLDS or config.get("post_trace_drain_limit") != DEFAULT_POST_TRACE_DRAIN_LIMIT:
        raise ValueError("A4.8.0 configuration is not the fixed A4.8.1a controller baseline")
    required = (
        "a470_a471_a4720_a4721_hash_bound_contract_chain_validated",
        "a471_transaction_sets_order_fifo_and_commit_boundaries_unchanged",
        "direct_service_baseline_preserved_and_drains_all_transactions",
        "causal_controller_uses_only_current_backlog_age_and_history",
        "controller_receives_no_future_arrivals_horizon_anchor_or_workload_identity",
        "all_transaction_commits_obey_intrinsic_predecessors_and_atomic_commit_boundary",
        "backlog_causes_intrinsic_same_bank_rmw_and_cross_bank_atomic_reported_separately",
    )
    if not all(a480.get("semantic_guards", {}).get(name) is True for name in required):
        raise ValueError("A4.8.0 semantic guards incomplete")
    return a480


@dataclass
class RootIncident:
    root_id: int
    cause: str
    origin_transaction: int
    origin_opportunity: int
    affected_transactions: set[int] = field(default_factory=set)
    downstream_transactions: set[int] = field(default_factory=set)
    observation_count: int = 0
    max_dependency_depth: int = 0


def ready_indices(backlog: Iterable[int], transactions: list[ScheduledTransaction], committed: set[int]) -> list[int]:
    return [index for index in backlog if all(parent in committed for parent in transactions[index].predecessors)]


def head_max(indices: Iterable[int], transactions: list[ScheduledTransaction]) -> int:
    counts: Counter[tuple[int, int]] = Counter((transactions[index].layer, transactions[index].head) for index in indices)
    return max(counts.values(), default=0)


def root_summary(records: dict[int, RootIncident]) -> dict[str, Any]:
    by_cause: dict[str, list[RootIncident]] = defaultdict(list)
    for item in records.values():
        by_cause[item.cause].append(item)
    output = {}
    for cause in ROOT_CAUSES:
        items = by_cause[cause]
        output[cause] = {
            "root_incident_count": len(items),
            "affected_transaction_count": sum(len(item.affected_transactions) for item in items),
            "unique_downstream_transaction_count": sum(len(item.downstream_transactions) for item in items),
            "downstream_transactions_per_root": distribution(len(item.downstream_transactions) for item in items),
            "root_lineage_observations_per_root": distribution(item.observation_count for item in items),
            "maximum_dependency_depth_per_root": distribution(item.max_dependency_depth for item in items),
            "amplification_definition": "unique downstream transaction groups carrying this root lineage, excluding the shortage-origin transaction itself; this is a canonical logical lineage count, not a hardware queue, latency, or causal graph cardinality",
        }
    return output


def audit_causal_replay(
    *, transactions: list[ScheduledTransaction], opportunities: list[tuple[str, int]], profile: dict[str, Any], post_trace_drain_limit: int,
) -> dict[str, Any]:
    """Replay the exact A4.8.0 policy with readiness/root instrumentation only."""
    arrivals: dict[int, list[int]] = defaultdict(list)
    for transaction in transactions:
        arrivals[transaction.arrival_ordinal].append(transaction.index)
    backlog: list[int] = []
    committed: set[int] = set(); commit_ordinal: dict[int, int] = {}
    controller = CausalController()
    lineage: dict[int, tuple[int, int]] = {}
    roots: dict[int, RootIncident] = {}
    next_root_id = 0
    opportunity_rows: list[dict[str, Any]] = []
    max_ordinal = len(opportunities) - 1
    ordinal = 0
    while ordinal <= max_ordinal or (backlog and ordinal <= max_ordinal + post_trace_drain_limit):
        trace_opportunity = ordinal <= max_ordinal
        phase, checkpoint = opportunities[ordinal] if trace_opportunity else (POST_TRACE_DRAIN_PHASE, ordinal - max_ordinal)
        new = list(arrivals.get(ordinal, [])) if trace_opportunity else []
        backlog.extend(new)
        pre_ready = ready_indices(backlog, transactions, committed)
        pre_ready_set = set(pre_ready)
        layer_backlog, head_backlog, age_max = backlog_observables(backlog, transactions, ordinal)
        level, quantum, transition = controller.choose(layer_backlog=layer_backlog, head_backlog=head_backlog, age_max=age_max)
        remaining = Counter({(bank, operation): quantum for bank in range(int(profile["bank_count"])) for operation in ("read", "write", "rmw")})
        committed_this_op: list[int] = []
        remaining_backlog: list[int] = []
        for index in backlog:
            transaction = transactions[index]
            if blocking_cause(transaction, committed, remaining) is not None:
                remaining_backlog.append(index)
                continue
            remaining.subtract(transaction.demands)
            committed.add(index); commit_ordinal[index] = ordinal; committed_this_op.append(index)
            lineage.pop(index, None)
        backlog = remaining_backlog
        immediate_causes: Counter[str] = Counter()
        for index in backlog:
            transaction = transactions[index]
            cause = blocking_cause(transaction, committed, remaining)
            if cause is None:
                raise AssertionError("uncommitted transaction must have an immediate blocker")
            immediate_causes[cause] += 1
            root_id: int
            depth: int
            if cause == "intrinsic_transaction_dependency":
                candidates = [(lineage[parent][0], lineage[parent][1], parent) for parent in sorted(transaction.predecessors) if parent not in committed and parent in lineage]
                if candidates:
                    root_id, parent_depth, _ = min(candidates, key=lambda item: (roots[item[0]].origin_opportunity, roots[item[0]].origin_transaction, item[2]))
                    depth = parent_depth + 1
                else:
                    root_id, depth = next_root_id, 0; next_root_id += 1
                    roots[root_id] = RootIncident(root_id=root_id, cause=cause, origin_transaction=index, origin_opportunity=ordinal)
            else:
                existing = lineage.get(index)
                if existing is not None and roots[existing[0]].origin_transaction == index:
                    root_id, depth = existing
                else:
                    root_id, depth = next_root_id, 0; next_root_id += 1
                    roots[root_id] = RootIncident(root_id=root_id, cause=cause, origin_transaction=index, origin_opportunity=ordinal)
            lineage[index] = (root_id, depth)
            root = roots[root_id]
            root.affected_transactions.add(index)
            if index != root.origin_transaction:
                root.downstream_transactions.add(index)
            root.observation_count += 1
            root.max_dependency_depth = max(root.max_dependency_depth, depth)
        post_ready = ready_indices(backlog, transactions, committed)
        post_ready_set = set(post_ready)
        _, _, post_service_age_max = backlog_observables(backlog, transactions, ordinal)
        post_ready_ages = [ordinal - transactions[index].arrival_ordinal for index in post_ready]
        opportunity_rows.append({
            "phase": phase, "logical_opportunity_ordinal": ordinal, "trace_derived_arrival": trace_opportunity,
            "new_transaction_groups": len(new), "level": level,
            "pre_service_backlog": len(backlog) + len(committed_this_op), "post_service_backlog": len(backlog),
            "pre_service_ready_backlog": len(pre_ready), "pre_service_dependency_blocked_backlog": len(backlog) + len(committed_this_op) - len(pre_ready),
            "post_service_ready_backlog": len(post_ready), "post_service_dependency_blocked_backlog": len(backlog) - len(post_ready),
            "pre_service_ready_max_per_head": head_max(pre_ready_set, transactions), "post_service_ready_max_per_head": head_max(post_ready_set, transactions),
            "post_service_age_max": post_service_age_max,
            "post_service_ready_age_max": max(post_ready_ages, default=0), "committed_transaction_groups": len(committed_this_op),
            "post_service_backlog_by_immediate_cause": {cause: immediate_causes[cause] for cause in ROOT_CAUSES},
        })
        ordinal += 1
        if not trace_opportunity and not backlog:
            break
    for index, transaction in enumerate(transactions):
        if index in committed and any(parent not in committed or commit_ordinal[parent] > commit_ordinal[index] for parent in transaction.predecessors):
            raise AssertionError("A4.8.1a committed before an immutable predecessor")
    completion = "drained" if not backlog else "prefix_censored_backlog_remains"
    immediate = Counter(); level_counts = Counter()
    for row in opportunity_rows:
        immediate.update(row["post_service_backlog_by_immediate_cause"]); level_counts[row["level"]] += 1
    delays = [commit_ordinal[index] - transaction.arrival_ordinal for index, transaction in enumerate(transactions) if index in commit_ordinal]
    phase_rows = {}
    for phase in (*PHASES, POST_TRACE_DRAIN_PHASE):
        items = [row for row in opportunity_rows if row["phase"] == phase]
        if not items:
            continue
        phase_rows[phase] = {
            "logical_opportunity_count": len(items),
            "pre_service_ready_backlog": distribution(row["pre_service_ready_backlog"] for row in items),
            "post_service_ready_backlog": distribution(row["post_service_ready_backlog"] for row in items),
            "post_service_dependency_blocked_backlog": distribution(row["post_service_dependency_blocked_backlog"] for row in items),
            "post_service_ready_age_max": distribution(row["post_service_ready_age_max"] for row in items),
            "sustained_post_service_ready_positive_logical_opportunity_run": longest_run(row["post_service_ready_backlog"] > 0 for row in items),
        }
    trace_rows = [row for row in opportunity_rows if row["trace_derived_arrival"]]
    trace_end = trace_rows[-1] if trace_rows else None
    return {
        "completion_state": completion, "committed_transaction_group_count": len(committed),
        "post_trace_drain_opportunities_used": max(0, len(opportunity_rows) - len(opportunities)),
        "logical_opportunity_count": len(opportunity_rows),
        "pre_service_backlog": distribution(row["pre_service_backlog"] for row in opportunity_rows),
        "post_service_backlog": distribution(row["post_service_backlog"] for row in opportunity_rows),
        "post_service_age_max": distribution(row["post_service_age_max"] for row in opportunity_rows),
        "logical_opportunity_epoch_delay": distribution(delays),
        "backlog_group_observations_by_blocking_cause": {cause: immediate[cause] for cause in ROOT_CAUSES},
        "level_opportunity_counts": {name: level_counts[name] for name, _ in SERVICE_LEVELS} | {"direct_unconstrained": 0},
        "high_level_occupancy_fraction": level_counts["high"] / len(opportunity_rows) if opportunity_rows else 0.0,
        "longest_consecutive_high_logical_opportunity_run": longest_run(row["level"] == "high" for row in opportunity_rows),
        "escalation_count": controller.escalations, "deescalation_count": controller.deescalations,
        "residual_backlog_at_high_service": distribution(row["post_service_backlog"] for row in opportunity_rows if row["level"] == "high"),
        "readiness": {
            "pre_service_ready_backlog": distribution(row["pre_service_ready_backlog"] for row in opportunity_rows),
            "post_service_ready_backlog": distribution(row["post_service_ready_backlog"] for row in opportunity_rows),
            "post_service_dependency_blocked_backlog": distribution(row["post_service_dependency_blocked_backlog"] for row in opportunity_rows),
            "post_service_ready_age_max": distribution(row["post_service_ready_age_max"] for row in opportunity_rows),
            "pre_service_ready_max_per_head": distribution(row["pre_service_ready_max_per_head"] for row in opportunity_rows),
            "post_service_ready_max_per_head": distribution(row["post_service_ready_max_per_head"] for row in opportunity_rows),
            "sustained_post_service_ready_positive_logical_opportunity_run": longest_run(row["post_service_ready_backlog"] > 0 for row in opportunity_rows),
            "trace_end_residual_backlog": {
                "total": trace_end["post_service_backlog"] if trace_end else 0,
                "ready": trace_end["post_service_ready_backlog"] if trace_end else 0,
                "dependency_blocked": trace_end["post_service_dependency_blocked_backlog"] if trace_end else 0,
            },
            "additional_post_trace_drain_logical_opportunities": max(0, len(opportunity_rows) - len(opportunities)),
            "phase_rows": phase_rows,
        },
        "root_cause_amplification": root_summary(roots),
    }


def baseline_equivalent(audit: dict[str, Any], reference: dict[str, Any]) -> bool:
    fields = (
        "completion_state", "committed_transaction_group_count", "post_trace_drain_opportunities_used",
        "logical_opportunity_count", "pre_service_backlog", "post_service_backlog", "post_service_age_max",
        "logical_opportunity_epoch_delay", "backlog_group_observations_by_blocking_cause",
        "level_opportunity_counts", "high_level_occupancy_fraction",
        "longest_consecutive_high_logical_opportunity_run", "escalation_count", "deescalation_count",
        "residual_backlog_at_high_service",
    )
    return all(audit[field] == reference[field] for field in fields)


def row_key(row: dict[str, Any]) -> tuple[str, str, int, str, str]:
    return (str(row["anchor"]), str(row["workload"]), int(row["evaluation_horizon_append_opportunities"]), str(row["organization_label"]), str(row["profile"]))


def main() -> None:
    args = parse_args()
    a480 = validate_inputs(args)
    if args.preflight_only:
        print("A4.8.1a preflight passed: A4.8.0 fixed-controller baseline and full hash-bound predecessor chain validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a480_rows = {row_key(row): row for row in a480["replay_rows"]}
    if len(a480_rows) != len(a480["replay_rows"]):
        raise AssertionError("duplicate A4.8.0 context/profile row")
    rows = []
    for context, record_ops, groups in iter_contexts(args.a468220_trace, args.a471_trace):
        predecessors, dependency_sources = dependency_predecessors(record_ops, groups)
        for profile in CANDIDATE_PROFILES:
            transactions, opportunities = make_scheduled_transactions(groups, predecessors, profile)
            key = (*context, str(profile["profile"]))
            if key not in a480_rows:
                raise AssertionError("A4.8.0 baseline missing context/profile")
            baseline = a480_rows[key]
            reference = service_backlog(transactions=transactions, opportunities=opportunities, policy="causal_elastic_v1", post_trace_drain_limit=DEFAULT_POST_TRACE_DRAIN_LIMIT)
            if compact_replay(reference) != baseline["causal_elastic_replay"]:
                raise AssertionError("current replay does not reproduce hash-bound A4.8.0 causal baseline")
            audit = audit_causal_replay(transactions=transactions, opportunities=opportunities, profile=profile, post_trace_drain_limit=DEFAULT_POST_TRACE_DRAIN_LIMIT)
            if not baseline_equivalent(audit, reference):
                raise AssertionError("A4.8.1a readiness instrumentation changed A4.8.0 replay outcome")
            rows.append({
                "anchor": context[0], "workload": context[1], "evaluation_horizon_append_opportunities": context[2], "organization_label": context[3],
                **profile, "transaction_group_count": len(transactions), "intrinsic_dependency_edge_sources": dependency_sources,
                "a480_causal_replay_reproduced_exactly": True, "readiness_root_cause_audit": audit,
            })
    if set(a480_rows) != {row_key(row) for row in rows}:
        raise AssertionError("A4.8.1a coverage does not equal A4.8.0 baseline")
    config = {
        "a480_fixed_config_hash": a480["config_hash"], "candidate_profiles": CANDIDATE_PROFILES,
        "root_lineage_rule": "when immediate blocker is a shortage, retain its origin while that origin remains uncommitted; when immediate blocker is dependency, inherit the oldest unresolved predecessor lineage, breaking ties by root origin transaction; a missing predecessor lineage is an intrinsic root. This is a canonical attribution, not a complete causal graph.",
        "readiness_definition": "dependency-ready means every fixed A4.7.0/A4.7.1 predecessor transaction has committed; it says nothing about abstract service availability.",
        "boundary": "Ready/dependency backlog, shortage-root amplification, logical opportunity epoch, abstract service quantum, and drain observations are not hardware queues, banks/ports, access transactions, cycles, timing, latency, bandwidth, throughput, energy, area, architecture selection, or RTL.",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(),
        "config": config, "config_hash": stable_hash(config),
        "execution_classification": "trace-derived immutable transaction inputs with functional fixed-controller readiness/root-lineage instrumentation; not measured hardware behavior",
        "input_artifacts": {
            "a468220_trace_sha256": sha256_file(args.a468220_trace), "a470_report_sha256": sha256_file(args.a470_report),
            "a471_report_sha256": sha256_file(args.a471_report), "a471_trace_sha256": sha256_file(args.a471_trace),
            "a4720_report_sha256": sha256_file(args.a4720_report), "a4721_report_sha256": sha256_file(args.a4721_report),
            "a480_report_sha256": sha256_file(args.a480_report),
        },
        "readiness_root_cause_rows": rows,
        "semantic_guards": {
            "a480_fixed_controller_and_predecessor_hash_chain_validated": True,
            "a480_causal_replay_reproduced_before_instrumentation": True,
            "no_transaction_dependency_fifo_commit_mapping_or_service_decision_changed": True,
            "ready_and_dependency_blocked_sets_reported_per_phase": True,
            "root_cause_amplification_uses_declared_canonical_lineage_not_inferred_hardware_causality": True,
            "root_and_immediate_blocking_causes_kept_distinct": True,
            "no_future_horizon_anchor_or_workload_identity_enters_controller": True,
            "no_fixed_service_sweep_or_new_scheduler_policy_introduced": True,
            "no_model_runtime_profiler_or_hardware_parameter_loaded": True,
            "no_hardware_queue_access_cycle_timing_performance_or_architecture_claim": True,
        },
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a481a_readiness_root_cause_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.8.1a complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} rows={len(rows)}")


if __name__ == "__main__":
    main()
