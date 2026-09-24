#!/usr/bin/env python3
"""A4.8.0 no-model, causal commit-aware metadata-backlog replay.

This stage consumes immutable Route-A semantic transaction groups.  It keeps
their FIFO-derived order, preregistered A4.7.0 dependency edges, and A4.7.1
commit boundaries unchanged while comparing an unbounded direct-commit
reference with one simple counter-only elastic abstract-service policy.

All opportunities, service quanta, waits, and delays are logical model
coordinates.  They are deliberately not hardware transactions, banks, ports,
cycles, bandwidth, timing, latency, throughput, energy, area, or an
architecture selection.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path
from typing import Any, Iterable

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a468220_metadata_recordization import TRACE_SCHEMA as RECORD_TRACE_SCHEMA
from tools.analyze_kvzap_route_a470_metadata_access_concurrency import SCHEMA as A470_SCHEMA, dependencies
from tools.analyze_kvzap_route_a471_metadata_transaction_contract import SCHEMA as A471_SCHEMA, TRANSACTION_TRACE_SCHEMA
from tools.analyze_kvzap_route_a4720_metadata_storage_sufficiency import SCHEMA as A4720_SCHEMA, context_key
from tools.analyze_kvzap_route_a4721_metadata_physical_dse import SCHEMA as A4721_SCHEMA, bank_index, lower_transaction
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a480-commit-aware-backlog-1.0"
PHASES = ("activation", "steady_state_append", "steady_state_dequeue")
POST_TRACE_DRAIN_PHASE = "post_trace_drain"
DEPENDENCY_CURVE = "strict_same_record"

# These two profiles are intentionally a small, predeclared sensitivity pair:
# they hold the modeled object layout and count constant and vary only the
# A4.7.2.1 mapping function.  They do not select a physical implementation.
CANDIDATE_PROFILES = (
    {"profile": "both_colocated_b8_head_affine", "layout": "both_colocated_direct_v1", "bank_count": 8, "bank_mapping": "head_affine_v1"},
    {"profile": "both_colocated_b8_object_striped", "layout": "both_colocated_direct_v1", "bank_count": 8, "bank_mapping": "object_identity_striped_v1"},
)
SERVICE_LEVELS = (("minimum", 1), ("medium", 2), ("high", 4))
CONTROLLER_THRESHOLDS = {
    "medium": {"layer_backlog": 128, "head_backlog": 16, "age": 4},
    "high": {"layer_backlog": 512, "head_backlog": 64, "age": 16},
    "deescalate": {"layer_backlog": 32, "head_backlog": 4, "age": 1, "consecutive_low_opportunities": 2},
}
DEFAULT_POST_TRACE_DRAIN_LIMIT = 512
BLOCKING_CAUSES = (
    "intrinsic_transaction_dependency",
    "rmw_service_shortage",
    "cross_bank_atomic_commit_waiting",
    "same_bank_service_shortage",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.8.0 no-model causal commit-aware transaction-backlog replay. Logical opportunities and abstract service quanta are not hardware timing, ports, or performance."
    )
    parser.add_argument("--a468220-trace", type=Path, required=True, help="Immutable A4.6.8.2.2.0 record trace required to reconstruct preregistered A4.7.0 dependencies.")
    parser.add_argument("--a470-report", type=Path, required=True)
    parser.add_argument("--a471-report", type=Path, required=True)
    parser.add_argument("--a471-trace", type=Path, required=True)
    parser.add_argument("--a4720-report", type=Path, required=True)
    parser.add_argument("--a4721-report", type=Path, required=True, help="Only the corrected A4.7.2.1 schema-1.2 report is accepted.")
    parser.add_argument("--post-trace-drain-limit", type=int, default=DEFAULT_POST_TRACE_DRAIN_LIMIT, help="Maximum synthetic no-arrival logical drain opportunities. This is an observation bound, not a controller input or timing bound.")
    parser.add_argument("--preflight-only", action="store_true", help="Validate all hash-bound predecessor contracts without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def distribution(values: Iterable[int]) -> dict[str, int | None]:
    items = sorted(values)

    def percentile(fraction: float) -> int | None:
        return items[int((len(items) - 1) * fraction)] if items else None

    return {
        "count": len(items), "min": min(items) if items else None,
        "p50": percentile(.50), "p95": percentile(.95), "p99": percentile(.99),
        "max": max(items) if items else None, "sum": sum(items),
    }


def longest_run(values: Iterable[bool]) -> int:
    best = current = 0
    for value in values:
        current = current + 1 if value else 0
        best = max(best, current)
    return best


def phase_local_ordinals(groups: list[dict[str, Any]]) -> dict[tuple[str, int], int]:
    per_phase: dict[str, set[int]] = defaultdict(set)
    for group in groups:
        per_phase[str(group["phase"])].add(int(group["logical_checkpoint"]))
    return {(phase, checkpoint): index for phase, checkpoints in per_phase.items() for index, checkpoint in enumerate(sorted(checkpoints))}


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    a470 = read_completed(args.a470_report, A470_SCHEMA, "A4.7.0 _02")
    a471 = read_completed(args.a471_report, A471_SCHEMA, "A4.7.1")
    a4720 = read_completed(args.a4720_report, A4720_SCHEMA, "A4.7.2.0")
    a4721 = read_completed(args.a4721_report, A4721_SCHEMA, "A4.7.2.1 _03")
    record_sha, transaction_sha = sha256_file(args.a468220_trace), sha256_file(args.a471_trace)
    if a471.get("transaction_trace", {}).get("schema_version") != TRANSACTION_TRACE_SCHEMA or a471["transaction_trace"].get("sha256") != transaction_sha:
        raise ValueError("A4.7.1 transaction trace hash/schema mismatch")
    if a471.get("input_artifacts", {}).get("a468220_trace_sha256") != record_sha:
        raise ValueError("A4.7.1 does not bind supplied A4.6.8.2.2.0 record trace")
    if a470.get("input_artifacts", {}).get("a468220_trace_sha256") != record_sha:
        raise ValueError("A4.7.0 does not bind supplied A4.6.8.2.2.0 record trace")
    expected_4721 = {
        "a470_report_sha256": sha256_file(args.a470_report),
        "a471_report_sha256": sha256_file(args.a471_report),
        "a471_trace_sha256": transaction_sha,
        "a4720_report_sha256": sha256_file(args.a4720_report),
    }
    if a4721.get("input_artifacts") != expected_4721:
        raise ValueError("A4.7.2.1 _03 predecessor hash chain mismatch")
    required_470 = (
        "only_four_preregistered_dependency_edge_types_emitted",
        "fixed_record_trace_fifo_grants_source_and_order_not_rescheduled",
        "critical_path_and_parallel_work_defined_in_logical_work_only",
    )
    required_471 = (
        "every_dependency_node_maps_to_exactly_one_transaction_group",
        "every_group_has_read_write_rmw_release_sets_and_one_commit_boundary",
        "post_commit_span_owner_source_queue_and_oldest_replay_consistent",
        "semantic_atomicity_explicitly_not_hardware_atomicity",
    )
    required_4720 = (
        "four_semantic_record_types_fixed_and_all_retained",
        "a471_transaction_sets_and_commit_boundaries_not_changed",
        "every_semantic_record_maps_to_declared_modeled_storage_object",
        "no_silent_field_or_namespace_overflow",
    )
    required_4721 = (
        "complete_a470_a471_a4720_hash_bound_chain_validated",
        "only_a4720_sufficient_layouts_and_width_profiles_consumed",
        "a471_transaction_sets_commit_boundaries_and_order_unchanged",
        "phase_local_opportunity_saturation_streaks_reported",
        "intrinsic_dependency_not_recomputed_or_conflated_with_modeled_physical_contention",
    )
    for report, required, name in ((a470, required_470, "A4.7.0"), (a471, required_471, "A4.7.1"), (a4720, required_4720, "A4.7.2.0"), (a4721, required_4721, "A4.7.2.1 _03")):
        if not all(report.get("semantic_guards", {}).get(item) is True for item in required):
            raise ValueError(f"{name} semantic guards incomplete")
    available_layouts = {str(row["layout"]) for row in a4721.get("static_candidate_rows", [])}
    if not {profile["layout"] for profile in CANDIDATE_PROFILES} <= available_layouts:
        raise ValueError("A4.8.0 candidate layout is not A4.7.2.1 _03 sufficient")
    if args.post_trace_drain_limit < 0:
        raise ValueError("post-trace drain limit must be non-negative")
    return a470, a471, a4720, a4721


@dataclass(frozen=True)
class ScheduledTransaction:
    index: int
    phase: str
    checkpoint: int
    layer: int
    head: int
    arrival_ordinal: int
    predecessors: frozenset[int]
    demands: Counter[tuple[int, str]]
    banks: frozenset[int]


def dependency_predecessors(record_ops: list[dict[str, Any]], groups: list[dict[str, Any]]) -> tuple[dict[int, set[int]], dict[str, int]]:
    """Lift A4.7.0 edges and retain A4.7.1's already-fixed per-head FIFO order.

    The FIFO predecessor is not a fifth A4.7.0 edge type. It is the existing
    A4.7.1 transaction serialization rule needed to prevent a later group of
    one head from committing before that head's earlier group.
    """
    nodes, _ = dependencies(record_ops, DEPENDENCY_CURVE)
    if len(nodes) != len(record_ops):
        raise AssertionError("A4.7.0 dependency reconstruction length mismatch")
    node_to_group: dict[int, int] = {}
    for group_index, group in enumerate(groups):
        for node_index in group["member_record_node_indices"]:
            node_index = int(node_index)
            if node_index in node_to_group:
                raise AssertionError("dependency node maps to multiple transaction groups")
            node_to_group[node_index] = group_index
    if set(node_to_group) != set(range(len(record_ops))):
        raise AssertionError("transaction groups do not cover every fixed dependency node")
    result: dict[int, set[int]] = {index: set() for index in range(len(groups))}
    edge_source_counts: Counter[str] = Counter()
    for node in nodes:
        current = node_to_group[int(node["index"])]
        for edge_type, parent_node in node["edges"]:
            if edge_type not in {"same-record", "same-head-control", "span-lifecycle", "ownership-order"}:
                raise AssertionError("unregistered A4.7.0 dependency edge")
            parent = node_to_group[int(parent_node)]
            if parent != current:
                before = len(result[current]); result[current].add(parent)
                if len(result[current]) != before:
                    edge_source_counts[f"a470_{edge_type}"] += 1
    previous_by_head: dict[tuple[int, int], int] = {}
    for current, group in enumerate(groups):
        head_key = (int(group["layer"]), int(group["kv_head"]))
        if head_key in previous_by_head:
            parent = previous_by_head[head_key]
            before = len(result[current]); result[current].add(parent)
            if len(result[current]) != before:
                edge_source_counts["a471_fixed_per_head_fifo_order"] += 1
        previous_by_head[head_key] = current
    if any(parent >= current for current, parents in result.items() for parent in parents):
        raise AssertionError("dependency edges must remain acyclic in immutable transaction order")
    return result, dict(edge_source_counts)


def make_scheduled_transactions(groups: list[dict[str, Any]], predecessors: dict[int, set[int]], profile: dict[str, Any]) -> tuple[list[ScheduledTransaction], list[tuple[str, int]]]:
    ordinals = phase_local_ordinals(groups)
    opportunities: list[tuple[str, int]] = []
    seen_opportunities: set[tuple[str, int]] = set()
    previous: tuple[str, int] | None = None
    transactions = []
    for index, group in enumerate(groups):
        phase, checkpoint = str(group["phase"]), int(group["logical_checkpoint"])
        if phase not in PHASES:
            raise ValueError("undeclared A4.7.1 phase")
        opportunity = (phase, checkpoint)
        if opportunity != previous:
            if opportunity in seen_opportunities:
                raise AssertionError("immutable transaction trace reopens a closed opportunity")
            opportunities.append(opportunity); seen_opportunities.add(opportunity); previous = opportunity
        lowered = lower_transaction(group, str(profile["layout"]))
        demands: Counter[tuple[int, str]] = Counter()
        banks: set[int] = set()
        for object_key, operation in lowered.items():
            bank = bank_index(str(profile["bank_mapping"]), int(profile["bank_count"]), object_key, layer=int(group["layer"]), head=int(group["kv_head"]))
            demands[(bank, operation)] += 1; banks.add(bank)
        if not demands:
            raise AssertionError("transaction has no lowered modeled work")
        transactions.append(ScheduledTransaction(
            index=index, phase=phase, checkpoint=checkpoint, layer=int(group["layer"]), head=int(group["kv_head"]),
            arrival_ordinal=len(opportunities) - 1, predecessors=frozenset(predecessors[index]), demands=demands, banks=frozenset(banks),
        ))
    # `arrival_ordinal` is a continuous immutable trace/replay coordinate.
    # Phase-local ordinals remain provenance in the predecessor report and are
    # intentionally not converted to a time coordinate here.
    if not ordinals:
        raise AssertionError("transaction trace has no phase-local opportunities")
    return transactions, opportunities


class CausalController:
    """Fixed global counter-only controller; it cannot see identity or future."""
    def __init__(self) -> None:
        self.level_index = 0
        self.low_pressure_run = 0
        self.escalations = 0
        self.deescalations = 0

    def choose(self, *, layer_backlog: int, head_backlog: int, age_max: int) -> tuple[str, int, str]:
        high = (layer_backlog >= CONTROLLER_THRESHOLDS["high"]["layer_backlog"] or head_backlog >= CONTROLLER_THRESHOLDS["high"]["head_backlog"] or age_max >= CONTROLLER_THRESHOLDS["high"]["age"])
        medium = (layer_backlog >= CONTROLLER_THRESHOLDS["medium"]["layer_backlog"] or head_backlog >= CONTROLLER_THRESHOLDS["medium"]["head_backlog"] or age_max >= CONTROLLER_THRESHOLDS["medium"]["age"])
        desired = 2 if high else 1 if medium else 0
        if desired > self.level_index:
            old = self.level_index; self.level_index = desired; self.low_pressure_run = 0
            self.escalations += self.level_index - old
            transition = f"escalate_{SERVICE_LEVELS[old][0]}_to_{SERVICE_LEVELS[self.level_index][0]}"
        elif desired < self.level_index:
            low = (layer_backlog <= CONTROLLER_THRESHOLDS["deescalate"]["layer_backlog"] and head_backlog <= CONTROLLER_THRESHOLDS["deescalate"]["head_backlog"] and age_max <= CONTROLLER_THRESHOLDS["deescalate"]["age"])
            self.low_pressure_run = self.low_pressure_run + 1 if low else 0
            if self.low_pressure_run >= CONTROLLER_THRESHOLDS["deescalate"]["consecutive_low_opportunities"]:
                old = self.level_index; self.level_index -= 1; self.low_pressure_run = 0; self.deescalations += 1
                transition = f"deescalate_{SERVICE_LEVELS[old][0]}_to_{SERVICE_LEVELS[self.level_index][0]}"
            else:
                transition = "hold_hysteresis"
        else:
            self.low_pressure_run = 0; transition = "hold"
        return SERVICE_LEVELS[self.level_index][0], SERVICE_LEVELS[self.level_index][1], transition


def backlog_observables(backlog: list[int], transactions: list[ScheduledTransaction], opportunity_ordinal: int) -> tuple[int, int, int]:
    by_layer: Counter[int] = Counter(); by_head: Counter[tuple[int, int]] = Counter(); ages = []
    for index in backlog:
        transaction = transactions[index]
        by_layer[transaction.layer] += 1; by_head[(transaction.layer, transaction.head)] += 1
        ages.append(opportunity_ordinal - transaction.arrival_ordinal)
    return max(by_layer.values(), default=0), max(by_head.values(), default=0), max(ages, default=0)


def blocking_cause(transaction: ScheduledTransaction, committed: set[int], remaining: Counter[tuple[int, str]] | None) -> str | None:
    if any(parent not in committed for parent in transaction.predecessors):
        return "intrinsic_transaction_dependency"
    if remaining is None:
        return None
    insufficient = {key for key, demand in transaction.demands.items() if remaining[key] < demand}
    if not insufficient:
        return None
    if any(operation == "rmw" for _, operation in insufficient):
        return "rmw_service_shortage"
    if len(transaction.banks) > 1:
        return "cross_bank_atomic_commit_waiting"
    return "same_bank_service_shortage"


def service_backlog(
    *, transactions: list[ScheduledTransaction], opportunities: list[tuple[str, int]], policy: str, post_trace_drain_limit: int,
) -> dict[str, Any]:
    """Commit in immutable transaction order; no semantic or FIFO reordering."""
    if policy not in {"direct_unconstrained_commit", "causal_elastic_v1"}:
        raise ValueError("unknown A4.8.0 policy")
    controller = CausalController() if policy == "causal_elastic_v1" else None
    arrivals: dict[int, list[int]] = defaultdict(list)
    for transaction in transactions:
        arrivals[transaction.arrival_ordinal].append(transaction.index)
    backlog: list[int] = []
    committed: set[int] = set(); commit_ordinal: dict[int, int] = {}
    opportunity_rows: list[dict[str, Any]] = []
    max_ordinal = len(opportunities) - 1
    ordinal = 0
    while ordinal <= max_ordinal or (backlog and ordinal <= max_ordinal + post_trace_drain_limit):
        trace_opportunity = ordinal <= max_ordinal
        phase, checkpoint = opportunities[ordinal] if trace_opportunity else (POST_TRACE_DRAIN_PHASE, ordinal - max_ordinal)
        new = list(arrivals.get(ordinal, [])) if trace_opportunity else []
        backlog.extend(new)
        pre_service_backlog = len(backlog)
        layer_backlog, head_backlog, age_max = backlog_observables(backlog, transactions, ordinal)
        if controller is None:
            level, quantum, transition = "direct_unconstrained", None, "direct_reference"
            remaining = None
        else:
            level, quantum, transition = controller.choose(layer_backlog=layer_backlog, head_backlog=head_backlog, age_max=age_max)
            remaining = Counter({(bank, operation): quantum for bank in range(8) for operation in ("read", "write", "rmw")})
        committed_this_op: list[int] = []
        remaining_backlog: list[int] = []
        # Every lifted predecessor has a lower immutable transaction index.
        # One stable-order pass therefore exposes all dependency-ready work
        # without admitting a scheduler reordering policy.
        for index in backlog:
            transaction = transactions[index]
            if blocking_cause(transaction, committed, remaining) is not None:
                remaining_backlog.append(index)
                continue
            if remaining is not None:
                remaining.subtract(transaction.demands)
            committed.add(index); commit_ordinal[index] = ordinal; committed_this_op.append(index)
        backlog = remaining_backlog
        causes = Counter()
        for index in backlog:
            cause = blocking_cause(transactions[index], committed, remaining)
            if cause is None:
                raise AssertionError("uncommitted transaction must have a semantic or abstract-service blocker")
            causes[cause] += 1
        _, _, post_age_max = backlog_observables(backlog, transactions, ordinal)
        opportunity_rows.append({
            "phase": phase, "raw_logical_checkpoint": checkpoint if trace_opportunity else None,
            "logical_opportunity_ordinal": ordinal, "trace_derived_arrival": trace_opportunity,
            "new_transaction_groups": len(new), "pre_service_backlog": pre_service_backlog,
            "post_service_backlog": len(backlog), "post_service_age_max": post_age_max,
            "level": level, "abstract_service_quantum_per_bank_per_operation_per_logical_opportunity": quantum,
            "transition": transition, "committed_transaction_groups": len(committed_this_op),
            "post_service_backlog_by_blocking_cause": {cause: causes[cause] for cause in BLOCKING_CAUSES},
        })
        ordinal += 1
        if not trace_opportunity and not backlog:
            break
    if any(index not in committed and not any(parent not in committed for parent in transactions[index].predecessors) for index in backlog) and policy == "direct_unconstrained_commit":
        raise AssertionError("direct baseline failed to commit a dependency-ready transaction")
    for index, transaction in enumerate(transactions):
        if index in committed and any(parent not in committed or commit_ordinal[parent] > commit_ordinal[index] for parent in transaction.predecessors):
            raise AssertionError("transaction committed before an intrinsic predecessor")
    completion = "drained" if not backlog else "prefix_censored_backlog_remains"
    level_rows = Counter(row["level"] for row in opportunity_rows)
    high_rows = [row for row in opportunity_rows if row["level"] == "high"]
    cause_observations = Counter()
    for row in opportunity_rows:
        cause_observations.update(row["post_service_backlog_by_blocking_cause"])
    delays = [commit_ordinal[index] - transaction.arrival_ordinal for index, transaction in enumerate(transactions) if index in commit_ordinal]
    phase_rows = {}
    for phase in (*PHASES, POST_TRACE_DRAIN_PHASE):
        items = [row for row in opportunity_rows if row["phase"] == phase]
        if not items:
            continue
        phase_causes = Counter()
        for item in items:
            phase_causes.update(item["post_service_backlog_by_blocking_cause"])
        phase_high = [item for item in items if item["level"] == "high"]
        phase_rows[phase] = {
            "logical_opportunity_count": len(items),
            "pre_service_backlog": distribution(item["pre_service_backlog"] for item in items),
            "post_service_backlog": distribution(item["post_service_backlog"] for item in items),
            "post_service_age_max": distribution(item["post_service_age_max"] for item in items),
            "backlog_group_observations_by_blocking_cause": {cause: phase_causes[cause] for cause in BLOCKING_CAUSES},
            "high_level_occupancy_fraction": (len(phase_high) / len(items)) if controller is not None else 0.0,
            "longest_consecutive_high_logical_opportunity_run": longest_run(item["level"] == "high" for item in items),
        }
    return {
        "policy": policy, "transaction_group_count": len(transactions), "committed_transaction_group_count": len(committed),
        "completion_state": completion, "post_trace_drain_opportunities_used": max(0, len(opportunity_rows) - len(opportunities)),
        "post_trace_drain_limit": post_trace_drain_limit, "logical_opportunity_count": len(opportunity_rows),
        "pre_service_backlog": distribution(row["pre_service_backlog"] for row in opportunity_rows),
        "post_service_backlog": distribution(row["post_service_backlog"] for row in opportunity_rows),
        "post_service_age_max": distribution(row["post_service_age_max"] for row in opportunity_rows),
        "logical_opportunity_epoch_delay": distribution(delays),
        "backlog_group_observations_by_blocking_cause": {cause: cause_observations[cause] for cause in BLOCKING_CAUSES},
        "level_opportunity_counts": {name: level_rows[name] for name, _ in SERVICE_LEVELS} | {"direct_unconstrained": level_rows["direct_unconstrained"]},
        "high_level_occupancy_fraction": (level_rows["high"] / len(opportunity_rows)) if controller is not None and opportunity_rows else 0.0,
        "longest_consecutive_high_logical_opportunity_run": longest_run(row["level"] == "high" for row in opportunity_rows),
        "escalation_count": controller.escalations if controller else 0,
        "deescalation_count": controller.deescalations if controller else 0,
        "residual_backlog_at_high_service": distribution(row["post_service_backlog"] for row in high_rows),
        "phase_rows": phase_rows,
        "opportunity_rows": opportunity_rows,
    }


def iter_context_rows(path: Path, schema: str, label: str) -> Iterable[tuple[tuple[str, str, int, str], list[dict[str, Any]]]]:
    """Yield one immutable trace context at a time; never materialize all traces."""
    current: tuple[str, str, int, str] | None = None
    rows: list[dict[str, Any]] = []
    closed: set[tuple[str, str, int, str]] = set()
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("schema_version") != schema:
                raise ValueError(f"unexpected {label} schema")
            key = context_key(row)
            if current is None:
                current = key
            elif key != current:
                if current in closed:
                    raise AssertionError(f"{label} context reappeared after closure")
                closed.add(current); yield current, rows
                current, rows = key, []
            rows.append(row)
    if current is not None:
        if current in closed:
            raise AssertionError(f"final {label} context reappeared after closure")
        yield current, rows


def iter_contexts(record_path: Path, transaction_path: Path) -> Iterable[tuple[tuple[str, str, int, str], list[dict[str, Any]], list[dict[str, Any]]]]:
    records = iter_context_rows(record_path, RECORD_TRACE_SCHEMA, "A4.6.8.2.2.0 record trace")
    groups = iter_context_rows(transaction_path, TRANSACTION_TRACE_SCHEMA, "A4.7.1 transaction trace")
    for record_item, group_item in zip_longest(records, groups):
        if record_item is None or group_item is None:
            raise AssertionError("record and transaction trace context coverage mismatch")
        record_key, record_rows = record_item; group_key, group_rows = group_item
        if record_key != group_key:
            raise AssertionError("record and transaction trace context order mismatch")
        yield record_key, record_rows, group_rows


def summarize_context(context: tuple[str, str, int, str], record_ops: list[dict[str, Any]], groups: list[dict[str, Any]], profile: dict[str, Any], drain_limit: int) -> dict[str, Any]:
    predecessors, dependency_sources = dependency_predecessors(record_ops, groups)
    transactions, opportunities = make_scheduled_transactions(groups, predecessors, profile)
    direct = service_backlog(transactions=transactions, opportunities=opportunities, policy="direct_unconstrained_commit", post_trace_drain_limit=drain_limit)
    causal = service_backlog(transactions=transactions, opportunities=opportunities, policy="causal_elastic_v1", post_trace_drain_limit=drain_limit)
    if direct["completion_state"] != "drained" or direct["committed_transaction_group_count"] != len(transactions):
        raise AssertionError("direct-service baseline must commit every immutable transaction")
    direct_delays = direct["logical_opportunity_epoch_delay"]
    edge_count = sum(len(value) for value in predecessors.values())
    return {
        "anchor": context[0], "workload": context[1], "evaluation_horizon_append_opportunities": context[2], "organization_label": context[3],
        **profile, "transaction_group_count": len(transactions), "intrinsic_dependency_edge_count": edge_count,
        "intrinsic_dependency_edge_sources": dependency_sources,
        "intrinsic_dependency_edge_scope": "the four preregistered A4.7.0 edge types lifted from immutable record nodes to distinct A4.7.1 transaction groups, plus the already-fixed A4.7.1 same-head FIFO transaction predecessor; the latter is a serialization guard, not a new A4.7.0 edge type",
        "direct_service_baseline": {key: value for key, value in direct.items() if key != "opportunity_rows"},
        "causal_elastic_replay": {key: value for key, value in causal.items() if key != "opportunity_rows"},
        "comparison": {
            "direct_baseline_drained_all_transactions": True,
            "causal_additional_logical_opportunity_epoch_delay_vs_direct_max": (causal["logical_opportunity_epoch_delay"]["max"] or 0) - (direct_delays["max"] or 0),
            "causal_post_service_backlog_max": causal["post_service_backlog"]["max"],
            "causal_residual_backlog": causal["post_service_backlog"]["max"] if causal["completion_state"] != "drained" else 0,
            "comparison_is_not_hardware_performance": True,
        },
    }


def main() -> None:
    args = parse_args()
    a470, a471, a4720, a4721 = validate_inputs(args)
    if args.preflight_only:
        print("A4.8.0 preflight passed: A4.7.0 _02/A4.7.1/A4.7.2.0/A4.7.2.1 _03 hash-bound contracts and guards validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    rows = []
    for context, record_ops, groups in iter_contexts(args.a468220_trace, args.a471_trace):
        for profile in CANDIDATE_PROFILES:
            rows.append(summarize_context(context, record_ops, groups, profile, args.post_trace_drain_limit))
    expected_contexts = {(row["anchor"], row["workload"], int(row["evaluation_horizon_append_opportunities"]), row["organization_label"]) for row in a471["context_rows"]}
    observed_contexts = {(row["anchor"], row["workload"], int(row["evaluation_horizon_append_opportunities"]), row["organization_label"]) for row in rows}
    if observed_contexts != expected_contexts or len(rows) != len(expected_contexts) * len(CANDIDATE_PROFILES):
        raise AssertionError("unexpected A4.8.0 context/profile coverage")
    config = {
        "candidate_profiles": CANDIDATE_PROFILES, "service_levels": [{"name": name, "abstract_quantum_per_bank_per_operation_per_logical_opportunity": quantum} for name, quantum in SERVICE_LEVELS],
        "causal_counter_thresholds": CONTROLLER_THRESHOLDS, "post_trace_drain_limit": args.post_trace_drain_limit,
        "blocking_cause_precedence": list(BLOCKING_CAUSES), "intrinsic_dependency_curve": DEPENDENCY_CURVE,
        "direct_service_baseline": "unconstrained commit of dependency-ready immutable groups within their recorded logical opportunity; a functional reference, not a service-capacity claim",
        "boundary": "Logical opportunity ordinal, abstract service quantum, modeled bank label, transaction backlog, blocking-cause attribution, commit delay, and high-level occupancy are not physical banks/ports, hardware accesses/atomics/transactions, cycles, timing, latency, throughput, bandwidth, HBM traffic, energy, area, architecture selection, or RTL.",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(),
        "config": config, "config_hash": stable_hash(config),
        "execution_classification": "trace-derived immutable record/transaction inputs with functional dependency-preserving commit replay and modeled abstract service sensitivity; not measured hardware behavior",
        "input_artifacts": {
            "a468220_trace_sha256": sha256_file(args.a468220_trace), "a470_report_sha256": sha256_file(args.a470_report),
            "a471_report_sha256": sha256_file(args.a471_report), "a471_trace_sha256": sha256_file(args.a471_trace),
            "a4720_report_sha256": sha256_file(args.a4720_report), "a4721_report_sha256": sha256_file(args.a4721_report),
        },
        "replay_rows": rows,
        "semantic_guards": {
            "a470_a471_a4720_a4721_hash_bound_contract_chain_validated": True,
            "only_a470_preregistered_dependency_edge_types_lifted_plus_existing_a471_per_head_fifo_serialization": True,
            "a471_transaction_sets_order_fifo_and_commit_boundaries_unchanged": True,
            "direct_service_baseline_preserved_and_drains_all_transactions": True,
            "causal_controller_uses_only_current_backlog_age_and_history": True,
            "controller_receives_no_future_arrivals_horizon_anchor_or_workload_identity": True,
            "all_transaction_commits_obey_intrinsic_predecessors_and_atomic_commit_boundary": True,
            "backlog_causes_intrinsic_same_bank_rmw_and_cross_bank_atomic_reported_separately": True,
            "high_level_occupancy_runs_transitions_and_residual_backlog_reported": True,
            "commit_delay_named_logical_opportunity_epoch_delay_not_latency": True,
            "no_scheduler_reordering_payload_movement_drop_fallback_or_backing_action": True,
            "no_model_runtime_profiler_or_hardware_parameter_loaded": True,
            "no_hardware_access_cycle_timing_performance_or_architecture_claim": True,
        },
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a480_commit_aware_backlog_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.8.0 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} rows={len(rows)} contexts={len(expected_contexts)} profiles={len(CANDIDATE_PROFILES)}")


if __name__ == "__main__":
    main()
