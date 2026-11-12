#!/usr/bin/env python3
"""A4.9.2 bounded whole-bank versus record-granular execution replay.

This is a no-model, no-RTL sensitivity.  It preserves the immutable A4.7.1
transaction stream, its predecessor/FIFO order, and its sole external commit
boundary.  The record-granular variant may interleave *internal* modeled
storage-object micro-operations, but no member publishes state or releases a
dependent transaction before its enclosing transaction commits.
"""
from __future__ import annotations

from kvpress.research.metadata import (record_summarize as summarize, MicroOp, ActiveMicroOp, micro_op_duration, build_micro_ops, whole_bank_queue_observations, record_granular_replay)

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a4720_metadata_storage_sufficiency import SCHEMA as A4720_SCHEMA
from tools.analyze_kvzap_route_a4721_metadata_physical_dse import bank_index, lower_transaction
from tools.analyze_kvzap_route_a480_commit_aware_backlog import (
    ScheduledTransaction, dependency_predecessors, iter_contexts,
    make_scheduled_transactions,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash
from tools.simulate_kvzap_route_a491_candidate_metadata_engine import (
    A490_SCHEMA, CANDIDATES, LAYOUT, SCHEMA as A491_SCHEMA, replay as replay_whole_bank,
)

SCHEMA = "kvzap-route-a492-record-granular-engine-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.9.2 declared whole-bank versus record-granular internal execution "
            "replay. Abstract cycles are not hardware timing or RTL evidence."
        )
    )
    parser.add_argument("--a468220-trace", type=Path, required=True)
    parser.add_argument("--a471-trace", type=Path, required=True)
    parser.add_argument("--a4720-report", type=Path, required=True)
    parser.add_argument("--a4721-report", type=Path, required=True)
    parser.add_argument("--a490-report", type=Path, required=True)
    parser.add_argument("--a491-report", type=Path, required=True)
    parser.add_argument("--post-trace-cycle-limit", type=int, default=4096,
                        help="Declared abstract drain bound, not latency.")
    parser.add_argument("--preflight-only", action="store_true",
                        help="Validate the complete immutable predecessor chain without output.")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Previously absent output directory only.")
    return parser.parse_args()




def context_id(key: tuple[str, str, int, str]) -> tuple[str, str, int, str]:
    return (str(key[0]), str(key[1]), int(key[2]), str(key[3]))


def candidate_id(candidate: dict[str, Any]) -> str:
    return str(candidate["name"])


def validate(args: argparse.Namespace) -> dict[str, Any]:
    a490 = read_completed(args.a490_report, A490_SCHEMA, "A4.9.0 _03")
    a491 = read_completed(args.a491_report, A491_SCHEMA, "A4.9.1 _02")
    a4720 = read_completed(args.a4720_report, A4720_SCHEMA, "A4.7.2.0")
    if not all(a490.get("envelope_exit_observation", {}).values()):
        raise ValueError("A4.9.0 exit is incomplete")
    expected = {
        "a468220_trace_sha256": sha256_file(args.a468220_trace),
        "a471_trace_sha256": sha256_file(args.a471_trace),
        "a4720_report_sha256": sha256_file(args.a4720_report),
        "a4721_report_sha256": sha256_file(args.a4721_report),
        "a490_report_sha256": sha256_file(args.a490_report),
    }
    if a491.get("input_artifacts") != expected:
        raise ValueError("A4.9.1 _02 input hash chain mismatch")
    if a490.get("input_artifacts", {}).get("a468220_trace_sha256") != expected["a468220_trace_sha256"]:
        raise ValueError("A4.9.0 record trace hash mismatch")
    if a490.get("input_artifacts", {}).get("a471_trace_sha256") != expected["a471_trace_sha256"]:
        raise ValueError("A4.9.0 transaction trace hash mismatch")
    if a490.get("input_artifacts", {}).get("a4720_report_sha256") != expected["a4720_report_sha256"]:
        raise ValueError("A4.9.0 field-width report hash mismatch")
    if a490.get("input_artifacts", {}).get("a4721_report_sha256") != expected["a4721_report_sha256"]:
        raise ValueError("A4.9.0 physical-DSE report hash mismatch")
    required = (
        "a490_exit_and_hash_chain_validated",
        "joint_safe_field_widths_fit_every_declared_word_padded_modeled_object",
        "fifo_ownership_and_commit_predecessors_reused_unchanged",
        "candidate_queue_overflow_is_observed_never_dropped",
        "no_model_or_pruning_path_loaded",
        "no_hardware_measurement_claim",
    )
    if not all(a491.get("semantic_guards", {}).get(name) is True for name in required):
        raise ValueError("A4.9.1 semantic guards incomplete")
    if a491.get("config", {}).get("fixed_layout") != LAYOUT:
        raise ValueError("A4.9.1 fixed layout changed")
    if a491.get("config", {}).get("candidates") != list(CANDIDATES):
        raise ValueError("A4.9.1 candidate catalog changed")
    if args.post_trace_cycle_limit < 0:
        raise ValueError("post-trace cycle limit must be nonnegative")
    return {"a490": a490, "a491": a491, "a4720": a4720, "input_hashes": expected}














