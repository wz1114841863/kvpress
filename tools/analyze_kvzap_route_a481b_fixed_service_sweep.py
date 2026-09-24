#!/usr/bin/env python3
"""A4.8.1b no-model fixed abstract-service readiness/root-cause sweep.

This holds every immutable A4.7.0/A4.7.1 transaction, predecessor, FIFO
order, A4.7.1 commit boundary, A4.7.2.1 mapping sensitivity, and A4.8.0
opportunity stream fixed.  It keeps the recorded A4.8.0 direct and causal
baselines beside five globally predeclared fixed abstract-service quanta.

All service and delay coordinates are logical/model quantities.  They are not
hardware queues, banks/ports, transactions, cycles, timing, latency, traffic,
bandwidth, throughput, energy, area, an architecture choice, or RTL evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a480_commit_aware_backlog import (
    BLOCKING_CAUSES,
    CANDIDATE_PROFILES,
    DEFAULT_POST_TRACE_DRAIN_LIMIT,
    PHASES,
    POST_TRACE_DRAIN_PHASE,
    ScheduledTransaction,
    backlog_observables,
    blocking_cause,
    dependency_predecessors,
    distribution,
    iter_contexts,
    longest_run,
    make_scheduled_transactions,
)
from tools.analyze_kvzap_route_a481a_readiness_root_cause import (
    SCHEMA as A481A_SCHEMA,
    RootIncident,
    baseline_equivalent,
    head_max,
    ready_indices,
    root_summary,
    row_key,
    validate_inputs as validate_a481a_inputs,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a481b-fixed-service-sweep-1.0"
FIXED_QUANTA = (1, 2, 4, 8, 16)
ROOT_CAUSES = BLOCKING_CAUSES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.8.1b no-model fixed abstract-service sweep beside the fixed A4.8.0 controller baseline; logical replay only, never hardware timing or performance."
    )
    parser.add_argument("--a468220-trace", type=Path, required=True)
    parser.add_argument("--a470-report", type=Path, required=True)
    parser.add_argument("--a471-report", type=Path, required=True)
    parser.add_argument("--a471-trace", type=Path, required=True)
    parser.add_argument("--a4720-report", type=Path, required=True)
    parser.add_argument("--a4721-report", type=Path, required=True)
    parser.add_argument("--a480-report", type=Path, required=True)
    parser.add_argument("--a481a-report", type=Path, required=True, help="Completed readiness/root-cause baseline that must be reproduced, not retuned.")
    parser.add_argument("--post-trace-drain-limit", type=int, default=DEFAULT_POST_TRACE_DRAIN_LIMIT, help="Must equal the fixed A4.8.0 observation bound (512); not a controller input or timing parameter.")
    parser.add_argument("--preflight-only", action="store_true", help="Validate the complete A4.8.1a/A4.8.0 hash-bound chain without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind A4.8.1a and A4.8.0 before adding the fixed sweep."""
    a480 = validate_a481a_inputs(args)
    a481a = read_completed(args.a481a_report, A481A_SCHEMA, "A4.8.1a")
    expected = {
        "a468220_trace_sha256": sha256_file(args.a468220_trace),
        "a470_report_sha256": sha256_file(args.a470_report),
        "a471_report_sha256": sha256_file(args.a471_report),
        "a471_trace_sha256": sha256_file(args.a471_trace),
        "a4720_report_sha256": sha256_file(args.a4720_report),
        "a4721_report_sha256": sha256_file(args.a4721_report),
        "a480_report_sha256": sha256_file(args.a480_report),
    }
    if a481a.get("input_artifacts") != expected:
        raise ValueError("A4.8.1a input hash binding mismatch")
    if a481a.get("config", {}).get("a480_fixed_config_hash") != a480.get("config_hash"):
        raise ValueError("A4.8.1a does not bind the supplied fixed A4.8.0 configuration")
    required = (
        "a480_fixed_controller_and_predecessor_hash_chain_validated",
        "a480_causal_replay_reproduced_before_instrumentation",
        "no_transaction_dependency_fifo_commit_mapping_or_service_decision_changed",
        "ready_and_dependency_blocked_sets_reported_per_phase",
        "root_cause_amplification_uses_declared_canonical_lineage_not_inferred_hardware_causality",
        "root_and_immediate_blocking_causes_kept_distinct",
    )
    if not all(a481a.get("semantic_guards", {}).get(name) is True for name in required):
        raise ValueError("A4.8.1a semantic guards incomplete")
    if args.post_trace_drain_limit != DEFAULT_POST_TRACE_DRAIN_LIMIT:
        raise ValueError("A4.8.1b fixes the A4.8.0 no-arrival observation bound at 512")
    return a480, a481a


