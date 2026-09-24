#!/usr/bin/env python3
"""A4.7.2.1 no-model metadata physicalization sensitivity DSE.

The A4.7.1 semantic transaction trace and commit boundaries are immutable.
This tool only lowers those records through A4.7.2.0 modeled storage objects,
then sweeps abstract bank mappings and per-logical-checkpoint service envelopes.
Neither a bank label nor an operation is a physical choice or hardware access.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a470_metadata_access_concurrency import SCHEMA as A470_SCHEMA
from tools.analyze_kvzap_route_a471_metadata_transaction_contract import SCHEMA as A471_SCHEMA, TRANSACTION_TRACE_SCHEMA
from tools.analyze_kvzap_route_a4720_metadata_storage_sufficiency import LAYOUTS, SCHEMA as A4720_SCHEMA, context_key, modeled_object_bits, normalized_object_key, semantic_record_bits
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4721-metadata-physical-dse-1.2"
OPS = ("read", "write", "rmw")
PHASES = ("activation", "steady_state_append", "steady_state_dequeue")
BANK_COUNTS = (1, 4, 8)
MAPPINGS = ("head_affine_v1", "object_identity_striped_v1")
SERVICE_QUANTA = (1, 2, 4)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.7.2.1 no-model metadata physicalization sensitivity: abstract modeled storage-object bank/service pressure only, never selected hardware banks, ports, cycles, or performance.")
    parser.add_argument("--a470-report", type=Path, required=True)
    parser.add_argument("--a471-report", type=Path, required=True)
    parser.add_argument("--a471-trace", type=Path, required=True)
    parser.add_argument("--a4720-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate hash-bound A4.7.0/A4.7.1/A4.7.2.0 inputs and guards without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def distribution(values: Iterable[int]) -> dict[str, int | None]:
    items = sorted(values)
    def percentile(fraction: float) -> int | None:
        return items[int((len(items) - 1) * fraction)] if items else None
    return {"count": len(items), "min": min(items) if items else None, "p50": percentile(.50), "p95": percentile(.95), "p99": percentile(.99), "max": max(items) if items else None, "sum": sum(items)}


def longest_consecutive_integer_run(values: Iterable[int]) -> int:
    """Return a checkpoint-number run, not a cycle/timing duration."""
    ordered = sorted(set(values))
    if not ordered:
        return 0
    best = current = 1
    for previous, value in zip(ordered, ordered[1:]):
        current = current + 1 if value == previous + 1 else 1
        best = max(best, current)
    return best


@dataclass
class Histogram:
    counts: Counter[int] = field(default_factory=Counter)

    def add(self, value: int) -> None:
        if value < 0:
            raise ValueError("histogram value must be non-negative")
        self.counts[value] += 1

    def summary(self) -> dict[str, int | None]:
        total = sum(self.counts.values())
        if not total:
            return distribution([])
        expanded: list[int] = []
        for value, count in self.counts.items():
            expanded.extend([value] * count)
        return distribution(expanded)


def fnv1a_64(text: str) -> int:
    value = 0xCBF29CE484222325
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 0x100000001B3) & ((1 << 64) - 1)
    return value


def bank_index(mapping: str, bank_count: int, object_key: tuple[str, tuple[Any, ...]], *, layer: int, head: int) -> int:
    if bank_count not in BANK_COUNTS:
        raise ValueError("undeclared bank-count sensitivity")
    if mapping == "head_affine_v1":
        encoded = f"{layer}:{head}"
    elif mapping == "object_identity_striped_v1":
        encoded = repr(object_key)
    else:
        raise ValueError(f"unknown bank mapping {mapping}")
    return fnv1a_64(encoded) % bank_count


def lower_transaction(row: dict[str, Any], layout: str) -> dict[tuple[str, tuple[Any, ...]], str]:
    """Explicit semantic-set lowering; never a hardware access count."""
    flags: dict[tuple[str, tuple[Any, ...]], set[str]] = defaultdict(set)
    for set_name, flag in (("read_set", "read"), ("write_set", "write"), ("rmw_set", "rmw"), ("release_set", "release")):
        for item in row[set_name]:
            object_key = normalized_object_key(layout, str(item["record_type"]), list(item["record_identity"]), layer=int(row["layer"]), head=int(row["kv_head"]))
            flags[object_key].add(flag)
    lowered: dict[tuple[str, tuple[Any, ...]], str] = {}
    for object_key, object_flags in flags.items():
        if "rmw" in object_flags or ("read" in object_flags and ("write" in object_flags or "release" in object_flags)):
            lowered[object_key] = "rmw"
        elif "write" in object_flags or "release" in object_flags:
            lowered[object_key] = "write"
        elif object_flags == {"read"}:
            lowered[object_key] = "read"
        else:
            raise AssertionError(f"unlowerable semantic-set flags: {object_flags}")
    if not lowered:
        raise AssertionError("semantic transaction lowered to no modeled storage object")
    return lowered


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    a470 = read_completed(args.a470_report, A470_SCHEMA, "A4.7.0 _02")
    a471 = read_completed(args.a471_report, A471_SCHEMA, "A4.7.1")
    a4720 = read_completed(args.a4720_report, A4720_SCHEMA, "A4.7.2.0")
    trace_sha = sha256_file(args.a471_trace)
    if a471.get("transaction_trace", {}).get("schema_version") != TRANSACTION_TRACE_SCHEMA or a471["transaction_trace"].get("sha256") != trace_sha:
        raise ValueError("A4.7.1 transaction trace binding mismatch")
    if a471.get("input_artifacts", {}).get("a470_report_sha256") != sha256_file(args.a470_report):
        raise ValueError("A4.7.1 does not bind supplied A4.7.0 report")
    if a4720["input_artifacts"].get("a470_report_sha256") != sha256_file(args.a470_report) or a4720["input_artifacts"].get("a471_report_sha256") != sha256_file(args.a471_report) or a4720["input_artifacts"].get("a471_trace_sha256") != trace_sha:
        raise ValueError("A4.7.2.0 predecessor hash chain mismatch")
    a471_guards = ("every_dependency_node_maps_to_exactly_one_transaction_group", "every_group_has_read_write_rmw_release_sets_and_one_commit_boundary", "post_commit_span_owner_source_queue_and_oldest_replay_consistent", "semantic_atomicity_explicitly_not_hardware_atomicity")
    a4720_guards = ("four_semantic_record_types_fixed_and_all_retained", "a471_transaction_sets_and_commit_boundaries_not_changed", "every_semantic_record_maps_to_declared_modeled_storage_object", "no_silent_field_or_namespace_overflow", "semantic_record_storage_object_and_physical_entry_concepts_separated")
    if not all(a471.get("semantic_guards", {}).get(item) is True for item in a471_guards):
        raise ValueError("A4.7.1 semantic guards incomplete")
    if not all(a4720.get("semantic_guards", {}).get(item) is True for item in a4720_guards):
        raise ValueError("A4.7.2.0 semantic guards incomplete")
    return a470, a471, a4720


def static_candidate_rows(a4720: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    groups: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in a4720["width_sufficiency_rows"]:
        groups[(row["layout"], row["storage_scope"], row["namespace_policy"], int(row["generation_bits"]))].append(row)
    rows = []
    for key, members in sorted(groups.items()):
        baseline = [item for item in members if int(item["width_slack_bits"]) == 0]
        if not baseline or not all(item["namespace_width_sufficient"] for item in baseline):
            raise AssertionError("zero-slack profile lacks A4.7.2.0 sufficiency")
        joint_widths = {field: max(item["field_widths_bits"][field] for item in baseline) for field in baseline[0]["field_widths_bits"]}
        joint_counts = {name: max(item["modeled_peak_storage_object_counts"][name] for item in baseline) for name in baseline[0]["modeled_peak_storage_object_counts"]}
        joint_object_bits = modeled_object_bits(key[0], semantic_record_bits(joint_widths))
        joint_safe_bits = sum(joint_counts[name] * joint_object_bits[name] for name in joint_counts)
        rows.append({
            "layout": key[0], "storage_scope": key[1], "namespace_policy": key[2], "generation_bits": key[3], "context_count": len(baseline),
            "trace_context_peak_metadata_bits_distribution": distribution(item["modeled_peak_metadata_bits"] for item in baseline),
            "cross_context_joint_safe_field_widths_bits": joint_widths,
            "cross_context_joint_safe_modeled_storage_object_counts": joint_counts,
            "cross_context_joint_safe_modeled_storage_object_widths_bits": joint_object_bits,
            "cross_context_joint_safe_modeled_metadata_bits": joint_safe_bits,
            "joint_safe_footprint_rule": "max each field width across the fixed workload set, max each modeled object count across the fixed workload set, then multiply together. This is a conservative cross-context modeled accounting bound, not a physical entry allocation or measured capacity.",
            "static_filter": "survives_zero_slack", "all_contexts_namespace_sufficient": True,
            "positive_slack_filtered_as_monotonic_modeled_bit_expansion": sorted({int(item["width_slack_bits"]) for item in members if int(item["width_slack_bits"]) > 0}),
            "physical_entry_not_selected": True,
        })
    summary = {"input_width_rows": len(a4720["width_sufficiency_rows"]), "surviving_static_profiles": len(rows), "filter": "Only width slack >0 is filtered within an identical layout/scope/namespace-policy/generation profile as a monotonic modeled-bit expansion. Layout/scope/reuse alternatives remain for later locality/conflict analysis.", "joint_safe_footprint_added_in_schema_1_1": True}
    return rows, summary


def saturation_streaks(checkpoints: list[int], bank_count: int, saturated: dict[int, set[int]]) -> dict[str, Any]:
    """Summarize runs over phase-local opportunity ordinal, never raw time."""
    ordinal = {checkpoint: index for index, checkpoint in enumerate(sorted(checkpoints))}
    per_bank = {bank: longest_consecutive_integer_run(ordinal[checkpoint] for checkpoint in saturated.get(bank, set())) for bank in range(bank_count)}
    observed = set(checkpoints)
    full = [bank for bank in range(bank_count) if observed and saturated.get(bank, set()) == observed]
    return {
        "phase_local_opportunity_count": len(ordinal),
        "per_bank_max_consecutive_saturated_phase_local_opportunity_run": distribution(per_bank.values()),
        "peak_any_bank_consecutive_saturated_phase_local_opportunity_run": max(per_bank.values(), default=0),
        "banks_saturated_at_every_observed_phase_local_opportunity": full,
        "phase_local_order_rule": "sort the immutable A4.7.1 raw logical checkpoints within each phase, then map them to contiguous phase-local opportunity ordinals; this is not a cycle or time duration",
    }


class ContextReplay:
    def __init__(self, key: tuple[str, str, int, str]):
        self.key = key
        self.pressure: Counter[tuple[str, int, str, int, int, str]] = Counter()
        self.checkpoints: dict[str, set[int]] = defaultdict(set)
        self.fanout: dict[tuple[str, int, str, str, str], Histogram] = defaultdict(Histogram)
        self.transaction_count: Counter[tuple[str, int, str, str]] = Counter()

    def add(self, row: dict[str, Any]) -> None:
        phase, checkpoint = str(row["phase"]), int(row["logical_checkpoint"])
        if phase not in PHASES:
            raise ValueError("undeclared A4.7.1 phase")
        self.checkpoints[phase].add(checkpoint)
        layer, head = int(row["layer"]), int(row["kv_head"])
        for layout in LAYOUTS:
            lowered = lower_transaction(row, layout)
            for mapping in MAPPINGS:
                for bank_count in BANK_COUNTS:
                    banks: set[int] = set()
                    for object_key, op in lowered.items():
                        bank = bank_index(mapping, bank_count, object_key, layer=layer, head=head)
                        banks.add(bank)
                        self.pressure[(layout, bank_count, mapping, checkpoint, bank, op)] += 1
                    self.fanout[(layout, bank_count, mapping, phase, "object_fanout")].add(len(lowered))
                    self.fanout[(layout, bank_count, mapping, phase, "bank_fanout")].add(len(banks))
                    self.transaction_count[(layout, bank_count, mapping, phase)] += 1

    def finalize(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        bank_rows: list[dict[str, Any]] = []
        fanout_rows: list[dict[str, Any]] = []
        service_rows: list[dict[str, Any]] = []
        anchor, workload, horizon, organization = self.key
        for layout in LAYOUTS:
            for mapping in MAPPINGS:
                for bank_count in BANK_COUNTS:
                    common = {"anchor": anchor, "workload": workload, "evaluation_horizon_append_opportunities": horizon, "organization_label": organization, "layout": layout, "bank_mapping": mapping, "bank_count_sensitivity": bank_count, "physical_entry_not_selected": True}
                    for phase in PHASES:
                        checkpoints = sorted(self.checkpoints.get(phase, set()))
                        tx_count = self.transaction_count[(layout, bank_count, mapping, phase)]
                        if not tx_count:
                            continue
                        for kind in ("object_fanout", "bank_fanout"):
                            fanout_rows.append({**common, "phase": phase, "fanout_kind": kind, "transaction_group_count": tx_count, "fanout": self.fanout[(layout, bank_count, mapping, phase, kind)].summary(), "semantic_atomicity_only": True, "hardware_atomic_operation_not_inferred": True})
                        demand_by_op: dict[str, list[int]] = {}
                        for op in OPS:
                            demands = [self.pressure[(layout, bank_count, mapping, checkpoint, bank, op)] for checkpoint in checkpoints for bank in range(bank_count)]
                            demand_by_op[op] = demands
                            bank_rows.append({**common, "phase": phase, "logical_checkpoint_count": len(checkpoints), "operation": op, "per_bank_per_logical_checkpoint_modeled_demand": distribution(demands), "nonzero_demand_observations": sum(value > 0 for value in demands), "demand_is_not_hardware_access_count": True})
                        for service_model in ("independent_class", "unified_total"):
                            for quantum in SERVICE_QUANTA:
                                if service_model == "independent_class":
                                    shortfall_by_op = {op: sum(max(0, value - quantum) for value in demand_by_op[op]) for op in OPS}
                                    saturated = sum(value > quantum for op in OPS for value in demand_by_op[op])
                                    demand = sum(sum(values) for values in demand_by_op.values())
                                    slots = len(checkpoints) * bank_count * len(OPS) * quantum
                                    saturation_streak_by_basis: dict[str, dict[str, Any]] = {}
                                    for op in OPS:
                                        per_bank = {bank: {checkpoint for checkpoint in checkpoints if self.pressure[(layout, bank_count, mapping, checkpoint, bank, op)] > quantum} for bank in range(bank_count)}
                                        saturation_streak_by_basis[op] = saturation_streaks(checkpoints, bank_count, per_bank)
                                    any_class = {bank: {checkpoint for checkpoint in checkpoints if any(self.pressure[(layout, bank_count, mapping, checkpoint, bank, op)] > quantum for op in OPS)} for bank in range(bank_count)}
                                    saturation_streak_by_basis["any_class"] = saturation_streaks(checkpoints, bank_count, any_class)
                                else:
                                    totals = [sum(self.pressure[(layout, bank_count, mapping, checkpoint, bank, op)] for op in OPS) for checkpoint in checkpoints for bank in range(bank_count)]
                                    shortfall_by_op = {"unattributed_unified_total": sum(max(0, value - quantum) for value in totals)}
                                    saturated, demand, slots = sum(value > quantum for value in totals), sum(totals), len(totals) * quantum
                                    per_bank = {bank: {checkpoint for checkpoint in checkpoints if sum(self.pressure[(layout, bank_count, mapping, checkpoint, bank, op)] for op in OPS) > quantum} for bank in range(bank_count)}
                                    saturation_streak_by_basis = {"unified_total": saturation_streaks(checkpoints, bank_count, per_bank)}
                                service_rows.append({**common, "phase": phase, "service_model": service_model, "abstract_service_quantum_per_bank_per_logical_checkpoint": quantum, "logical_checkpoint_count": len(checkpoints), "total_modeled_object_operation_demand": demand, "abstract_service_slots": slots, "modeled_shortfall": sum(shortfall_by_op.values()), "shortfall_by_operation": shortfall_by_op, "saturated_bank_checkpoint_observations": saturated, "saturation_streaks_by_basis": saturation_streak_by_basis, "no_reordering_or_scheduler_inferred": True, "not_cycles_bandwidth_or_port_requirement": True})
        return bank_rows, fanout_rows, service_rows


def replay_trace(path: Path, expected_contexts: set[tuple[str, str, int, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    bank_rows: list[dict[str, Any]] = []
    fanout_rows: list[dict[str, Any]] = []
    service_rows: list[dict[str, Any]] = []
    active: ContextReplay | None = None
    completed: set[tuple[str, str, int, str]] = set()
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("schema_version") != TRANSACTION_TRACE_SCHEMA:
                raise ValueError("unexpected A4.7.1 transaction trace schema")
            key = context_key(row)
            if active is None:
                active = ContextReplay(key)
            elif key != active.key:
                if key in completed:
                    raise AssertionError("A4.7.1 contexts must be contiguous")
                current = active.finalize(); bank_rows.extend(current[0]); fanout_rows.extend(current[1]); service_rows.extend(current[2]); completed.add(active.key)
                active = ContextReplay(key)
            active.add(row)
    if active is None:
        raise ValueError("empty A4.7.1 transaction trace")
    current = active.finalize(); bank_rows.extend(current[0]); fanout_rows.extend(current[1]); service_rows.extend(current[2]); completed.add(active.key)
    if completed != expected_contexts:
        raise AssertionError("A4.7.1 context coverage mismatch")
    return bank_rows, fanout_rows, service_rows


def main() -> None:
    args = parse_args()
    a470, a471, a4720 = validate_inputs(args)
    if args.preflight_only:
        print("A4.7.2.1 preflight passed: A4.7.0 _02/A4.7.1/A4.7.2.0 hash-bound contracts and guards validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    candidates, static_filter = static_candidate_rows(a4720)
    expected_contexts = {context_key(row) for row in a471["context_rows"]}
    bank_rows, fanout_rows, service_rows = replay_trace(args.a471_trace, expected_contexts)
    if len(candidates) != len(LAYOUTS) * 3 * 3 or not bank_rows or not fanout_rows or not service_rows:
        raise AssertionError("unexpected A4.7.2.1 coverage")
    config = {
        "layouts": LAYOUTS, "bank_counts": list(BANK_COUNTS), "bank_mappings": list(MAPPINGS), "operations": list(OPS), "phases": list(PHASES), "service_quanta": list(SERVICE_QUANTA),
        "service_models": {"independent_class": "Each modeled R/W/RMW class receives the declared quantum independently; no shared resource is implied.", "unified_total": "All modeled R/W/RMW demand shares one declared total quantum; class-specific shortfall is deliberately unattributed."},
        "static_filter": static_filter["filter"],
        "transaction_lowering": "Within one immutable A4.7.1 transaction, RMW or read+write/release lowers to modeled RMW, release-only lowers to modeled write, and no transactions merge or reorder.",
        "boundary": "Bank labels, modeled object-operation demand, service quanta, shortfall, fanout, and phase-local opportunity saturation runs are abstract sensitivity values, not selected physical banks/ports, hardware accesses/atomics/transactions, cycles, timing, latency, throughput, bandwidth, HBM traffic, energy, area, architecture specification, or RTL.",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "execution_classification": "functional lowering of fixed semantic transaction sets plus modeled storage-object footprint, bank-mapping, commit-fanout, and abstract per-logical-checkpoint service sensitivity; not measured hardware behavior",
        "input_artifacts": {"a470_report_sha256": sha256_file(args.a470_report), "a471_report_sha256": sha256_file(args.a471_report), "a471_trace_sha256": sha256_file(args.a471_trace), "a4720_report_sha256": sha256_file(args.a4720_report)},
        "static_candidate_rows": candidates, "static_filter_summary": static_filter, "bank_pressure_rows": bank_rows, "commit_fanout_rows": fanout_rows, "service_sensitivity_rows": service_rows,
        "semantic_guards": {"complete_a470_a471_a4720_hash_bound_chain_validated": True, "only_a4720_sufficient_layouts_and_width_profiles_consumed": True, "a471_transaction_sets_commit_boundaries_and_order_unchanged": True, "semantic_atomicity_explicitly_not_hardware_atomic_operation": True, "intrinsic_dependency_not_recomputed_or_conflated_with_modeled_physical_contention": True, "static_slack_filter_is_only_monotonic_modeled_bit_filter": True, "cross_context_joint_safe_modeled_footprint_reported": True, "phase_local_opportunity_saturation_streaks_reported": True, "bank_mapping_and_service_vectors_predeclared": True, "modeled_operations_do_not_equal_hardware_accesses": True, "no_scheduler_reordering_payload_movement_or_protection_action": True, "no_model_runtime_profiler_or_hardware_parameter_loaded": True, "no_cycles_bandwidth_latency_throughput_energy_area_or_architecture_selection": True},
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a4721_metadata_physical_dse_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.7.2.1 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} static_profiles={len(candidates)} topologies={len(LAYOUTS) * len(MAPPINGS) * len(BANK_COUNTS)} bank_rows={len(bank_rows)} service_rows={len(service_rows)}")


if __name__ == "__main__":
    main()
