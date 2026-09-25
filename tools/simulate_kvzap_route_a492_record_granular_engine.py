#!/usr/bin/env python3
"""A4.9.2 bounded whole-bank versus record-granular execution replay.

This is a no-model, no-RTL sensitivity.  It preserves the immutable A4.7.1
transaction stream, its predecessor/FIFO order, and its sole external commit
boundary.  The record-granular variant may interleave *internal* modeled
storage-object micro-operations, but no member publishes state or releases a
dependent transaction before its enclosing transaction commits.
"""
from __future__ import annotations

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


def summarize(values: list[int]) -> dict[str, int]:
    if not values:
        return {"count": 0, "min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "sum": 0}
    ordered = sorted(values)
    def at(fraction: float) -> int:
        return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]
    return {"count": len(ordered), "min": ordered[0], "p50": at(.50), "p95": at(.95),
            "p99": at(.99), "max": ordered[-1], "sum": sum(ordered)}


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


@dataclass(frozen=True)
class MicroOp:
    transaction_index: int
    object_key: tuple[str, tuple[Any, ...]]
    bank: int
    operation: str


@dataclass(frozen=True)
class ActiveMicroOp:
    finish_tick: int
    micro_op: MicroOp


def micro_op_duration(operation: str) -> int:
    if operation in {"read", "write"}:
        return 1
    if operation == "rmw":
        return 2
    raise ValueError(f"undeclared modeled operation: {operation}")


def build_micro_ops(groups: list[dict[str, Any]], transactions: list[ScheduledTransaction], candidate: dict[str, Any]) -> dict[int, tuple[MicroOp, ...]]:
    """Lower one immutable group to one member micro-op per modeled object."""
    if len(groups) != len(transactions):
        raise AssertionError("immutable group/transaction cardinality mismatch")
    result: dict[int, tuple[MicroOp, ...]] = {}
    for index, (group, transaction) in enumerate(zip(groups, transactions)):
        if transaction.index != index:
            raise AssertionError("transaction index diverged from immutable group order")
        lowered = lower_transaction(group, LAYOUT)
        members = tuple(sorted((
            MicroOp(
                transaction_index=index,
                object_key=object_key,
                bank=bank_index(str(candidate["mapping"]), int(candidate["banks"]), object_key,
                                layer=int(group["layer"]), head=int(group["kv_head"])),
                operation=operation,
            )
            for object_key, operation in lowered.items()
        ), key=lambda item: repr(item.object_key)))
        if len({member.object_key for member in members}) != len(members):
            raise AssertionError("one transaction contains duplicate modeled-object micro-ops")
        demand = Counter((member.bank, member.operation) for member in members)
        if demand != transaction.demands or frozenset(member.bank for member in members) != transaction.banks:
            raise AssertionError("record micro-op lowering does not exactly reproduce A4.9.1 demand")
        result[index] = members
    return result


