#!/usr/bin/env python3
"""A4.9.0 final no-model envelope closure for the eager Route-A RMW contract.

This is deliberately the final envelope stage.  It consumes the closed A4.8.2
result, retains eager authoritative RMW semantics, and reports only existing
A4.7.2 storage references plus per-atomic-group temporary state and fanout.
It does not choose a bank count, SRAM organization, RMW lane count, port
organization, queue depth, cycle count, or final architecture specification.
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
from tools.analyze_kvzap_route_a4720_metadata_storage_sufficiency import (
    SCHEMA as A4720_SCHEMA,
)
from tools.analyze_kvzap_route_a4721_metadata_physical_dse import (
    SCHEMA as A4721_SCHEMA,
    bank_index,
    lower_transaction,
)
from tools.analyze_kvzap_route_a480_commit_aware_backlog import (
    CANDIDATE_PROFILES,
    DEFAULT_POST_TRACE_DRAIN_LIMIT,
    dependency_predecessors,
    distribution,
    iter_contexts,
    make_scheduled_transactions,
)
from tools.analyze_kvzap_route_a481a_readiness_root_cause import row_key
from tools.analyze_kvzap_route_a482b_contract_simplification_replay import (
    EAGER_OPTION,
    SCHEMA as A482B_SCHEMA,
    modeled_work_ledger,
    validate_inputs as validate_a482b_inputs,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a490-eager-rmw-envelope-1.0"
OBSERVATION_QUANTUM = 4
LAYOUT = "both_colocated_direct_v1"
PHASES = ("activation", "steady_state_append", "steady_state_dequeue")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.9.0 final no-model eager-RMW envelope closure. It reports "
            "trace-derived/model state and fanout only; never selected hardware "
            "banks, ports, queues, cycles, timing, or performance."
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
    parser.add_argument("--a482b-report", type=Path, required=True)
    parser.add_argument(
        "--post-trace-drain-limit", type=int, default=DEFAULT_POST_TRACE_DRAIN_LIMIT,
        help="Inherited fixed 512 no-arrival observation bound for predecessor validation; not a timing parameter.",
    )
    parser.add_argument("--preflight-only", action="store_true", help="Validate the complete eager-RMW predecessor chain without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def context_key(row: dict[str, Any]) -> tuple[str, str, int, str]:
    return (
        str(row["anchor"]), str(row["workload"]),
        int(row["evaluation_horizon_append_opportunities"]), str(row["organization_label"]),
    )


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Reuse A4.8.2b's complete predecessor validation, then bind its result."""
    a480, a481a, a481b, a482a = validate_a482b_inputs(args)
    a482b = read_completed(args.a482b_report, A482B_SCHEMA, "A4.8.2b")
    a4720 = read_completed(args.a4720_report, A4720_SCHEMA, "A4.7.2.0")
    a4721 = read_completed(args.a4721_report, A4721_SCHEMA, "A4.7.2.1 _03")
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
        "a482a_report_sha256": sha256_file(args.a482a_report),
    }
    if a482b.get("input_artifacts") != expected_inputs:
        raise ValueError("A4.8.2b input hash binding mismatch")
    if a482b.get("config", {}).get("a482a_fixed_config_hash") != a482a.get("config_hash"):
        raise ValueError("A4.8.2b does not bind the supplied A4.8.2a configuration")
    required = (
        "a482a_closed_option_catalog_and_full_predecessor_hash_chain_validated",
        "only_a482a_admitted_eager_and_same_record_read_write_templates_consumed",
        "eager_modeled_storage_object_demands_and_every_fixed_replay_exactly_reproduce_a481b",
        "transaction_group_identity_dependencies_fifo_order_mapping_and_commit_boundary_unchanged",
        "semantic_record_work_and_modeled_storage_object_demand_reported_separately",
        "ready_backlog_age_residual_drain_and_root_lineage_reported_for_every_option_quantum",
    )
    if not all(a482b.get("semantic_guards", {}).get(name) is True for name in required):
        raise ValueError("A4.8.2b semantic guards incomplete")
    if set(a482b.get("fixed_service_outcome_summary", {}).get(EAGER_OPTION, {})) != {"1", "2", "4", "8", "16"}:
        raise ValueError("A4.8.2b eager fixed sweep is incomplete")
    if not any(row.get("layout") == LAYOUT for row in a4721.get("static_candidate_rows", [])):
        raise ValueError("the fixed A4.8 profile layout is absent from A4.7.2.1")
    return a480, a481a, a481b, a482a, a482b