def audit_fixed_service_replay(
    *, transactions: list[ScheduledTransaction], opportunities: list[tuple[str, int]], profile: dict[str, Any], quantum: int,
    post_trace_drain_limit: int,
) -> dict[str, Any]:
    """Stable-order fixed-quantum replay with A4.8.1a observer semantics."""
    if quantum not in FIXED_QUANTA:
        raise ValueError("fixed quantum is not preregistered")
    arrivals: dict[int, list[int]] = defaultdict(list)
    for transaction in transactions:
        arrivals[transaction.arrival_ordinal].append(transaction.index)
    backlog: list[int] = []
    committed: set[int] = set()
    commit_ordinal: dict[int, int] = {}
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
        remaining = Counter({(bank, operation): quantum for bank in range(int(profile["bank_count"])) for operation in ("read", "write", "rmw")})
        committed_this_op: list[int] = []
        remaining_backlog: list[int] = []
        for index in backlog:
            transaction = transactions[index]
            if blocking_cause(transaction, committed, remaining) is not None:
                remaining_backlog.append(index)
                continue
            remaining.subtract(transaction.demands)
            committed.add(index)
            commit_ordinal[index] = ordinal
            committed_this_op.append(index)
            lineage.pop(index, None)
        backlog = remaining_backlog
        immediate_causes: Counter[str] = Counter()
        for index in backlog:
            transaction = transactions[index]
            cause = blocking_cause(transaction, committed, remaining)
            if cause is None:
                raise AssertionError("uncommitted transaction must have an immediate blocker")
            immediate_causes[cause] += 1
            if cause == "intrinsic_transaction_dependency":
                candidates = [(lineage[parent][0], lineage[parent][1], parent) for parent in sorted(transaction.predecessors) if parent not in committed and parent in lineage]
                if candidates:
                    root_id, parent_depth, _ = min(candidates, key=lambda item: (roots[item[0]].origin_opportunity, roots[item[0]].origin_transaction, item[2]))
                    depth = parent_depth + 1
                else:
                    root_id, depth = next_root_id, 0
                    next_root_id += 1
                    roots[root_id] = RootIncident(root_id=root_id, cause=cause, origin_transaction=index, origin_opportunity=ordinal)
            else:
                existing = lineage.get(index)
                if existing is not None and roots[existing[0]].origin_transaction == index:
                    root_id, depth = existing
                else:
                    root_id, depth = next_root_id, 0
                    next_root_id += 1
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
            "phase": phase,
            "logical_opportunity_ordinal": ordinal,
            "trace_derived_arrival": trace_opportunity,
            "new_transaction_groups": len(new),
            "pre_service_backlog": len(backlog) + len(committed_this_op),
            "post_service_backlog": len(backlog),
            "pre_service_ready_backlog": len(pre_ready),
            "pre_service_dependency_blocked_backlog": len(backlog) + len(committed_this_op) - len(pre_ready),
            "post_service_ready_backlog": len(post_ready),
            "post_service_dependency_blocked_backlog": len(backlog) - len(post_ready),
            "pre_service_ready_max_per_head": head_max(pre_ready_set, transactions),
            "post_service_ready_max_per_head": head_max(post_ready_set, transactions),
            "post_service_age_max": post_service_age_max,
            "post_service_ready_age_max": max(post_ready_ages, default=0),
            "committed_transaction_groups": len(committed_this_op),
            "post_service_backlog_by_immediate_cause": {cause: immediate_causes[cause] for cause in ROOT_CAUSES},
        })
        ordinal += 1
        if not trace_opportunity and not backlog:
            break
    for index, transaction in enumerate(transactions):
        if index in committed and any(parent not in committed or commit_ordinal[parent] > commit_ordinal[index] for parent in transaction.predecessors):
            raise AssertionError("fixed-service replay committed before an immutable predecessor")
    completion = "drained" if not backlog else "prefix_censored_backlog_remains"
    immediate = Counter()
    for row in opportunity_rows:
        immediate.update(row["post_service_backlog_by_immediate_cause"])
    delays = [commit_ordinal[index] - transaction.arrival_ordinal for index, transaction in enumerate(transactions) if index in commit_ordinal]
    phase_rows = {}
    for phase in (*PHASES, POST_TRACE_DRAIN_PHASE):
        items = [row for row in opportunity_rows if row["phase"] == phase]
        if items:
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
        "policy": "fixed_global_abstract_quantum_per_bank_per_operation",
        "fixed_abstract_quantum_per_bank_per_operation_per_logical_opportunity": quantum,
        "transaction_group_count": len(transactions),
        "committed_transaction_group_count": len(committed),
        "completion_state": completion,
        "post_trace_drain_limit": post_trace_drain_limit,
        "post_trace_drain_opportunities_used": max(0, len(opportunity_rows) - len(opportunities)),
        "logical_opportunity_count": len(opportunity_rows),
        "pre_service_backlog": distribution(row["pre_service_backlog"] for row in opportunity_rows),
        "post_service_backlog": distribution(row["post_service_backlog"] for row in opportunity_rows),
        "post_service_age_max": distribution(row["post_service_age_max"] for row in opportunity_rows),
        "logical_opportunity_epoch_delay": distribution(delays),
        "backlog_group_observations_by_blocking_cause": {cause: immediate[cause] for cause in ROOT_CAUSES},
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


