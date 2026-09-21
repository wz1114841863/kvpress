#!/usr/bin/env python3
"""A4.6.8.1 representation-aware, hardware-agnostic pending access contract.

This no-model replay turns the exact A4.6.8.0 birth-ordered source spans into
an explicit *logical* lifecycle/metadata/payload-reference operation trace.  It
does not assign a physical layout, descriptor width, payload movement, byte
count, port, bank, timing, or hardware cost to any operation.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import SCHEMA as A461_SCHEMA, read_completed
from tools.analyze_kvzap_route_a4632_temporal_contention_replay import HORIZONS, source_streams
from tools.analyze_kvzap_route_a464_causal_elastic_contract import SCHEMA as A464_SCHEMA
from tools.analyze_kvzap_route_a465_causal_capacity_envelope import expected_a464, run_causal_observer, validate_against_a464
from tools.analyze_kvzap_route_a4670_pending_ownership_reference import (
    SCHEMA as A4670_SCHEMA,
    PendingOwnershipState,
    derive_fixed_grants,
    organization_variants,
)
from tools.analyze_kvzap_route_a4671_pending_organization_tax_recovery import SCHEMA as A4671_SCHEMA
from tools.analyze_kvzap_route_a4680_pending_representation_sufficiency import (
    REQUIRED_A4670_GUARDS,
    REPRESENTATION,
    SCHEMA as A4680_SCHEMA,
    a4671_variant,
    prior_horizon,
    prior_variant,
    source_snapshots,
    validate_chain,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4681-representation-access-contract-1.0"
Stream = tuple[int, int]
SOURCES = ("private", "shared")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.6.8.1 no-model Route-A birth-ordered span access-contract replay: "
            "fixed grants/FIFO and hardware-agnostic lifecycle/metadata/payload-reference "
            "primitives only; no physical mapping or hardware selection."
        )
    )
    parser.add_argument("--a461-report", type=Path, required=True)
    parser.add_argument("--a464-report", type=Path, required=True)
    parser.add_argument("--a4670-report", type=Path, required=True)
    parser.add_argument("--a4671-report", type=Path, required=True)
    parser.add_argument("--a4680-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate completed hash-bound inputs and guards without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


@dataclass
class AccessSpan:
    """One logical source/birth span; not a descriptor or physical record."""

    source: str
    birth_opportunity: int
    sequence_start: int
    count: int

    @property
    def key(self) -> tuple[int, int]:
        return self.birth_opportunity, self.sequence_start

    def consume(self, count: int) -> None:
        if count <= 0 or count > self.count:
            raise ValueError("invalid access-contract span consumption")
        self.sequence_start += count
        self.count -= count


class AccessStatistics:
    """Aggregate event pressure without treating primitive counts as physical accesses."""

    def __init__(self) -> None:
        self.by_phase: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.by_phase_layer_opportunity: dict[tuple[str, int, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.release_opportunities: set[tuple[str, int, int]] = set()
        self.max_active_spans_one_layer = 0
        self.max_active_sources_one_layer = 0

    def record(self, *, phase: str, layer: int, opportunity: int, name: str, count: int = 1) -> None:
        if phase not in {"activation", "steady_state_append", "steady_state_dequeue"} or count < 0:
            raise ValueError("invalid logical access-contract event")
        self.by_phase[phase][name] += count
        self.by_phase_layer_opportunity[(phase, layer, opportunity)][name] += count
        if name == "span_release":
            self.release_opportunities.add((phase, layer, opportunity))

    def observe_layer_concurrency(self, *, states: dict[Stream, "BirthOrderedAccessState"]) -> None:
        by_layer_spans: dict[int, int] = defaultdict(int)
        by_layer_sources: dict[int, int] = defaultdict(int)
        for (layer, _), state in states.items():
            by_layer_spans[layer] += state.active_spans()
            by_layer_sources[layer] += state.active_sources()
        self.max_active_spans_one_layer = max(self.max_active_spans_one_layer, max(by_layer_spans.values(), default=0))
        self.max_active_sources_one_layer = max(self.max_active_sources_one_layer, max(by_layer_sources.values(), default=0))

    def phase_summary(self, phase: str) -> dict[str, Any]:
        events = dict(sorted(self.by_phase[phase].items()))
        pressure_rows = [
            (layer, opportunity, values)
            for (row_phase, layer, opportunity), values in self.by_phase_layer_opportunity.items()
            if row_phase == phase
        ]
        max_total = max((sum(values.values()) for _, _, values in pressure_rows), default=0)
        max_compare = max((values.get("oldest_source_compare", 0) for _, _, values in pressure_rows), default=0)
        max_release = max((values.get("span_release", 0) for _, _, values in pressure_rows), default=0)
        return {
            "logical_primitive_counts": events,
            "max_logical_primitives_one_layer_one_opportunity": max_total,
            "max_cross_source_oldest_selection_one_layer_one_opportunity": max_compare,
            "release_pattern": {
                "span_release_count": events.get("span_release", 0),
                "layer_opportunity_with_release_count": sum(1 for item in self.release_opportunities if item[0] == phase),
                "max_span_releases_one_layer_one_opportunity": max_release,
            },
        }


class BirthOrderedAccessState:
    """Replay state which emits the declared logical access-contract primitives."""

    def __init__(self, *, statistics: AccessStatistics, layer: int) -> None:
        self.statistics = statistics
        self.layer = layer
        self.sources: dict[str, deque[AccessSpan]] = {source: deque() for source in SOURCES}
        self.live = {source: 0 for source in SOURCES}
        self.next_sequence = 0
        self.created_span_count = 0
        self.released_span_count = 0
        self.tail_extension_count = 0

    @property
    def pending(self) -> int:
        return sum(self.live.values())

    def active_spans(self) -> int:
        return sum(len(queue) for queue in self.sources.values())

    def active_sources(self) -> int:
        return sum(bool(queue) for queue in self.sources.values())

    def append_from_reference(self, *, events: list[dict[str, int]], birth_opportunity: int, phase: str) -> None:
        """Create source-affiliated spans exactly as assigned by A4.6.7.0."""
        for event in events:
            source, count = str(event["source"]), int(event["count"])
            if source not in self.sources or count <= 0 or birth_opportunity < 0:
                raise ValueError("invalid source-span creation")
            self.sources[source].append(AccessSpan(source, birth_opportunity, self.next_sequence, count))
            self.live[source] += count
            self.next_sequence += count
            self.created_span_count += 1
            for name in ("span_create", "ownership_link", "payload_reference_create"):
                self.statistics.record(phase=phase, layer=self.layer, opportunity=birth_opportunity, name=name)

    def extend_tail(self, *, source: str, birth_opportunity: int, sequence_start: int, count: int, phase: str) -> None:
        """A legal extension is same-source, same-birth, and sequence-contiguous only.

        The fixed A4.6.7.0 event stream does not need this coalescing operation:
        its source-affiliation event is represented by one span create.  Keeping
        this primitive explicit prevents an implementation from silently merging
        entries across a birth boundary merely to reduce metadata.
        """
        if source not in self.sources or count <= 0 or not self.sources[source]:
            raise ValueError("tail extension requires an existing source tail")
        tail = self.sources[source][-1]
        if (tail.birth_opportunity, tail.sequence_start + tail.count) != (birth_opportunity, sequence_start):
            raise ValueError("tail extension would cross birth/order boundary")
        tail.count += count
        self.live[source] += count
        self.next_sequence = max(self.next_sequence, sequence_start + count)
        self.tail_extension_count += 1
        self.statistics.record(phase=phase, layer=self.layer, opportunity=birth_opportunity, name="tail_extension")

    def oldest_source(self, *, phase: str, opportunity: int) -> str:
        candidates = [source for source in SOURCES if self.sources[source]]
        if not candidates:
            raise ValueError("empty access state has no oldest entry")
        for _ in candidates:
            self.statistics.record(phase=phase, layer=self.layer, opportunity=opportunity, name="source_head_metadata_read")
        if len(candidates) == 2:
            self.statistics.record(phase=phase, layer=self.layer, opportunity=opportunity, name="oldest_source_compare")
        return min(candidates, key=lambda source: self.sources[source][0].key)

    def dequeue(self, *, count: int, phase: str, opportunity: int) -> list[tuple[str, int]]:
        if count < 0 or count > self.pending:
            raise ValueError("invalid access-contract dequeue")
        chunks: list[tuple[str, int]] = []
        while count:
            source = self.oldest_source(phase=phase, opportunity=opportunity)
            span = self.sources[source][0]
            amount = min(count, span.count)
            span.consume(amount)
            self.live[source] -= amount
            count -= amount
            self.statistics.record(phase=phase, layer=self.layer, opportunity=opportunity, name="span_partial_dequeue")
            self.statistics.record(phase=phase, layer=self.layer, opportunity=opportunity, name="span_head_remaining_update")
            if span.count == 0:
                self.sources[source].popleft()
                self.released_span_count += 1
                for name in ("span_release", "ownership_unlink", "payload_reference_release", "source_head_update"):
                    self.statistics.record(phase=phase, layer=self.layer, opportunity=opportunity, name=name)
            else:
                self.statistics.record(phase=phase, layer=self.layer, opportunity=opportunity, name="source_head_update")
            chunks.append((source, amount))
        return chunks

    def reconstruct_canonical_runs(self) -> list[tuple[str, int, int, int]]:
        offsets = {source: 0 for source in SOURCES}
        output: list[tuple[str, int, int, int]] = []
        while True:
            candidates = []
            for source in SOURCES:
                if offsets[source] < len(self.sources[source]):
                    span = self.sources[source][offsets[source]]
                    candidates.append((span.key, source, span))
            if not candidates:
                return output
            _, source, span = min(candidates, key=lambda item: item[0])
            if sum(item[0] == span.key for item in candidates) != 1:
                raise AssertionError("access state has ambiguous canonical oldest entry")
            output.append((source, span.birth_opportunity, span.sequence_start, span.count))
            offsets[source] += 1


def assert_access_contract_sufficient(*, reference: PendingOwnershipState, state: BirthOrderedAccessState) -> None:
    """Functional gate: every access-contract state must reconstruct A4.6.7.0 FIFO."""
    if state.pending != reference.pending or state.next_sequence != reference.next_sequence:
        raise AssertionError("access contract lost pending accounting or sequence coverage")
    actual = state.reconstruct_canonical_runs()
    expected = [(item.birth_opportunity, item.sequence_start, item.count) for item in reference.canonical]
    if [(birth, sequence, count) for _, birth, sequence, count in actual] != expected:
        raise AssertionError("access contract cannot reconstruct canonical FIFO order")
    for source in SOURCES:
        access_source = [(item.birth_opportunity, item.sequence_start, item.count) for item in state.sources[source]]
        if access_source != source_snapshots(reference)[source]:
            raise AssertionError("access contract cannot reconstruct source ownership")
    if reference.pending:
        chosen = min((source for source in SOURCES if state.sources[source]), key=lambda source: state.sources[source][0].key)
        if state.sources[chosen][0].key != reference.canonical[0].key:
            raise AssertionError("access contract oldest selection disagrees with canonical FIFO")


def validate_a4680(*, a4680: dict[str, Any], args: argparse.Namespace) -> None:
    inputs = a4680.get("input_artifacts", {})
    expected = {
        "a461_report_sha256": sha256_file(args.a461_report),
        "a464_report_sha256": sha256_file(args.a464_report),
        "a4670_report_sha256": sha256_file(args.a4670_report),
        "a4671_report_sha256": sha256_file(args.a4671_report),
    }
    if any(inputs.get(name) != value for name, value in expected.items()):
        raise ValueError("A4.6.8.0 does not hash-bind the supplied upstream reports")
    if a4680.get("config", {}).get("representation", "").find("same-source, same-birth") < 0:
        raise ValueError("A4.6.8.0 representation contract is not the declared birth-ordered source span")
    required = (
        "complete_hash_chain_validated",
        "fixed_a464_grants_not_rescheduled",
        "a4670_canonical_fifo_replayed_exactly",
        "current_pending_birth_order_oldest_and_source_reconstructible",
        "source_count_only_lossy_negative_control_rejected",
        "a4671_span_inventory_and_capacity_context_matched",
        "q0_shared_and_large_q_headlocal_endpoints_validated",
        "no_finite_allocator_migration_drop_fallback_or_backing_action",
        "no_model_or_runtime_loaded",
        "no_descriptor_width_byte_access_port_bank_traffic_cycle_or_hardware_parameter_selected",
        "qwen_llama_rows_separate",
    )
    if not all(a4680.get("semantic_guards", {}).get(name) is True for name in required):
        raise ValueError("A4.6.8.0 representation sufficiency gate is incomplete")
    if a4680.get("negative_control", {}).get("source_count_only_representation_rejected") is not True:
        raise ValueError("A4.6.8.0 lossiness negative control did not pass")


def _reference_operations(states: dict[Stream, PendingOwnershipState]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for state in states.values():
        for name, count in state.operation_counts.items():
            totals[name] += count
    return dict(sorted(totals.items()))


def simulate_variant(
    *, inventory: dict[Stream, dict[str, int]], arrivals: dict[Stream, list[int]],
    fixed_schedule: list[dict[Stream, tuple[int, int, int]]], organization: str,
    private_quota: int | None,
) -> dict[str, Any]:
    references = {key: PendingOwnershipState(organization=organization, private_quota=private_quota) for key in sorted(inventory)}
    statistics = AccessStatistics()
    states = {key: BirthOrderedAccessState(statistics=statistics, layer=key[0]) for key in sorted(inventory)}
    checkpoints = {"after_activation": 0, "after_append": 0, "after_dequeue": 0}
    for key, reference in references.items():
        events = reference.enqueue(count=inventory[key]["pending"], birth_opportunity=0)
        states[key].append_from_reference(events=events, birth_opportunity=0, phase="activation")
        assert_access_contract_sufficient(reference=reference, state=states[key])
        checkpoints["after_activation"] += 1
    statistics.observe_layer_concurrency(states=states)
    for index, schedule in enumerate(fixed_schedule):
        opportunity = index + 1
        for key, reference in references.items():
            events = reference.enqueue(count=arrivals[key][index], birth_opportunity=opportunity)
            states[key].append_from_reference(events=events, birth_opportunity=opportunity, phase="steady_state_append")
            expected_pre, _, _ = schedule[key]
            if reference.pending != expected_pre:
                raise AssertionError("access-contract append changed fixed pre-grant pending")
            assert_access_contract_sufficient(reference=reference, state=states[key])
            checkpoints["after_append"] += 1
        statistics.observe_layer_concurrency(states=states)
        for key, reference in references.items():
            _, grant, expected_post = schedule[key]
            reference_chunks = [(str(item["source"]), int(item["count"])) for item in reference.dequeue(count=grant)]
            access_chunks = states[key].dequeue(count=grant, phase="steady_state_dequeue", opportunity=opportunity)
            if access_chunks != reference_chunks:
                raise AssertionError("access-contract dequeue diverges from A4.6.7.0 canonical FIFO")
            if reference.pending != expected_post:
                raise AssertionError("access-contract dequeue changed fixed post-grant pending")
            assert_access_contract_sufficient(reference=reference, state=states[key])
            checkpoints["after_dequeue"] += 1
        statistics.observe_layer_concurrency(states=states)
    operations = _reference_operations(references)
    created = sum(state.created_span_count for state in states.values())
    released = sum(state.released_span_count for state in states.values())
    if created != sum(value for name, value in operations.items() if name.endswith("_enqueue_segment_count")):
        raise AssertionError("each immutable source-affiliation enqueue segment must create one span")
    if released != sum(value for name, value in operations.items() if name.endswith("_release_segment_count")):
        raise AssertionError("each released source-affiliation segment must release one span")
    return {
        "reference_logical_queue_operations": operations,
        "replay_gate": {
            "current_pending_birth_order_oldest_and_source_reconstructed_after_each_event": True,
            "fixed_dequeue_chunks_match_a4670_canonical_fifo": True,
            "source_residence_immutable_no_migration": True,
            "checkpoints": checkpoints,
        },
        "representation_lifecycle_inventory": {
            "span_create_count": created,
            "tail_extension_count": sum(state.tail_extension_count for state in states.values()),
            "span_release_count": released,
            "tail_extension_rule": "same_source + same_birth_opportunity + sequence_contiguous only; fixed replay uses source-affiliation span_create events and performs no cross-birth extension",
        },
        "hardware_agnostic_access_pressure": {
            "activation": statistics.phase_summary("activation"),
            "steady_state_append": statistics.phase_summary("steady_state_append"),
            "steady_state_dequeue": statistics.phase_summary("steady_state_dequeue"),
            "concurrent_representation_state": {
                "max_active_spans_one_layer": statistics.max_active_spans_one_layer,
                "max_active_sources_one_layer": statistics.max_active_sources_one_layer,
            },
            "payload_reference_boundary": "payload_reference_create/release denote only logical association lifetime. They do not imply K/V reads, K/V writes, copies, movement, bytes, or traffic.",
        },
        "terminal_pending": sum(state.pending for state in states.values()),
    }


def endpoint_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference_logical_queue_operations": row["reference_logical_queue_operations"],
        "representation_lifecycle_inventory": row["representation_lifecycle_inventory"],
        "terminal_pending": row["terminal_pending"],
    }


def analyze_row(*, source_row: dict[str, Any], a464_row: dict[str, Any], a4670_row: dict[str, Any], a4671_row: dict[str, Any], a4680_row: dict[str, Any]) -> dict[str, Any]:
    inventory, arrivals = source_streams(source_row)
    a4680_horizons = {int(item["evaluation_horizon_append_opportunities"]): item for item in a4680_row["horizon_rows"]}
    horizon_rows = []
    for horizon in HORIZONS:
        observed = run_causal_observer(inventory=inventory, arrivals=arrivals, horizon=horizon)
        validate_against_a464(observed, expected_a464(a464_row, horizon))
        ownership_horizon = prior_horizon(a4670_row, horizon)
        tax_horizon = prior_horizon(a4671_row, horizon)
        representation_horizon = a4680_horizons[horizon]
        fixed_schedule = derive_fixed_grants(observed=observed, arrivals=arrivals)
        rows = []
        representation_by_label = {item["label"]: item for item in representation_horizon["representation_rows"]}
        for variant in organization_variants(observed):
            result = simulate_variant(
                inventory=inventory, arrivals=arrivals, fixed_schedule=fixed_schedule,
                organization=variant["organization"], private_quota=variant["private_quota"],
            )
            prior = prior_variant(ownership_horizon, variant["label"])
            if result["reference_logical_queue_operations"] != prior["global_logical_queue_operations"]:
                raise AssertionError("A4.6.8.1 reference operations disagree with A4.6.7.0")
            span = representation_by_label[variant["label"]]["lossless_span_inventory"]
            lifecycle = result["representation_lifecycle_inventory"]
            if lifecycle["span_create_count"] != span["span_created_count"] or lifecycle["span_release_count"] != span["span_released_count"]:
                raise AssertionError("A4.6.8.1 lifecycle inventory disagrees with A4.6.8.0")
            tax = a4671_variant(tax_horizon, variant["label"])
            rows.append({
                "label": variant["label"],
                "organization": variant["organization"],
                "private_quota_per_head": variant["private_quota"],
                "semantic_endpoint_only": variant["semantic_endpoint_only"],
                "representation": REPRESENTATION,
                "a4671_capacity_recovery_context": tax["logical_capacity_recovery_context"],
                **result,
            })
        by_label = {row["label"]: row for row in rows}
        if endpoint_payload(by_label["layer_shared_unbounded"]) != endpoint_payload(by_label["hierarchical_q0_shared_endpoint"]):
            raise AssertionError("q=0 endpoint changed shared access-contract replay")
        if endpoint_payload(by_label["head_local_private_unbounded"]) != endpoint_payload(by_label["hierarchical_qpeak_head_local_endpoint"]):
            raise AssertionError("large-q endpoint changed head-local access-contract replay")
        horizon_rows.append({
            "evaluation_horizon_append_opportunities": horizon,
            "horizon_completion_state": tax_horizon["horizon_completion_state"],
            "fixed_causal_outcome": ownership_horizon["causal_outcome"],
            "access_contract_rows": rows,
            "access_contract_guards": {
                "fixed_a464_grants_replayed_without_rescheduling": True,
                "a4670_canonical_fifo_replayed_exactly_after_each_lifecycle_event": True,
                "a4680_representation_sufficiency_inventory_matched": True,
                "tail_extension_cross_birth_prohibited": True,
                "lifecycle_metadata_and_payload_reference_categories_separated": True,
                "q0_shared_and_large_q_headlocal_endpoints_match": True,
            },
        })
    return {
        "anchor": source_row["anchor"],
        "workload": source_row["workload"],
        "reasoning_priority_row": source_row["workload"] == "reasoning",
        "horizon_rows": horizon_rows,
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a461 = read_completed(args.a461_report, A461_SCHEMA, "A4.6.1")
    a464 = read_completed(args.a464_report, A464_SCHEMA, "A4.6.4")
    a4670 = read_completed(args.a4670_report, A4670_SCHEMA, "A4.6.7.0")
    a4671 = read_completed(args.a4671_report, A4671_SCHEMA, "A4.6.7.1")
    a4680 = read_completed(args.a4680_report, A4680_SCHEMA, "A4.6.8.0")
    source, causal, ownership, tax = validate_chain(a461=a461, a464=a464, a4670=a4670, a4671=a4671, args=args)
    validate_a4680(a4680=a4680, args=args)
    if args.preflight_only:
        print("A4.6.8.1 preflight passed: A4.6.1/A4.6.4/A4.6.7.0/A4.6.7.1/A4.6.8.0 hash chain and representation-sufficiency guards validated; no output created.")
        return
    a4680_rows = {(row["anchor"], row["workload"]): row for row in a4680["anchor_rows"]}
    if set(source) != set(a4680_rows) or len(a4680_rows) != 6:
        raise ValueError("A4.6.8.0 six-row coverage mismatch")
    config = {
        "a461_report": str(args.a461_report),
        "a464_report": str(args.a464_report),
        "a4670_report": str(args.a4670_report),
        "a4671_report": str(args.a4671_report),
        "a4680_report": str(args.a4680_report),
        "evaluation_horizons_append_opportunities": list(HORIZONS),
        "representation": REPRESENTATION,
        "logical_access_contract": {
            "span_create": "One immutable source-affiliation event creates one logical span and records ownership/payload-reference association.",
            "tail_extension": "Legal only for same source, same birth opportunity, and contiguous within-head sequence; never used to merge across births.",
            "partial_dequeue": "Read source front metadata, select the unique oldest front, consume a count, and update remaining/head state.",
            "release": "A zero-count source-front span emits release, ownership-unlink, payload-reference-release, and source-head-update primitives.",
            "oldest_selection": "When both sources are nonempty, record one logical two-front comparison per canonical selection; no scheduler is changed.",
            "ownership_update": "Link/unlink are logical source-affiliation lifecycle primitives only.",
        },
        "payload_boundary": "Payload-reference lifecycle records association only. It must not be converted into K/V movement, reads, writes, bytes, or traffic without a separately declared mapping assumption.",
        "mapping_boundary": "No descriptor/PTE width, physical layout, allocator, payload movement, access width, port, bank, HBM/DMA traffic, bandwidth, cycle, timing, latency, throughput, energy, area, capacity, hardware parameter, architecture specification, or RTL is selected.",
    }
    report = {
        "schema_version": SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model functional replay of trace-derived lifecycle inputs through a hardware-agnostic representation access contract; not measured or modeled physical hardware cost",
        "input_artifacts": {
            "a461_report_sha256": sha256_file(args.a461_report),
            "a464_report_sha256": sha256_file(args.a464_report),
            "a4670_report_sha256": sha256_file(args.a4670_report),
            "a4671_report_sha256": sha256_file(args.a4671_report),
            "a4680_report_sha256": sha256_file(args.a4680_report),
        },
        "primitive_categories": {
            "logical_lifecycle": ["span_create", "tail_extension", "span_partial_dequeue", "span_release"],
            "hardware_agnostic_metadata": ["source_head_metadata_read", "oldest_source_compare", "span_head_remaining_update", "source_head_update", "ownership_link", "ownership_unlink"],
            "payload_reference_lifecycle_not_payload_movement": ["payload_reference_create", "payload_reference_release"],
        },
        "anchor_rows": [
            analyze_row(source_row=source[key], a464_row=causal[key], a4670_row=ownership[key], a4671_row=tax[key], a4680_row=a4680_rows[key])
            for key in sorted(source)
        ],
        "semantic_guards": {
            "complete_hash_chain_validated": True,
            "a4680_representation_sufficiency_gate_required_and_validated": True,
            "fixed_a464_grants_not_rescheduled": True,
            "a4670_canonical_fifo_replayed_after_activation_append_and_dequeue": True,
            "exact_pending_birth_order_oldest_and_source_ownership_reconstructible": True,
            "tail_extension_cross_birth_or_noncontiguous_rejected": True,
            "a4680_span_create_release_inventory_matched": True,
            "lifecycle_metadata_and_payload_reference_categories_separated": True,
            "no_payload_movement_inferred_from_lifecycle_transition": True,
            "no_finite_allocator_migration_drop_fallback_or_backing_action": True,
            "no_model_or_runtime_loaded": True,
            "no_physical_width_byte_port_bank_traffic_cycle_or_hardware_parameter_selected": True,
            "qwen_llama_rows_separate": True,
        },
        "boundaries": [
            "A4.6.8.1 defines a semantics-to-hardware-agnostic access contract only. Its primitive counts are not physical accesses, descriptor/PTE records, bytes, HBM/DMA traffic, bandwidth, cycles, timing, latency, throughput, energy, area, or physical capacity.",
            "Payload-reference create/release describe association lifetime only; no logical lifecycle transition automatically entails K/V read, K/V write, copy, fill, seal, or movement. A later physicalization mapping must make any such relation explicit and falsifiable.",
            "The fixed A4.6.4 grants, A4.6.7.0 source assignment, and A4.6.8.0 representation are inputs. This study neither selects an organization nor models finite capacity, allocator behavior, migration, spill, compaction, DROP, fallback, Full-KV backing, protection, scheduler, physical storage, banking, ports, arbitration, architecture specification, or RTL.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a4681_representation_access_contract_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.8.1 representation-aware access contract completed: {output}")


if __name__ == "__main__":
    main()