def selected_width_rows(a4720: dict[str, Any]) -> list[dict[str, Any]]:
    """Retain all pre-existing zero-slack references; select none of them."""
    rows = [
        row for row in a4720["width_sufficiency_rows"]
        if row["layout"] == LAYOUT and int(row["width_slack_bits"]) == 0
        and row["namespace_width_sufficient"]
    ]
    if not rows:
        raise AssertionError("no zero-slack sufficient persistent metadata reference")
    return rows


def persistent_envelope(width_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep A4.7.2.0 per-context observations separate from joint-safe bounds."""
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in width_rows:
        grouped[(str(row["storage_scope"]), str(row["namespace_policy"]), int(row["generation_bits"]))].append(row)
    output = []
    for (scope, policy, generation_bits), rows in sorted(grouped.items()):
        context_keys = {context_key(row) for row in rows}
        fields = rows[0]["field_widths_bits"]
        object_types = rows[0]["modeled_peak_storage_object_counts"]
        output.append({
            "layout": LAYOUT, "storage_scope": scope, "namespace_policy": policy,
            "generation_bits": generation_bits, "context_count": len(context_keys),
            "modeled_peak_metadata_bits": distribution(int(row["modeled_peak_metadata_bits"]) for row in rows),
            "maximum_field_widths_bits": {name: max(int(row["field_widths_bits"][name]) for row in rows) for name in fields},
            "maximum_modeled_storage_object_counts": {name: max(int(row["modeled_peak_storage_object_counts"][name]) for row in rows) for name in object_types},
            "reference_rule": "Existing A4.7.2.0 zero-slack sufficient rows only; this is a modeled metadata-bit envelope, not allocated SRAM capacity or a selected organization.",
        })
    return output


def joint_safe_persistent_references(a4721: dict[str, Any]) -> list[dict[str, Any]]:
    """Use A4.7.2.1's pre-existing cross-context-safe, nonselected references."""
    references = []
    for row in a4721.get("static_candidate_rows", []):
        if row.get("layout") != LAYOUT:
            continue
        references.append({
            "layout": row["layout"], "storage_scope": row["storage_scope"],
            "namespace_policy": row["namespace_policy"], "generation_bits": row["generation_bits"],
            "context_count": row["context_count"],
            "cross_context_joint_safe_modeled_metadata_bits": row["cross_context_joint_safe_modeled_metadata_bits"],
            "cross_context_joint_safe_field_widths_bits": row["cross_context_joint_safe_field_widths_bits"],
            "cross_context_joint_safe_modeled_storage_object_counts": row["cross_context_joint_safe_modeled_storage_object_counts"],
            "reference_rule": row["joint_safe_footprint_rule"],
            "physical_entry_not_selected": row["physical_entry_not_selected"],
        })
    if not references:
        raise AssertionError("A4.7.2.1 has no joint-safe persistent footprint reference for the fixed layout")
    return references


def group_temporary_state(group: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """One atomic-group envelope; it does not infer multi-group pipeline depth."""
    lowered = lower_transaction(group, LAYOUT)
    operations = Counter(lowered.values())
    banks = {
        bank_index(
            str(profile["bank_mapping"]), int(profile["bank_count"]), object_key,
            layer=int(group["layer"]), head=int(group["kv_head"]),
        )
        for object_key in lowered
    }
    return {
        "phase": str(group["phase"]),
        "atomic_group_touched_modeled_storage_objects": len(lowered),
        "atomic_group_commit_guarded_modeled_storage_objects": operations["write"] + operations["rmw"],
        "atomic_group_rmw_exclusion_objects": operations["rmw"],
        "atomic_group_read_only_modeled_storage_objects": operations["read"],
        "atomic_group_modeled_bank_fanout": len(banks),
        "atomic_group_cross_bank_commit": len(banks) > 1,
        "operation_mix": {operation: operations[operation] for operation in ("read", "write", "rmw")},
        "temporary_state_boundary": "Counts are one immutable atomic group's touched/commit-guarded/RMW-exclusion modeled objects. They do not choose a queue depth, number of in-flight groups, lock encoding, SRAM entry, port, or cycle implementation.",
    }


def summarize_temporary_state(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(items)
    if not rows:
        raise AssertionError("empty temporary-state envelope")
    fields = (
        "atomic_group_touched_modeled_storage_objects",
        "atomic_group_commit_guarded_modeled_storage_objects",
        "atomic_group_rmw_exclusion_objects",
        "atomic_group_read_only_modeled_storage_objects",
        "atomic_group_modeled_bank_fanout",
    )
    operations = ("read", "write", "rmw")
    return {
        "transaction_group_count": len(rows),
        "per_atomic_group": {field: distribution(int(row[field]) for row in rows) for field in fields},
        "cross_bank_atomic_group_count": sum(bool(row["atomic_group_cross_bank_commit"]) for row in rows),
        "operation_mix_per_atomic_group": {
            operation: distribution(int(row["operation_mix"][operation]) for row in rows)
            for operation in operations
        },
        "temporary_state_scope": "per immutable A4.7.1 atomic group only; a multi-group in-flight bound remains intentionally unselected for A4.9.1 candidate microarchitecture DSE",
    }


def reasoning_observation(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Use A4.8.2b's already-fixed q=4 observation, never as a chosen rate."""
    items = [
        row["option_fixed_service_replays"][EAGER_OPTION][str(OBSERVATION_QUANTUM)]
        for row in rows if str(row["workload"]) == "reasoning"
    ]
    if not items:
        raise AssertionError("reasoning workload missing from eager observation")
    readiness = [item["readiness"] for item in items]
    all_drained = all(item["completion_state"] == "drained" for item in items)
    return {
        "context_profile_row_count": len(items),
        "observation_quantum": OBSERVATION_QUANTUM,
        "completion_state_counts": dict(sorted(Counter(item["completion_state"] for item in items).items())),
        "post_service_ready_backlog_max": distribution(item["post_service_ready_backlog"]["max"] for item in readiness),
        "post_service_ready_age_max": distribution(item["post_service_ready_age_max"]["max"] for item in readiness),
        "trace_end_ready_residual": distribution(item["trace_end_residual_backlog"]["ready"] for item in readiness),
        "additional_no_arrival_drain_logical_opportunities": distribution(item["additional_post_trace_drain_logical_opportunities"] for item in readiness),
        "sustained_ready_positive_logical_opportunity_run": distribution(item["sustained_post_service_ready_positive_logical_opportunity_run"] for item in readiness),
        "observed_bounded_drain_within_fixed_trace_window": all_drained,
        "boundary": "This only observes finite trace replay plus A4.8.1b's fixed 512 no-arrival continuation. It cannot prove mathematical boundedness on arbitrary future workloads and does not select a hardware service rate.",
    }


def main() -> None:
    args = parse_args()
    a480, a481a, a481b, a482a, a482b = validate_inputs(args)
    a4720 = read_completed(args.a4720_report, A4720_SCHEMA, "A4.7.2.0")
    a4721 = read_completed(args.a4721_report, A4721_SCHEMA, "A4.7.2.1 _03")
    if args.preflight_only:
        print("A4.9.0 preflight passed: eager A4.8.2b closure and complete predecessor hash/guard chain validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")

    a482b_rows = {row_key(row): row for row in a482b["context_profile_rows"]}
    if len(a482b_rows) != len(a482b["context_profile_rows"]):
        raise AssertionError("duplicate A4.8.2b context/profile row")
    temporary_rows = []
    expected_profile_keys = set()
    for context, record_ops, groups in iter_contexts(args.a468220_trace, args.a471_trace):
        predecessors, _ = dependency_predecessors(record_ops, groups)
        for profile in CANDIDATE_PROFILES:
            key = (*context, str(profile["profile"]))
            expected_profile_keys.add(key)
            if key not in a482b_rows:
                raise AssertionError("A4.8.2b eager reference missing immutable context/profile")
            transactions, _ = make_scheduled_transactions(groups, predecessors, profile)
            if modeled_work_ledger(transactions) != a482b_rows[key]["modeled_storage_object_work_ledger"][EAGER_OPTION]:
                raise AssertionError("A4.9.0 eager demand does not exactly reproduce A4.8.2b")
            state = [group_temporary_state(group, profile) for group in groups]
            temporary_rows.append({
                "anchor": context[0], "workload": context[1],
                "evaluation_horizon_append_opportunities": context[2], "organization_label": context[3],
                **profile, "transaction_group_count": len(groups),
                "phase_envelopes": {
                    phase: summarize_temporary_state(row for row in state if row["phase"] == phase)
                    for phase in PHASES if any(row["phase"] == phase for row in state)
                },
                "all_phase_envelope": summarize_temporary_state(state),
            })
    if expected_profile_keys != set(a482b_rows):
        raise AssertionError("A4.9.0 coverage does not equal A4.8.2b")
    width_rows = selected_width_rows(a4720)
    expected_contexts = {context_key(row) for row in a482b["context_profile_rows"]}
    if {context_key(row) for row in width_rows} != expected_contexts:
        raise AssertionError("A4.7.2.0 persistent envelope coverage does not equal A4.8.2b contexts")
    reasoning = reasoning_observation(a482b["context_profile_rows"])
    persistent_observations = persistent_envelope(width_rows)
    persistent_joint_safe = joint_safe_persistent_references(a4721)
    if not all(int(item["context_count"]) == len(expected_contexts) for item in persistent_joint_safe):
        raise AssertionError("A4.7.2.1 joint-safe footprint reference does not cover every A4.9.0 context")
    config = {
        "eager_contract": EAGER_OPTION,
        "layout_reference": LAYOUT,
        "candidate_profiles": CANDIDATE_PROFILES,
        "reasoning_observation_quantum": OBSERVATION_QUANTUM,
        "stage_boundary": "A4.9.0 is the final envelope stage. A pass may authorize A4.9.1 candidate microarchitecture DSE; this stage does not add an A4.9.0.x branch.",
        "pass_observation_rule": "Pass requires finite A4.7.2.1 cross-context joint-safe persistent metadata references, finite per-atomic-group temporary commit/exclusion state and object/bank fanout in every covered context/profile, plus all reasoning q=4 observations draining within the already-fixed continuation bound. A4.7.2.0 per-context maxima are retained only as observations, never substituted for the joint-safe bound. It is finite-trace evidence, not proof for arbitrary workloads.",
        "boundary": "All metadata bits, storage objects, atomic-group state, fanout, abstract q=4 observations, and drain opportunities are trace-derived/functional/model quantities. They are not selected SRAM capacity, bank count, port count, queue depth, RMW lane count, cycles, timing, traffic, bandwidth, throughput, energy, area, architecture specification, or RTL evidence.",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "execution_classification": "trace-derived existing metadata envelopes plus functional eager-RMW transaction replay cross-check; not measured hardware behavior",
        "input_artifacts": {
            "a468220_trace_sha256": sha256_file(args.a468220_trace), "a470_report_sha256": sha256_file(args.a470_report),
            "a471_report_sha256": sha256_file(args.a471_report), "a471_trace_sha256": sha256_file(args.a471_trace),
            "a4720_report_sha256": sha256_file(args.a4720_report), "a4721_report_sha256": sha256_file(args.a4721_report),
            "a480_report_sha256": sha256_file(args.a480_report), "a481a_report_sha256": sha256_file(args.a481a_report),
            "a481b_report_sha256": sha256_file(args.a481b_report), "a482a_report_sha256": sha256_file(args.a482a_report),
            "a482b_report_sha256": sha256_file(args.a482b_report),
        },
        "persistent_metadata_envelope_references": {
            "a4720_per_context_zero_slack_observations": persistent_observations,
            "a4721_cross_context_joint_safe_references": persistent_joint_safe,
        },
        "temporary_commit_and_fanout_envelope_rows": temporary_rows,
        "reasoning_hotspot_observation": reasoning,
        "envelope_exit_observation": {
            "persistent_metadata_cross_context_joint_safe_reference_finite_in_every_covered_a4721_context": all(
                int(item["context_count"]) == len(expected_contexts)
                and int(item["cross_context_joint_safe_modeled_metadata_bits"]) > 0
                for item in persistent_joint_safe
            ),
            "per_atomic_group_temporary_commit_and_rmw_exclusion_state_finite": all(
                item["all_phase_envelope"]["per_atomic_group"]["atomic_group_commit_guarded_modeled_storage_objects"]["max"] is not None
                for item in temporary_rows
            ),
            "transaction_object_and_modeled_bank_fanout_finite": all(
                item["all_phase_envelope"]["per_atomic_group"]["atomic_group_touched_modeled_storage_objects"]["max"] is not None
                and item["all_phase_envelope"]["per_atomic_group"]["atomic_group_modeled_bank_fanout"]["max"] is not None
                for item in temporary_rows
            ),
            "reasoning_observed_to_drain_within_fixed_continuation_not_universal_unboundedness_proof": reasoning["observed_bounded_drain_within_fixed_trace_window"],
        },
        "semantic_guards": {
            "a482b_eager_closure_and_full_predecessor_hash_chain_validated": True,
            "a490_is_final_envelope_stage_without_a490_substage_or_new_semantic_variant": True,
            "a482b_eager_modeled_demand_exactly_reproduced_before_envelope_summary": True,
            "persistent_metadata_retains_a4720_observations_but_uses_existing_a4721_cross_context_joint_safe_references_for_exit": True,
            "temporary_state_is_limited_to_one_unchanged_atomic_group_and_does_not_select_inflight_queue_depth": True,
            "transaction_object_and_bank_fanout_preserve_existing_layout_mapping_and_profiles": True,
            "reasoning_hotspot_uses_existing_q4_observation_only_not_a_selected_service_rate": True,
            "no_pruning_fifo_ownership_order_commit_or_scheduler_changed": True,
            "no_model_runtime_profiler_or_hardware_parameter_loaded": True,
            "no_hardware_bank_sram_port_queue_cycle_timing_performance_or_architecture_claim": True,
        },
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a490_eager_rmw_envelope_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"A4.9.0 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} "
        f"rows={len(temporary_rows)} persistent_joint_safe_refs={len(persistent_joint_safe)}"
    )


if __name__ == "__main__":
    main()
