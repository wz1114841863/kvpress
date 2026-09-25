#!/usr/bin/env python3
"""A4.8.2b bounded Route-A contract-simplification replay.

This consumes only the two A4.8.2a-admitted templates.  It holds the A4.8.1b
arrival order, dependencies, FIFO order, group commit boundary, candidate
profile, and fixed abstract service sweep unchanged.  The eager template must
reproduce A4.8.1b exactly.  The alternate template changes only every existing
*modeled storage-object* RMW demand into a read and write demand on that same
object, both required before the unchanged group commit.

Semantic-record ledger work and modeled storage-object service demand are
reported separately: storage-object co-location can make their counts differ.
Neither is a hardware access, atomic instruction, queue, bank/port, cycle,
latency, traffic, bandwidth, throughput, energy, area, architecture choice, or
RTL result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a480_commit_aware_backlog import (
    CANDIDATE_PROFILES,
    DEFAULT_POST_TRACE_DRAIN_LIMIT,
    ScheduledTransaction,
    dependency_predecessors,
    distribution,
    iter_contexts,
    make_scheduled_transactions,
)
from tools.analyze_kvzap_route_a481a_readiness_root_cause import (
    baseline_equivalent,
    row_key,
)
from tools.analyze_kvzap_route_a481b_fixed_service_sweep import (
    FIXED_QUANTA,
    audit_fixed_service_replay,
)
from tools.analyze_kvzap_route_a482a_contract_simplification_gate import (
    OPTIONS,
    SCHEMA as A482A_SCHEMA,
    validate_inputs as validate_a482a_inputs,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a482b-contract-simplification-replay-1.0"
EAGER_OPTION = "eager_authoritative_rmw_v1"
EXPANDED_OPTION = "same_record_read_write_commit_exclusion_v1"
OPTIONS_TO_REPLAY = (EAGER_OPTION, EXPANDED_OPTION)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.8.2b no-model bounded contract-simplification replay beside "
            "the fixed A4.8.1b sweep; logical contract/model quantities only, "
            "never hardware timing or performance."
        )
    )
    parser.add_argument("--a468220-trace", type=Path, required=True)
    parser.add_argument("--a470-report", type=Path, required=True)
    parser.add_argument("--a471-report", type=Path, required=True)
    parser.add_argument("--a471-trace", type=Path, required=True)
    parser.add_argument("--a4720-report", type=Path, required=True)
    parser.add_argument("--a4721-report", type=Path, required=True)
    parser.add_argument("--a480-report", type=Path, required=True)
    parser.add_argument("--a481a-report", type=Path, required=True)
    parser.add_argument("--a481b-report", type=Path, required=True)
    parser.add_argument("--a482a-report", type=Path, required=True)
    parser.add_argument(
        "--post-trace-drain-limit", type=int, default=DEFAULT_POST_TRACE_DRAIN_LIMIT,
        help="Must equal the fixed 512 no-arrival logical observation bound; not a timing parameter.",
    )
    parser.add_argument(
        "--preflight-only", action="store_true",
        help="Validate the complete A4.8.2a/A4.8.1b hash-bound chain without creating output.",
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def context_key(row: dict[str, Any]) -> tuple[str, str, int, str]:
    return (
        str(row["anchor"]), str(row["workload"]),
        int(row["evaluation_horizon_append_opportunities"]), str(row["organization_label"]),
    )


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Bind the closed A4.8.2a catalog to immutable A4.8.1b inputs."""
    if args.post_trace_drain_limit != DEFAULT_POST_TRACE_DRAIN_LIMIT:
        raise ValueError("A4.8.2b fixes the A4.8.0/A4.8.1b no-arrival observation bound at 512")
    a480, a481a, a481b = validate_a482a_inputs(args)
    a482a = read_completed(args.a482a_report, A482A_SCHEMA, "A4.8.2a")
    expected_inputs = {
        "a468220_trace_sha256": sha256_file(args.a468220_trace),
        "a470_report_sha256": sha256_file(args.a470_report),
        "a471_report_sha256": sha256_file(args.a471_report),
        "a471_trace_sha256": sha256_file(args.a471_trace),
        "a4720_report_sha256": sha256_file(args.a4720_report),
        "a4721_report_sha256": sha256_file(args.a4721_report),
        "a480_report_sha256": sha256_file(args.a480_report),
        "a481a_report_sha256": sha256_file(args.a481a_report),
        "a481b_report_sha256": sha256_file(args.a481b_report),
    }
    if a482a.get("input_artifacts") != expected_inputs:
        raise ValueError("A4.8.2a input hash binding mismatch")
    if a482a.get("config", {}).get("a481b_fixed_config_hash") != a481b.get("config_hash"):
        raise ValueError("A4.8.2a does not bind the supplied fixed A4.8.1b configuration")
    required = (
        "a481b_a481a_a480_and_full_predecessor_hash_chain_validated",
        "frozen_four_record_catalog_and_a471_transaction_boundaries_unchanged",
        "every_context_replays_authoritative_state_after_every_unchanged_commit",
        "same_record_read_write_expansion_preserves_record_identity_and_adds_no_semantic_state",
        "all_expanded_read_write_pairs_publish_only_at_existing_commit_boundary",
        "expanded_rmw_work_and_same_record_commit_exclusion_obligation_accounted_explicitly",
        "a482a_contract_simplification_variant_catalog_closed",
    )
    if not all(a482a.get("semantic_guards", {}).get(name) is True for name in required):
        raise ValueError("A4.8.2a semantic guards incomplete")
    admitted = tuple(name for name, item in a482a["config"]["contract_options"].items() if item["admitted_to_a482b"])
    if admitted != OPTIONS_TO_REPLAY or set(OPTIONS) != set(a482a["config"]["contract_options"]):
        raise ValueError("A4.8.2a admitted option catalog is not the frozen two-template interface")
    return a480, a481a, a481b, a482a