def main() -> None:
    args = parse_args()
    a480, a481a = validate_inputs(args)
    if args.preflight_only:
        print("A4.8.1b preflight passed: A4.8.1a/A4.8.0 fixed baselines and the full hash-bound predecessor chain validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a480_rows = {row_key(row): row for row in a480["replay_rows"]}
    a481a_rows = {row_key(row): row for row in a481a["readiness_root_cause_rows"]}
    if len(a480_rows) != len(a480["replay_rows"]) or len(a481a_rows) != len(a481a["readiness_root_cause_rows"]):
        raise AssertionError("duplicate baseline context/profile row")
    rows = []
    for context, record_ops, groups in iter_contexts(args.a468220_trace, args.a471_trace):
        predecessors, dependency_sources = dependency_predecessors(record_ops, groups)
        for profile in CANDIDATE_PROFILES:
            transactions, opportunities = make_scheduled_transactions(groups, predecessors, profile)
            key = (*context, str(profile["profile"]))
            if key not in a480_rows or key not in a481a_rows:
                raise AssertionError("A4.8.0/A4.8.1a baseline missing context/profile")
            a480_row, a481a_row = a480_rows[key], a481a_rows[key]
            causal = a481a_row["readiness_root_cause_audit"]
            if not a481a_row.get("a480_causal_replay_reproduced_exactly") or not baseline_equivalent(causal, a480_row["causal_elastic_replay"]):
                raise AssertionError("A4.8.1a causal baseline no longer exactly matches A4.8.0")
            direct = a480_row["direct_service_baseline"]
            if direct.get("completion_state") != "drained" or direct.get("committed_transaction_group_count") != len(transactions):
                raise AssertionError("A4.8.0 direct baseline contract is incomplete")
            fixed_rows = [audit_fixed_service_replay(transactions=transactions, opportunities=opportunities, profile=profile, quantum=quantum, post_trace_drain_limit=DEFAULT_POST_TRACE_DRAIN_LIMIT) for quantum in FIXED_QUANTA]
            rows.append({
                "anchor": context[0], "workload": context[1], "evaluation_horizon_append_opportunities": context[2], "organization_label": context[3],
                **profile, "transaction_group_count": len(transactions), "intrinsic_dependency_edge_sources": dependency_sources,
                "direct_service_baseline": direct, "causal_controller_baseline": causal,
                "fixed_service_rows": fixed_rows,
            })
    expected_keys = set(a480_rows)
    if expected_keys != set(a481a_rows) or expected_keys != {row_key(row) for row in rows}:
        raise AssertionError("A4.8.1b coverage does not equal both fixed baselines")
    config = {
        "a480_fixed_config_hash": a480["config_hash"],
        "a481a_fixed_config_hash": a481a["config_hash"],
        "candidate_profiles": CANDIDATE_PROFILES,
        "fixed_global_abstract_service_quanta_per_bank_per_operation_per_logical_opportunity": list(FIXED_QUANTA),
        "fixed_service_rule": "At every recorded logical opportunity, each modeled bank/operation starts with the declared fixed quantum. Stable immutable transaction order and fixed dependencies decide eligibility; no workload identity, horizon, future arrival, backlog/age adaptation, borrowing, or scheduler action enters the fixed sweep.",
        "root_lineage_rule": a481a["config"]["root_lineage_rule"],
        "boundary": "Fixed quanta, readiness, root amplification, drain observations, and logical opportunity epoch are model coordinates only; they are not hardware service rates, queues, banks/ports, transactions, cycles, timing, latency, traffic, bandwidth, throughput, energy, area, architecture selection, or RTL.",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(),
        "config": config, "config_hash": stable_hash(config),
        "execution_classification": "trace-derived immutable transaction inputs with functional fixed-service replay and fixed A4.8.0/A4.8.1a baselines; not measured hardware behavior",
        "input_artifacts": {
            "a468220_trace_sha256": sha256_file(args.a468220_trace), "a470_report_sha256": sha256_file(args.a470_report),
            "a471_report_sha256": sha256_file(args.a471_report), "a471_trace_sha256": sha256_file(args.a471_trace),
            "a4720_report_sha256": sha256_file(args.a4720_report), "a4721_report_sha256": sha256_file(args.a4721_report),
            "a480_report_sha256": sha256_file(args.a480_report), "a481a_report_sha256": sha256_file(args.a481a_report),
        },
        "fixed_service_sweep_rows": rows,
        "semantic_guards": {
            "a481a_a480_and_full_predecessor_hash_chain_validated": True,
            "direct_and_causal_baselines_preserved_side_by_side": True,
            "a481a_causal_baseline_still_exactly_matches_a480": True,
            "all_fixed_quanta_global_preregistered_and_not_trace_tuned": True,
            "no_transaction_dependency_fifo_mapping_or_commit_boundary_changed": True,
            "fixed_sweep_uses_no_future_anchor_workload_horizon_or_runtime_controller_input": True,
            "ready_dependency_blocked_and_root_amplification_reported_for_every_fixed_quantum": True,
            "root_lineage_remains_declared_canonical_attribution_not_hardware_causality": True,
            "no_new_scheduler_borrowing_or_controller_policy_introduced": True,
            "no_model_runtime_profiler_or_hardware_parameter_loaded": True,
            "no_hardware_queue_access_cycle_timing_performance_or_architecture_claim": True,
        },
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a481b_fixed_service_sweep_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.8.1b complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} rows={len(rows)} quanta={len(FIXED_QUANTA)}")


if __name__ == "__main__":
    main()