def whole_bank_queue_observations(transactions: list[ScheduledTransaction], opportunities: list[tuple[str, int]], candidate: dict[str, Any], drain_limit: int) -> dict[str, Any]:
    """Instrument the unchanged A4.9.1 algorithm without altering its result."""
    arrivals: dict[int, list[ScheduledTransaction]] = defaultdict(list)
    for transaction in transactions:
        arrivals[transaction.arrival_ordinal].append(transaction)
    pending: list[ScheduledTransaction] = []
    committed: set[int] = set()
    active: list[tuple[int, ScheduledTransaction]] = []
    bank_until = [0] * int(candidate["banks"])
    coordinator_until = 0
    peak_by_bank = [0] * int(candidate["banks"])
    tick = 0
    last_arrival = len(opportunities) - 1
    while tick <= last_arrival or pending or active:
        if tick > last_arrival + drain_limit:
            break
        pending.extend(arrivals.get(tick, []))
        finished = [item for item in active if item[0] <= tick]
        active = [item for item in active if item[0] > tick]
        committed.update(transaction.index for _, transaction in finished)
        queued = Counter(bank for transaction in pending for bank in transaction.banks)
        for bank in range(int(candidate["banks"])):
            peak_by_bank[bank] = max(peak_by_bank[bank], queued[bank])
        retained: list[ScheduledTransaction] = []
        for transaction in pending:
            if any(parent not in committed for parent in transaction.predecessors):
                retained.append(transaction); continue
            if any(bank_until[bank] > tick for bank in transaction.banks):
                retained.append(transaction); continue
            if len(transaction.banks) > 1 and candidate["commit_slots"] and coordinator_until > tick:
                retained.append(transaction); continue
            reads = sum(value for (_, operation), value in transaction.demands.items() if operation == "read")
            writes = sum(value for (_, operation), value in transaction.demands.items() if operation == "write")
            rmw = sum(value for (_, operation), value in transaction.demands.items() if operation == "rmw")
            duration = max(
                (reads + candidate["read_ports"] - 1) // candidate["read_ports"],
                (writes + candidate["write_ports"] - 1) // candidate["write_ports"],
                2 * ((rmw + candidate["rmw_lanes"] - 1) // candidate["rmw_lanes"]), 1,
            ) + (1 if len(transaction.banks) > 1 else 0)
            for bank in transaction.banks:
                bank_until[bank] = tick + duration
            if len(transaction.banks) > 1 and candidate["commit_slots"]:
                coordinator_until = tick + duration
            active.append((tick + duration, transaction))
        pending = retained
        tick += 1
    return {
        "peak_queued_transaction_groups_per_bank": summarize(peak_by_bank),
        "queue_occupancy_definition": "A4.9.1 pending transaction groups touching each modeled bank immediately before unchanged whole-bank selection; active groups are excluded.",
    }


def record_granular_replay(transactions: list[ScheduledTransaction], opportunities: list[tuple[str, int]], micro_ops: dict[int, tuple[MicroOp, ...]], candidate: dict[str, Any], drain_limit: int) -> dict[str, Any]:
    """Interleave only micro-ops; all semantic publication remains at group commit."""
    arrivals: dict[int, list[int]] = defaultdict(list)
    for transaction in transactions:
        arrivals[transaction.arrival_ordinal].append(transaction.index)
    pending: list[int] = []
    committed: set[int] = set()
    completed_members: dict[int, set[MicroOp]] = defaultdict(set)
    started_members: dict[int, set[MicroOp]] = defaultdict(set)
    locks: dict[tuple[str, tuple[Any, ...]], int] = {}
    active: list[ActiveMicroOp] = []
    transaction_first_start: dict[int, int] = {}
    transaction_commit_tick: dict[int, int] = {}
    reasons: Counter[str] = Counter()
    peak_queue_by_bank = [0] * int(candidate["banks"])
    active_samples: list[int] = []
    coordinator_until = 0
    tick = 0
    last_arrival = len(opportunities) - 1
    while tick <= last_arrival or pending or active:
        if tick > last_arrival + drain_limit:
            break
        pending.extend(arrivals.get(tick, []))
        finished = [item for item in active if item.finish_tick <= tick]
        active = [item for item in active if item.finish_tick > tick]
        for item in finished:
            completed_members[item.micro_op.transaction_index].add(item.micro_op)
        # Commit is the sole visibility/release point.  Stable immutable order is
        # retained even when internal members completed in a different order.
        for index in list(pending):
            transaction = transactions[index]
            if any(parent not in committed for parent in transaction.predecessors):
                continue
            if len(completed_members[index]) != len(micro_ops[index]):
                continue
            cross_bank = len(transaction.banks) > 1
            if cross_bank and candidate["commit_slots"] and coordinator_until > tick:
                reasons["cross_bank_commit_coordination"] += 1
                continue
            if cross_bank and candidate["commit_slots"]:
                coordinator_until = tick + 1
            pending.remove(index)
            committed.add(index)
            transaction_commit_tick[index] = tick
            for member in micro_ops[index]:
                if locks.get(member.object_key) != index:
                    raise AssertionError("transaction committed without owning every member lock")
                del locks[member.object_key]
        # This is the same per-bank *queued transaction group* definition used
        # above for A4.9.1: a group leaves the queue on its first internal start.
        queued = Counter(
            bank for index in pending if not started_members[index]
            for bank in transactions[index].banks
        )
        for bank in range(int(candidate["banks"])):
            peak_queue_by_bank[bank] = max(peak_queue_by_bank[bank], queued[bank])
        active_by_resource = Counter((item.micro_op.bank, item.micro_op.operation) for item in active)
        for index in pending:
            transaction = transactions[index]
            if any(parent not in committed for parent in transaction.predecessors):
                reasons["intrinsic_dependency"] += 1
                continue
            for member in micro_ops[index]:
                if member in started_members[index]:
                    continue
                lock_owner = locks.get(member.object_key)
                if lock_owner is not None and lock_owner != index:
                    reasons["same_record_lock"] += 1
                    continue
                limit_name = {"read": "read_ports", "write": "write_ports", "rmw": "rmw_lanes"}[member.operation]
                if active_by_resource[(member.bank, member.operation)] >= int(candidate[limit_name]):
                    reasons[f"bank_{member.operation}_port" if member.operation != "rmw" else "rmw_lane"] += 1
                    continue
                locks[member.object_key] = index
                started_members[index].add(member)
                transaction_first_start.setdefault(index, tick)
                active.append(ActiveMicroOp(tick + micro_op_duration(member.operation), member))
                active_by_resource[(member.bank, member.operation)] += 1
        active_samples.append(len(active))
        tick += 1
    first_start_delays = [transaction_first_start[index] - transaction.arrival_ordinal for index, transaction in enumerate(transactions) if index in transaction_first_start]
    commit_delays = [transaction_commit_tick[index] - transaction.arrival_ordinal for index, transaction in enumerate(transactions) if index in transaction_commit_tick]
    if any(index in committed and any(parent not in committed or transaction_commit_tick[parent] > transaction_commit_tick[index] for parent in transaction.predecessors) for index, transaction in enumerate(transactions)):
        raise AssertionError("a transaction committed before an intrinsic predecessor commit")
    if committed and locks:
        raise AssertionError("committed transaction left a same-record lock behind")
    return {
        "completed": len(committed), "total": len(transactions),
        "drained_within_declared_bound": len(committed) == len(transactions),
        "abstract_cycles_elapsed": tick,
        "transaction_first_micro_op_delay_abstract_cycles": summarize(first_start_delays),
        "transaction_commit_delay_abstract_cycles": summarize(commit_delays),
        "peak_queued_transaction_groups_per_bank": summarize(peak_queue_by_bank),
        "queue_overflow_groups_observed": max(0, max(peak_queue_by_bank, default=0) - int(candidate["queue_groups_per_bank"])),
        "active_micro_op_concurrency": summarize(active_samples),
        "blocking_observation_counts": {name: reasons[name] for name in (
            "intrinsic_dependency", "same_record_lock", "bank_read_port", "bank_write_port", "rmw_lane", "cross_bank_commit_coordination",
        )},
        "execution_boundary": "Micro-ops may interleave only inside immutable A4.7.1 transaction groups. Every member remains externally invisible until the sole existing group commit; FIFO/ownership/oldest release and all dependencies are commit-gated. Abstract cycles/resources are declared model coordinates, not hardware timing or implementation evidence.",
    }


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