def expand_modeled_rmw_demands(demands: Counter[tuple[int, str]], option: str) -> Counter[tuple[int, str]]:
    """Map only an existing modeled-object RMW to same-object R+W demand."""
    if option not in OPTIONS_TO_REPLAY:
        raise ValueError("option is not admitted to A4.8.2b")
    result: Counter[tuple[int, str]] = Counter()
    for (bank, operation), count in demands.items():
        if count < 0:
            raise AssertionError("negative modeled demand")
        if option == EXPANDED_OPTION and operation == "rmw":
            result[(bank, "read")] += count
            result[(bank, "write")] += count
        else:
            result[(bank, operation)] += count
    return result


def variant_transactions(transactions: list[ScheduledTransaction], option: str) -> list[ScheduledTransaction]:
    """Preserve all immutable group identity/order/dependencies and banks."""
    output = []
    for transaction in transactions:
        demands = expand_modeled_rmw_demands(transaction.demands, option)
        if not demands:
            raise AssertionError("variant transaction lost all modeled work")
        output.append(ScheduledTransaction(
            index=transaction.index, phase=transaction.phase, checkpoint=transaction.checkpoint,
            layer=transaction.layer, head=transaction.head,
            arrival_ordinal=transaction.arrival_ordinal,
            predecessors=transaction.predecessors, demands=demands,
            banks=frozenset(bank for bank, _ in demands),
        ))
    return output


def transaction_identity_equal(left: list[ScheduledTransaction], right: list[ScheduledTransaction]) -> bool:
    return len(left) == len(right) and all(
        (a.index, a.phase, a.checkpoint, a.layer, a.head, a.arrival_ordinal, a.predecessors, a.banks)
        == (b.index, b.phase, b.checkpoint, b.layer, b.head, b.arrival_ordinal, b.predecessors, b.banks)
        for a, b in zip(left, right)
    )


def modeled_work_ledger(transactions: Iterable[ScheduledTransaction]) -> dict[str, int]:
    ledger: Counter[str] = Counter()
    for transaction in transactions:
        for (_, operation), count in transaction.demands.items():
            ledger[f"{operation}_modeled_storage_object_work"] += int(count)
    ledger["total_modeled_storage_object_work"] = sum(
        value for name, value in ledger.items() if name.endswith("_modeled_storage_object_work")
    )
    return dict(sorted(ledger.items()))