def prior_rows(report: dict[str, Any]) -> dict[tuple[tuple[str, str, int, str], str], dict[str, Any]]:
    rows: dict[tuple[tuple[str, str, int, str], str], dict[str, Any]] = {}
    for row in report.get("candidate_context_rows", []):
        key = (str(row["anchor"]), str(row["workload"]), int(row["evaluation_horizon_append_opportunities"]), str(row["organization_label"]))
        marker = (key, candidate_id(row["candidate"]))
        if marker in rows:
            raise AssertionError("duplicate A4.9.1 context/candidate row")
        rows[marker] = row["result"]
    if not rows:
        raise AssertionError("A4.9.1 report has no candidate rows")
    return rows


def main() -> None:
    args = parse_args()
    validated = validate(args)
    if args.preflight_only:
        print("A4.9.2 preflight passed: A4.9.0/A4.9.1 immutable hash chain and candidate catalog validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    expected = prior_rows(validated["a491"])
    rows: list[dict[str, Any]] = []
    observed: set[tuple[tuple[str, str, int, str], str]] = set()
    for key, record_ops, groups in iter_contexts(args.a468220_trace, args.a471_trace):
        predecessors, _ = dependency_predecessors(record_ops, groups)
        for candidate in CANDIDATES:
            profile = {"layout": LAYOUT, "bank_count": candidate["banks"], "bank_mapping": candidate["mapping"]}
            transactions, opportunities = make_scheduled_transactions(groups, predecessors, profile)
            baseline = replay_whole_bank(transactions, opportunities, candidate, args.post_trace_cycle_limit)
            marker = (context_id(key), candidate_id(candidate))
            if baseline != expected.get(marker):
                raise AssertionError(f"A4.9.1 baseline reproduction mismatch: {marker}")
            members = build_micro_ops(groups, transactions, candidate)
            granular = record_granular_replay(transactions, opportunities, members, candidate, args.post_trace_cycle_limit)
            whole_queue = whole_bank_queue_observations(transactions, opportunities, candidate, args.post_trace_cycle_limit)
            rows.append({
                "anchor": key[0], "workload": key[1], "evaluation_horizon_append_opportunities": key[2], "organization_label": key[3],
                "candidate": candidate,
                "whole_bank_a491_baseline": {"result": baseline, **whole_queue},
                "record_granular_internal_execution": granular,
                "comparison": {
                    "cmin_abstract_cycles_delta_record_granular_minus_whole_bank": granular["abstract_cycles_elapsed"] - baseline["abstract_cycles_elapsed"],
                    "both_execution_models_drained_within_declared_bound": bool(baseline["drained_within_declared_bound"] and granular["drained_within_declared_bound"]),
                    "comparison_boundary": "Cmin is a declared replay coordinate only; it is not calibrated latency, throughput, or a hardware selection.",
                },
            })
            observed.add(marker)
    if set(expected) != observed:
        raise AssertionError("A4.9.2 context/candidate coverage differs from A4.9.1 _02")
    config = {
        "fixed_layout": LAYOUT, "candidates": CANDIDATES,
        "whole_bank_baseline": "A4.9.1 exact conservative all-touched-bank reservation replay.",
        "record_granular_variant": "Only modeled storage-object micro-ops inside one immutable transaction may interleave. No micro-op independently publishes state or releases FIFO/ownership/oldest/dependency state.",
        "rmw_rule": "An existing eager RMW remains one RMW micro-op with the unchanged declared two-abstract-cycle RMW-lane service; it is not expanded to read plus write.",
        "cross_bank_commit_rule": "Only candidates with the existing nonzero commit_slots field model one abstract commit-coordination slot at final multi-bank group commit; it is not held during internal member execution.",
        "queue_rule": "Queue occupancy counts not-yet-started transaction groups touching a bank; active/incomplete groups are reported separately through active micro-op concurrency.",
        "boundary": "All resources and abstract cycles are declared execution-model quantities, not hardware timing, FIFO depth, SRAM ports, throughput, traffic, energy, area, architecture specification, or RTL evidence.",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(),
        "input_artifacts": {**validated["input_hashes"], "a491_report_sha256": sha256_file(args.a491_report)},
        "config": config, "config_hash": stable_hash(config),
        "semantic_guards": {
            "a491_hash_chain_candidate_catalog_and_exact_baseline_reproduction_validated": True,
            "immutable_transaction_groups_predecessors_fifo_and_single_commit_boundary_unchanged": True,
            "record_granular_interleaving_is_internal_and_all_external_publication_is_commit_gated": True,
            "same_record_lock_is_explicit_and_released_only_at_group_commit": True,
            "intrinsic_same_record_bank_port_rmw_lane_and_cross_bank_commit_blockers_separated": True,
            "queue_overflow_is_observed_never_dropped": True,
            "no_model_default_pruning_path_or_hardware_measurement_loaded": True,
            "no_third_execution_granularity_or_semantic_variant_introduced": True,
        },
        "candidate_context_rows": rows,
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a492_record_granular_engine_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.9.2 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} rows={len(rows)}")


if __name__ == "__main__":
    main()