def option_summary(rows: list[dict[str, Any]], option: str) -> dict[str, Any]:
    """Aggregate outcomes without selecting an abstract service level."""
    result = {}
    for quantum in FIXED_QUANTA:
        audits = [row["option_fixed_service_replays"][option][str(quantum)] for row in rows]
        readiness = [audit["readiness"] for audit in audits]
        result[str(quantum)] = {
            "context_profile_row_count": len(audits),
            "completion_state_counts": dict(sorted(Counter(str(audit["completion_state"]) for audit in audits).items())),
            "post_service_ready_backlog_max": distribution(audit["readiness"]["post_service_ready_backlog"]["max"] for audit in audits),
            "post_service_ready_age_max": distribution(audit["readiness"]["post_service_ready_age_max"]["max"] for audit in audits),
            "trace_end_ready_residual": distribution(item["trace_end_residual_backlog"]["ready"] for item in readiness),
            "additional_no_arrival_drain_logical_opportunities": distribution(item["additional_post_trace_drain_logical_opportunities"] for item in readiness),
            "sustained_ready_positive_logical_opportunity_run": distribution(item["sustained_post_service_ready_positive_logical_opportunity_run"] for item in readiness),
            "root_lineage_amplification": {
                cause: distribution(
                    audit["root_cause_amplification"][cause]["unique_downstream_transaction_count"]
                    for audit in audits
                )
                for cause in next(iter(audits))["root_cause_amplification"]
            },
        }
    return result


def static_footprint_reference(a4721: dict[str, Any]) -> list[dict[str, Any]]:
    """Retain, rather than select, fixed A4.7.2.1 footprint references."""
    references = []
    for row in a4721.get("static_candidate_rows", []):
        if row.get("layout") == "both_colocated_direct_v1":
            references.append({
                "layout": row["layout"], "storage_scope": row["storage_scope"],
                "namespace_policy": row["namespace_policy"], "generation_bits": row["generation_bits"],
                "cross_context_joint_safe_modeled_metadata_bits": row["cross_context_joint_safe_modeled_metadata_bits"],
            })
    if not references:
        raise AssertionError("A4.8.0 profile layout has no fixed A4.7.2.1 footprint reference")
    return references


def main() -> None:
    args = parse_args()
    a480, a481a, a481b, a482a = validate_inputs(args)
    if args.preflight_only:
        print("A4.8.2b preflight passed: A4.8.2a's closed two-template catalog and the full A4.8.1b/A4.8.1a/A4.8.0 chain validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")

    a480_rows = {row_key(row): row for row in a480["replay_rows"]}
    a481a_rows = {row_key(row): row for row in a481a["readiness_root_cause_rows"]}
    a481b_rows = {row_key(row): row for row in a481b["fixed_service_sweep_rows"]}
    predecessor_maps = (
        (a480_rows, a480["replay_rows"]),
        (a481a_rows, a481a["readiness_root_cause_rows"]),
        (a481b_rows, a481b["fixed_service_sweep_rows"]),
    )
    if any(len(mapping) != len(source) for mapping, source in predecessor_maps):
        raise AssertionError("duplicate immutable predecessor context/profile row")
    semantic_rows = {context_key(row): row for row in a482a["context_rows"]}
    if len(semantic_rows) != len(a482a["context_rows"]):
        raise AssertionError("duplicate A4.8.2a semantic context row")

    rows = []
    for context, record_ops, groups in iter_contexts(args.a468220_trace, args.a471_trace):
        predecessors, dependency_sources = dependency_predecessors(record_ops, groups)
        if context not in semantic_rows:
            raise AssertionError("A4.8.2a semantic ledger missing immutable context")
        for profile in CANDIDATE_PROFILES:
            key = (*context, str(profile["profile"]))
            if key not in a480_rows or key not in a481a_rows or key not in a481b_rows:
                raise AssertionError("A4.8.0/A4.8.1 baseline missing immutable context/profile")
            base_transactions, opportunities = make_scheduled_transactions(groups, predecessors, profile)
            variants = {option: variant_transactions(base_transactions, option) for option in OPTIONS_TO_REPLAY}
            if not transaction_identity_equal(base_transactions, variants[EAGER_OPTION]) or not transaction_identity_equal(base_transactions, variants[EXPANDED_OPTION]):
                raise AssertionError("A4.8.2b lowering changed immutable transaction identity")
            if any(item.demands != base.demands for item, base in zip(variants[EAGER_OPTION], base_transactions)):
                raise AssertionError("eager A4.8.2b lowering does not exactly retain A4.8.1b demands")
            if any(any(operation == "rmw" for _, operation in item.demands) for item in variants[EXPANDED_OPTION]):
                raise AssertionError("expanded A4.8.2b lowering retained modeled RMW work")
            replays = {
                option: {
                    str(quantum): audit_fixed_service_replay(
                        transactions=variants[option], opportunities=opportunities, profile=profile,
                        quantum=quantum, post_trace_drain_limit=DEFAULT_POST_TRACE_DRAIN_LIMIT,
                    )
                    for quantum in FIXED_QUANTA
                }
                for option in OPTIONS_TO_REPLAY
            }
            expected_eager = {
                str(item["fixed_abstract_quantum_per_bank_per_operation_per_logical_opportunity"]): item
                for item in a481b_rows[key]["fixed_service_rows"]
            }
            if replays[EAGER_OPTION] != expected_eager:
                raise AssertionError("A4.8.2b eager fixed replay does not exactly reproduce A4.8.1b")
            causal = a481a_rows[key]["readiness_root_cause_audit"]
            if not a481a_rows[key].get("a480_causal_replay_reproduced_exactly") or not baseline_equivalent(causal, a480_rows[key]["causal_elastic_replay"]):
                raise AssertionError("A4.8.1a causal reference no longer exactly reproduces A4.8.0")
            rows.append({
                "anchor": context[0], "workload": context[1],
                "evaluation_horizon_append_opportunities": context[2], "organization_label": context[3],
                **profile, "transaction_group_count": len(base_transactions),
                "intrinsic_dependency_edge_sources": dependency_sources,
                "a482a_semantic_record_work_ledger": semantic_rows[context]["option_work_ledgers"],
                "modeled_storage_object_work_ledger": {option: modeled_work_ledger(variants[option]) for option in OPTIONS_TO_REPLAY},
                "a480_direct_service_reference": a480_rows[key]["direct_service_baseline"],
                "a481a_causal_controller_reference": causal,
                "option_fixed_service_replays": replays,
            })

    expected_keys = set(a480_rows)
    if expected_keys != set(a481a_rows) or expected_keys != set(a481b_rows) or expected_keys != {row_key(row) for row in rows}:
        raise AssertionError("A4.8.2b context/profile coverage does not equal every immutable predecessor baseline")
    if set(semantic_rows) != {context_key(row) for row in rows}:
        raise AssertionError("A4.8.2b semantic context coverage does not equal replay coverage")
    semantic_ledger = a482a["aggregate_option_work_ledgers"]
    modeled_ledger: dict[str, Counter[str]] = {option: Counter() for option in OPTIONS_TO_REPLAY}
    for row in rows:
        for option in OPTIONS_TO_REPLAY:
            modeled_ledger[option].update(row["modeled_storage_object_work_ledger"][option])
    a4721 = read_completed(args.a4721_report, "kvzap-route-a4721-metadata-physical-dse-1.2", "A4.7.2.1 _03")
    config = {
        "a480_fixed_config_hash": a480["config_hash"], "a481a_fixed_config_hash": a481a["config_hash"],
        "a481b_fixed_config_hash": a481b["config_hash"], "a482a_fixed_config_hash": a482a["config_hash"],
        "admitted_contract_options": {name: a482a["config"]["contract_options"][name] for name in OPTIONS_TO_REPLAY},
        "fixed_quanta": list(FIXED_QUANTA), "candidate_profiles": CANDIDATE_PROFILES,
        "variant_lowering_rule": "Keep every A4.7.2.1 modeled storage object and immutable A4.7.1 transaction group fixed. In the alternate admitted template, map each existing modeled-object RMW demand to one read plus one write demand on that same object; both remain required before the unchanged group commit/linearization boundary.",
        "footprint_rule": "Both templates retain A4.8.2a's four semantic record classes and add zero semantic records. The A4.7.2.1 modeled storage-footprint reference is therefore unchanged. The same-record commit-exclusion obligation has no selected realization and its physical footprint is explicitly unmodeled rather than assumed zero.",
        "boundary": "Semantic ledger work, modeled storage-object demand, abstract fixed quanta, ready backlog/age, root lineage, and no-arrival drain opportunities are trace-derived/functional/model quantities only. They are not hardware accesses, atomics, queues, bank/port service rates, cycles, timing, latency, traffic, bandwidth, throughput, energy, area, architecture selection, or RTL.",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "execution_classification": "trace-derived immutable transaction inputs with functional fixed-service replay and logical semantic/storage-object accounting; not measured hardware behavior",
        "input_artifacts": {
            "a468220_trace_sha256": sha256_file(args.a468220_trace), "a470_report_sha256": sha256_file(args.a470_report),
            "a471_report_sha256": sha256_file(args.a471_report), "a471_trace_sha256": sha256_file(args.a471_trace),
            "a4720_report_sha256": sha256_file(args.a4720_report), "a4721_report_sha256": sha256_file(args.a4721_report),
            "a480_report_sha256": sha256_file(args.a480_report), "a481a_report_sha256": sha256_file(args.a481a_report),
            "a481b_report_sha256": sha256_file(args.a481b_report), "a482a_report_sha256": sha256_file(args.a482a_report),
        },
        "semantic_record_work_unique_contexts": semantic_ledger,
        "modeled_storage_object_work_across_context_profile_rows": {name: dict(sorted(ledger.items())) for name, ledger in modeled_ledger.items()},
        "footprint_contract": {
            "semantic_record_catalog": a482a["config"]["frozen_semantic_record_catalog"],
            "additional_semantic_record_count": {name: semantic_ledger[name]["additional_semantic_record_count"] for name in OPTIONS_TO_REPLAY},
            "a4721_fixed_modeled_storage_footprint_references": static_footprint_reference(a4721),
            "same_record_commit_exclusion_physical_footprint": "unselected_and_not_assumed_zero",
        },
        "fixed_service_outcome_summary": {name: option_summary(rows, name) for name in OPTIONS_TO_REPLAY},
        "context_profile_rows": rows,
        "semantic_guards": {
            "a482a_closed_option_catalog_and_full_predecessor_hash_chain_validated": True,
            "only_a482a_admitted_eager_and_same_record_read_write_templates_consumed": True,
            "eager_modeled_storage_object_demands_and_every_fixed_replay_exactly_reproduce_a481b": True,
            "transaction_group_identity_dependencies_fifo_order_mapping_and_commit_boundary_unchanged": True,
            "expanded_read_and_write_are_same_object_and_jointly_required_before_existing_commit": True,
            "semantic_record_work_and_modeled_storage_object_demand_reported_separately": True,
            "semantic_catalog_and_a4721_footprint_reference_unchanged_commit_exclusion_footprint_unselected": True,
            "direct_and_causal_baselines_preserved_as_immutable_references": True,
            "ready_backlog_age_residual_drain_and_root_lineage_reported_for_every_option_quantum": True,
            "no_new_scheduler_controller_future_input_or_semantic_variant_introduced": True,
            "no_model_runtime_profiler_or_hardware_parameter_loaded": True,
            "no_hardware_access_queue_cycle_timing_performance_or_architecture_claim": True,
        },
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a482b_contract_simplification_replay_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.8.2b complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} rows={len(rows)} quanta={len(FIXED_QUANTA)}")


if __name__ == "__main__":
    main()
