#!/usr/bin/env python3
"""A4.6.8.2.0 phase-aware access-epoch and span-lifetime closure for Route-A.

The replay preserves A4.6.8.1's fixed grants, immutable source ownership, and
canonical FIFO, but emits a compact ordered logical event trace.  Epochs are
logical activation/append/dequeue checkpoints, never hardware cycles or time.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
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
    REPRESENTATION,
    SCHEMA as A4680_SCHEMA,
    a4671_variant,
    prior_horizon,
    prior_variant,
    source_snapshots,
    validate_chain,
)
from tools.analyze_kvzap_route_a4681_representation_access_contract import (
    AccessSpan,
    AccessStatistics,
    SCHEMA as A4681_SCHEMA,
    validate_a4680,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4682-access-epoch-trace-1.0"
TRACE_SCHEMA = "kvzap-route-a4682-access-epoch-trace-record-1.0"
Stream = tuple[int, int]
SOURCES = ("private", "shared")
PHASES = ("activation", "steady_state_append", "steady_state_dequeue")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.6.8.2.0 no-model Route-A access-epoch trace and span-lifetime closure: "
            "fixed A4.6.8.1 grants/FIFO only, with logical checkpoints rather than cycles."
        )
    )
    parser.add_argument("--a461-report", type=Path, required=True)
    parser.add_argument("--a464-report", type=Path, required=True)
    parser.add_argument("--a4670-report", type=Path, required=True)
    parser.add_argument("--a4671-report", type=Path, required=True)
    parser.add_argument("--a4680-report", type=Path, required=True)
    parser.add_argument("--a4681-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate hash-bound reports and guards without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def checkpoint_index(*, phase: str, opportunity: int) -> int:
    """Map a logical phase/opportunity pair to an ordered checkpoint, never time."""
    if phase == "activation" and opportunity == 0:
        return 0
    if phase == "steady_state_append" and opportunity > 0:
        return 2 * opportunity - 1
    if phase == "steady_state_dequeue" and opportunity > 0:
        return 2 * opportunity
    raise ValueError("invalid logical checkpoint")


def percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction)))
    return ordered[index]


def distribution(values: list[int]) -> dict[str, int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "p50": percentile(values, 0.50),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values) if values else None,
        "sum": sum(values),
    }


class AccessEpochTraceWriter:
    """Streaming deterministic compressed trace writer; no payload values are stored."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._raw = path.open("wb")
        self._gzip = gzip.GzipFile(filename="", mode="wb", fileobj=self._raw, mtime=0)
        self._text = io.TextIOWrapper(self._gzip, encoding="utf-8", newline="\n")
        self.record_count = 0

    def record(self, **event: Any) -> None:
        payload = {"schema_version": TRACE_SCHEMA, **event}
        self._text.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        self.record_count += 1

    def close(self) -> None:
        self._text.close()


@dataclass
class SpanLifecycle:
    span_id: int
    source: str
    birth_opportunity: int
    creation_phase: str
    creation_checkpoint: int
    active_checkpoint_count: int = 0
    end_phase: str | None = None
    end_opportunity: int | None = None
    end_checkpoint: int | None = None
    right_censored: bool = False


class LifetimeTracker:
    """Tracks span life in logical checkpoints with explicit right censoring."""

    def __init__(self) -> None:
        self.by_span: dict[int, SpanLifecycle] = {}
        self.completed: list[SpanLifecycle] = []
        self.censored: list[SpanLifecycle] = []

    def create(self, *, span_id: int, source: str, birth_opportunity: int, phase: str, opportunity: int) -> None:
        if span_id in self.by_span:
            raise AssertionError("duplicate span identity")
        self.by_span[span_id] = SpanLifecycle(
            span_id=span_id,
            source=source,
            birth_opportunity=birth_opportunity,
            creation_phase=phase,
            creation_checkpoint=checkpoint_index(phase=phase, opportunity=opportunity),
        )

    def observe_active(self, *, states: dict[Stream, "EpochAccessState"]) -> None:
        for state in states.values():
            for queue in state.sources.values():
                for span in queue:
                    self.by_span[state.span_id(span)].active_checkpoint_count += 1

    def release(self, *, span_id: int, phase: str, opportunity: int) -> SpanLifecycle:
        record = self.by_span[span_id]
        if record.end_checkpoint is not None:
            raise AssertionError("span released twice")
        record.end_phase = phase
        record.end_opportunity = opportunity
        record.end_checkpoint = checkpoint_index(phase=phase, opportunity=opportunity)
        self.completed.append(record)
        return record

    def finalize_censored(self, *, states: dict[Stream, "EpochAccessState"], final_opportunity: int) -> None:
        final_checkpoint = checkpoint_index(phase="steady_state_dequeue", opportunity=final_opportunity)
        for state in states.values():
            for queue in state.sources.values():
                for span in queue:
                    record = self.by_span[state.span_id(span)]
                    if record.end_checkpoint is not None:
                        raise AssertionError("released span remains live")
                    record.end_phase = "steady_state_dequeue"
                    record.end_opportunity = final_opportunity
                    record.end_checkpoint = final_checkpoint
                    record.right_censored = True
                    self.censored.append(record)

    @staticmethod
    def _summary(records: list[SpanLifecycle]) -> dict[str, Any]:
        checkpoint_distance = [item.end_checkpoint - item.creation_checkpoint for item in records if item.end_checkpoint is not None]
        opportunity_distance = [item.end_opportunity - item.birth_opportunity for item in records if item.end_opportunity is not None]
        active_residence = [item.active_checkpoint_count for item in records]
        by_source = {}
        for source in SOURCES:
            source_records = [item for item in records if item.source == source]
            by_source[source] = {
                "span_count": len(source_records),
                "lifetime_checkpoint_distance": distribution([item.end_checkpoint - item.creation_checkpoint for item in source_records if item.end_checkpoint is not None]),
                "lifetime_opportunity_distance": distribution([item.end_opportunity - item.birth_opportunity for item in source_records if item.end_opportunity is not None]),
                "active_span_residence_checkpoints": distribution([item.active_checkpoint_count for item in source_records]),
            }
        return {
            "span_count": len(records),
            "lifetime_checkpoint_distance": distribution(checkpoint_distance),
            "lifetime_opportunity_distance": distribution(opportunity_distance),
            "active_span_residence_checkpoints": distribution(active_residence),
            "by_source": by_source,
        }

    def summary(self) -> dict[str, Any]:
        all_records = self.completed + self.censored
        return {
            "definition": {
                "logical_checkpoint": "activation=0; append(t)=2t-1; dequeue(t)=2t. This is an ordered replay index, not a hardware cycle or elapsed time.",
                "lifetime_checkpoint_distance": "end_checkpoint - creation_checkpoint; release at a later checkpoint gives a positive distance.",
                "lifetime_opportunity_distance": "end_opportunity - birth_opportunity; append and dequeue in the same opportunity have distance zero.",
                "active_span_residence_checkpoints": "Number of post-phase logical checkpoints at which the span remained active; its sum is an active-span checkpoint area, not time or storage bytes.",
                "right_censored": "A span still active after the fixed horizon is reported separately and ends observationally at the final dequeue checkpoint.",
            },
            "completed": self._summary(self.completed),
            "right_censored": self._summary(self.censored),
            "all_observed_spans": self._summary(all_records),
        }


class OccupancyTracker:
    """Tracks phase-separated active-span occupancy and max-plateau duration."""

    def __init__(self) -> None:
        self.per_layer: dict[int, list[dict[str, int | str]]] = defaultdict(list)
        self.global_rows: list[dict[str, int | str]] = []

    def observe(self, *, states: dict[Stream, "EpochAccessState"], phase: str, opportunity: int) -> None:
        index = checkpoint_index(phase=phase, opportunity=opportunity)
        layer_spans: dict[int, int] = defaultdict(int)
        layer_sources: dict[int, int] = defaultdict(int)
        for (layer, _), state in states.items():
            layer_spans[layer] += state.active_spans()
            layer_sources[layer] += state.active_sources()
        for layer in sorted(layer_spans):
            self.per_layer[layer].append({
                "phase": phase,
                "opportunity": opportunity,
                "logical_checkpoint": index,
                "active_spans": layer_spans[layer],
                "active_sources": layer_sources[layer],
            })
        self.global_rows.append({
            "phase": phase,
            "opportunity": opportunity,
            "logical_checkpoint": index,
            "active_spans": sum(layer_spans.values()),
            "active_sources": sum(layer_sources.values()),
        })

    @staticmethod
    def _plateau(rows: list[dict[str, int | str]]) -> dict[str, int | None]:
        values = [int(item["active_spans"]) for item in rows]
        if not values:
            return {"peak_active_spans": 0, "peak_active_span_plateau_max_contiguous_checkpoints": 0, "peak_active_span_plateau_total_checkpoints": 0}
        peak = max(values)
        max_run = 0
        run = 0
        total = 0
        for value in values:
            if value == peak:
                run += 1
                total += 1
                max_run = max(max_run, run)
            else:
                run = 0
        return {
            "peak_active_spans": peak,
            "peak_active_span_plateau_max_contiguous_checkpoints": max_run,
            "peak_active_span_plateau_total_checkpoints": total,
        }

    def summary(self) -> dict[str, Any]:
        per_layer = []
        for layer, rows in sorted(self.per_layer.items()):
            phases = {phase: [row for row in rows if row["phase"] == phase] for phase in PHASES}
            per_layer.append({
                "layer": layer,
                "all_checkpoints": self._plateau(rows),
                "phase_peak_active_spans": {phase: self._plateau(phase_rows)["peak_active_spans"] for phase, phase_rows in phases.items()},
            })
        return {
            "definition": "Peak plateau duration counts contiguous logical replay checkpoints at the row's exact maximum active-span count; it is not time, cycles, latency, or a cache-residency duration.",
            "global_all_layers": self._plateau(self.global_rows),
            "per_layer": per_layer,
        }


class EpochAccessState:
    """A4.6.8.1-equivalent source-span state with identity and event emission."""

    def __init__(self, *, statistics: AccessStatistics, layer: int, kv_head: int, trace: AccessEpochTraceWriter, context: dict[str, Any], lifetimes: LifetimeTracker) -> None:
        self.statistics = statistics
        self.layer = layer
        self.kv_head = kv_head
        self.trace = trace
        self.context = context
        self.lifetimes = lifetimes
        self.sources: dict[str, deque[AccessSpan]] = {source: deque() for source in SOURCES}
        self.live = {source: 0 for source in SOURCES}
        self.next_sequence = 0
        self.created_span_count = 0
        self.released_span_count = 0
        self._span_ids: dict[int, int] = {}

    def span_id(self, span: AccessSpan) -> int:
        return self._span_ids[id(span)]

    @property
    def pending(self) -> int:
        return sum(self.live.values())

    def active_spans(self) -> int:
        return sum(len(queue) for queue in self.sources.values())

    def active_sources(self) -> int:
        return sum(bool(queue) for queue in self.sources.values())

    def _event(self, *, phase: str, opportunity: int, primitive: str, source: str | None, span: AccessSpan | None = None, count: int | None = None, candidate_sources: list[str] | None = None, **extra: Any) -> None:
        event: dict[str, Any] = {
            **self.context,
            "phase": phase,
            "opportunity": opportunity,
            "logical_checkpoint": checkpoint_index(phase=phase, opportunity=opportunity),
            "layer": self.layer,
            "kv_head": self.kv_head,
            "primitive": primitive,
            "source": source,
        }
        if span is not None:
            event.update({
                "span_id": self.span_id(span),
                "birth_opportunity": span.birth_opportunity,
                "within_head_sequence_start": span.sequence_start,
                "span_remaining_count": span.count,
            })
        if count is not None:
            event["logical_count"] = count
        if candidate_sources is not None:
            event["candidate_sources"] = candidate_sources
        event.update(extra)
        self.trace.record(**event)

    def append_from_reference(self, *, events: list[dict[str, int]], birth_opportunity: int, phase: str) -> None:
        for event in events:
            source, count = str(event["source"]), int(event["count"])
            if source not in self.sources or count <= 0:
                raise ValueError("invalid epoch-span creation")
            span = AccessSpan(source, birth_opportunity, self.next_sequence, count)
            self.sources[source].append(span)
            self.live[source] += count
            self.next_sequence += count
            self.created_span_count += 1
            span_id = self.created_span_count + (self.layer << 32) + (self.kv_head << 24)
            if span_id in self.lifetimes.by_span:
                raise AssertionError("span identity collision")
            self._span_ids[id(span)] = span_id
            self.lifetimes.create(span_id=span_id, source=source, birth_opportunity=birth_opportunity, phase=phase, opportunity=birth_opportunity)
            for primitive in ("span_create", "ownership_link", "payload_reference_create"):
                self.statistics.record(phase=phase, layer=self.layer, opportunity=birth_opportunity, name=primitive)
                self._event(phase=phase, opportunity=birth_opportunity, primitive=primitive, source=source, span=span, count=count)

    def oldest_source(self, *, phase: str, opportunity: int) -> str:
        candidates = [source for source in SOURCES if self.sources[source]]
        if not candidates:
            raise ValueError("empty epoch state has no oldest entry")
        for source in candidates:
            span = self.sources[source][0]
            self.statistics.record(phase=phase, layer=self.layer, opportunity=opportunity, name="source_head_metadata_read")
            self._event(phase=phase, opportunity=opportunity, primitive="source_head_metadata_read", source=source, span=span)
        if len(candidates) == 2:
            self.statistics.record(phase=phase, layer=self.layer, opportunity=opportunity, name="oldest_source_compare")
            self._event(phase=phase, opportunity=opportunity, primitive="oldest_source_compare", source=None, candidate_sources=candidates)
        return min(candidates, key=lambda source: self.sources[source][0].key)

    def dequeue(self, *, count: int, phase: str, opportunity: int) -> list[tuple[str, int]]:
        if count < 0 or count > self.pending:
            raise ValueError("invalid epoch access dequeue")
        chunks: list[tuple[str, int]] = []
        while count:
            source = self.oldest_source(phase=phase, opportunity=opportunity)
            span = self.sources[source][0]
            amount = min(count, span.count)
            span.consume(amount)
            self.live[source] -= amount
            count -= amount
            for primitive in ("span_partial_dequeue", "span_head_remaining_update"):
                self.statistics.record(phase=phase, layer=self.layer, opportunity=opportunity, name=primitive)
                self._event(phase=phase, opportunity=opportunity, primitive=primitive, source=source, span=span, count=amount)
            if span.count == 0:
                self.sources[source].popleft()
                self.released_span_count += 1
                lifetime = self.lifetimes.release(span_id=self.span_id(span), phase=phase, opportunity=opportunity)
                for primitive in ("span_release", "ownership_unlink", "payload_reference_release", "source_head_update"):
                    self.statistics.record(phase=phase, layer=self.layer, opportunity=opportunity, name=primitive)
                    self._event(
                        phase=phase, opportunity=opportunity, primitive=primitive, source=source, span=span, count=amount,
                        lifetime_checkpoint_distance=lifetime.end_checkpoint - lifetime.creation_checkpoint,
                        lifetime_opportunity_distance=lifetime.end_opportunity - lifetime.birth_opportunity,
                        active_span_residence_checkpoints=lifetime.active_checkpoint_count,
                    )
            else:
                self.statistics.record(phase=phase, layer=self.layer, opportunity=opportunity, name="source_head_update")
                self._event(phase=phase, opportunity=opportunity, primitive="source_head_update", source=source, span=span, count=amount)
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
                raise AssertionError("epoch trace has ambiguous oldest span")
            output.append((source, span.birth_opportunity, span.sequence_start, span.count))
            offsets[source] += 1


def assert_epoch_state_sufficient(*, reference: PendingOwnershipState, state: EpochAccessState) -> None:
    if state.pending != reference.pending or state.next_sequence != reference.next_sequence:
        raise AssertionError("access-epoch replay lost pending accounting or sequence coverage")
    expected = [(item.birth_opportunity, item.sequence_start, item.count) for item in reference.canonical]
    actual = state.reconstruct_canonical_runs()
    if [(birth, sequence, count) for _, birth, sequence, count in actual] != expected:
        raise AssertionError("access-epoch replay lost exact canonical FIFO order")
    for source in SOURCES:
        actual_source = [(item.birth_opportunity, item.sequence_start, item.count) for item in state.sources[source]]
        if actual_source != source_snapshots(reference)[source]:
            raise AssertionError("access-epoch replay lost source ownership")
    if reference.pending:
        selected = min((source for source in SOURCES if state.sources[source]), key=lambda source: state.sources[source][0].key)
        if state.sources[selected][0].key != reference.canonical[0].key:
            raise AssertionError("access-epoch replay oldest selection differs from canonical FIFO")


def validate_a4681(*, a4681: dict[str, Any], args: argparse.Namespace) -> None:
    expected = {
        "a461_report_sha256": sha256_file(args.a461_report),
        "a464_report_sha256": sha256_file(args.a464_report),
        "a4670_report_sha256": sha256_file(args.a4670_report),
        "a4671_report_sha256": sha256_file(args.a4671_report),
        "a4680_report_sha256": sha256_file(args.a4680_report),
    }
    if any(a4681.get("input_artifacts", {}).get(name) != value for name, value in expected.items()):
        raise ValueError("A4.6.8.1 does not hash-bind supplied inputs")
    required = (
        "complete_hash_chain_validated",
        "a4680_representation_sufficiency_gate_required_and_validated",
        "fixed_a464_grants_not_rescheduled",
        "a4670_canonical_fifo_replayed_after_activation_append_and_dequeue",
        "exact_pending_birth_order_oldest_and_source_ownership_reconstructible",
        "tail_extension_cross_birth_or_noncontiguous_rejected",
        "a4680_span_create_release_inventory_matched",
        "lifecycle_metadata_and_payload_reference_categories_separated",
        "no_payload_movement_inferred_from_lifecycle_transition",
        "no_finite_allocator_migration_drop_fallback_or_backing_action",
        "no_model_or_runtime_loaded",
        "no_physical_width_byte_port_bank_traffic_cycle_or_hardware_parameter_selected",
        "qwen_llama_rows_separate",
    )
    if a4681.get("status") != "complete" or not all(a4681.get("semantic_guards", {}).get(name) is True for name in required):
        raise ValueError("A4.6.8.1 access-contract guards are incomplete")
    if a4681.get("config", {}).get("representation") != REPRESENTATION:
        raise ValueError("A4.6.8.1 representation mismatch")


def reference_operations(states: dict[Stream, PendingOwnershipState]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for state in states.values():
        for name, value in state.operation_counts.items():
            totals[name] += value
    return dict(sorted(totals.items()))


def phase_counts(statistics: AccessStatistics) -> dict[str, dict[str, int]]:
    return {phase: dict(sorted(statistics.by_phase[phase].items())) for phase in PHASES}


def simulate_variant(
    *, inventory: dict[Stream, dict[str, int]], arrivals: dict[Stream, list[int]],
    fixed_schedule: list[dict[Stream, tuple[int, int, int]]], organization: str,
    private_quota: int | None, trace: AccessEpochTraceWriter, context: dict[str, Any],
) -> dict[str, Any]:
    references = {key: PendingOwnershipState(organization=organization, private_quota=private_quota) for key in sorted(inventory)}
    statistics = AccessStatistics()
    lifetimes = LifetimeTracker()
    states = {
        key: EpochAccessState(statistics=statistics, layer=key[0], kv_head=key[1], trace=trace, context=context, lifetimes=lifetimes)
        for key in sorted(inventory)
    }
    occupancy = OccupancyTracker()
    checkpoints = {"after_activation": 0, "after_append": 0, "after_dequeue": 0}
    trace_start = trace.record_count
    for key, reference in references.items():
        events = reference.enqueue(count=inventory[key]["pending"], birth_opportunity=0)
        states[key].append_from_reference(events=events, birth_opportunity=0, phase="activation")
        assert_epoch_state_sufficient(reference=reference, state=states[key])
        checkpoints["after_activation"] += 1
    lifetimes.observe_active(states=states)
    occupancy.observe(states=states, phase="activation", opportunity=0)
    for index, schedule in enumerate(fixed_schedule):
        opportunity = index + 1
        for key, reference in references.items():
            events = reference.enqueue(count=arrivals[key][index], birth_opportunity=opportunity)
            states[key].append_from_reference(events=events, birth_opportunity=opportunity, phase="steady_state_append")
            expected_pre, _, _ = schedule[key]
            if reference.pending != expected_pre:
                raise AssertionError("access-epoch append changed fixed pre-grant pending")
            assert_epoch_state_sufficient(reference=reference, state=states[key])
            checkpoints["after_append"] += 1
        lifetimes.observe_active(states=states)
        occupancy.observe(states=states, phase="steady_state_append", opportunity=opportunity)
        for key, reference in references.items():
            _, grant, expected_post = schedule[key]
            reference_chunks = [(str(item["source"]), int(item["count"])) for item in reference.dequeue(count=grant)]
            epoch_chunks = states[key].dequeue(count=grant, phase="steady_state_dequeue", opportunity=opportunity)
            if epoch_chunks != reference_chunks:
                raise AssertionError("access-epoch dequeue differs from A4.6.7.0 canonical FIFO")
            if reference.pending != expected_post:
                raise AssertionError("access-epoch dequeue changed fixed post-grant pending")
            assert_epoch_state_sufficient(reference=reference, state=states[key])
            checkpoints["after_dequeue"] += 1
        lifetimes.observe_active(states=states)
        occupancy.observe(states=states, phase="steady_state_dequeue", opportunity=opportunity)
    lifetimes.finalize_censored(states=states, final_opportunity=len(fixed_schedule))
    created = sum(state.created_span_count for state in states.values())
    released = sum(state.released_span_count for state in states.values())
    operations = reference_operations(references)
    if created != sum(value for name, value in operations.items() if name.endswith("_enqueue_segment_count")):
        raise AssertionError("source-affiliation enqueue segments and created spans differ")
    if released != sum(value for name, value in operations.items() if name.endswith("_release_segment_count")):
        raise AssertionError("source-affiliation releases and released spans differ")
    return {
        "trace_record_count": trace.record_count - trace_start,
        "fixed_access_contract_equivalence": {
            "current_pending_birth_order_oldest_and_source_reconstructed_after_each_event": True,
            "fixed_dequeue_chunks_match_a4670_canonical_fifo": True,
            "source_residence_immutable_no_migration": True,
            "checkpoints": checkpoints,
        },
        "reference_logical_queue_operations": operations,
        "representation_lifecycle_inventory": {
            "span_create_count": created,
            "tail_extension_count": 0,
            "span_release_count": released,
            "tail_extension_rule": "same_source + same_birth_opportunity + sequence_contiguous only; no fixed replay tail extension or cross-birth merge exists",
        },
        "phase_primitive_counts": phase_counts(statistics),
        "span_lifetime": lifetimes.summary(),
        "phase_separated_active_span_occupancy": occupancy.summary(),
        "terminal_pending": sum(state.pending for state in states.values()),
    }


def a4681_horizon(row: dict[str, Any], horizon: int) -> dict[str, Any]:
    return next(item for item in row["horizon_rows"] if int(item["evaluation_horizon_append_opportunities"]) == horizon)


def a4681_variant(row: dict[str, Any], label: str) -> dict[str, Any]:
    return next(item for item in row["access_contract_rows"] if item["label"] == label)


def endpoint_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference_logical_queue_operations": row["reference_logical_queue_operations"],
        "representation_lifecycle_inventory": row["representation_lifecycle_inventory"],
        "phase_primitive_counts": row["phase_primitive_counts"],
        "span_lifetime": row["span_lifetime"],
        "phase_separated_active_span_occupancy": row["phase_separated_active_span_occupancy"],
        "terminal_pending": row["terminal_pending"],
    }


def analyze_row(
    *, source_row: dict[str, Any], a464_row: dict[str, Any], a4670_row: dict[str, Any],
    a4671_row: dict[str, Any], a4680_row: dict[str, Any], a4681_row: dict[str, Any],
    trace: AccessEpochTraceWriter,
) -> dict[str, Any]:
    inventory, arrivals = source_streams(source_row)
    a4680_horizons = {int(item["evaluation_horizon_append_opportunities"]): item for item in a4680_row["horizon_rows"]}
    horizon_rows = []
    for horizon in HORIZONS:
        observed = run_causal_observer(inventory=inventory, arrivals=arrivals, horizon=horizon)
        validate_against_a464(observed, expected_a464(a464_row, horizon))
        ownership_horizon = prior_horizon(a4670_row, horizon)
        tax_horizon = prior_horizon(a4671_row, horizon)
        representation_horizon = a4680_horizons[horizon]
        access_horizon = a4681_horizon(a4681_row, horizon)
        fixed_schedule = derive_fixed_grants(observed=observed, arrivals=arrivals)
        access_by_label = {item["label"]: item for item in access_horizon["access_contract_rows"]}
        span_by_label = {item["label"]: item for item in representation_horizon["representation_rows"]}
        rows = []
        for variant in organization_variants(observed):
            context = {
                "anchor": source_row["anchor"],
                "workload": source_row["workload"],
                "evaluation_horizon_append_opportunities": horizon,
                "organization_label": variant["label"],
                "organization": variant["organization"],
                "private_quota_per_head": variant["private_quota"],
            }
            result = simulate_variant(
                inventory=inventory, arrivals=arrivals, fixed_schedule=fixed_schedule,
                organization=variant["organization"], private_quota=variant["private_quota"], trace=trace, context=context,
            )
            ownership = prior_variant(ownership_horizon, variant["label"])
            access = access_by_label[variant["label"]]
            span = span_by_label[variant["label"]]["lossless_span_inventory"]
            lifecycle = result["representation_lifecycle_inventory"]
            if result["reference_logical_queue_operations"] != ownership["global_logical_queue_operations"]:
                raise AssertionError("A4.6.8.2.0 reference operations disagree with A4.6.7.0")
            if lifecycle["span_create_count"] != span["span_created_count"] or lifecycle["span_release_count"] != span["span_released_count"]:
                raise AssertionError("A4.6.8.2.0 span inventory disagrees with A4.6.8.0")
            expected_phase = {
                phase: access["hardware_agnostic_access_pressure"][phase]["logical_primitive_counts"]
                for phase in PHASES
            }
            if result["phase_primitive_counts"] != expected_phase:
                raise AssertionError("A4.6.8.2.0 event trace primitive totals disagree with A4.6.8.1")
            tax = a4671_variant(tax_horizon, variant["label"])
            rows.append({
                "label": variant["label"],
                "organization": variant["organization"],
                "private_quota_per_head": variant["private_quota"],
                "semantic_endpoint_only": variant["semantic_endpoint_only"],
                "representation": REPRESENTATION,
                "a4671_capacity_recovery_context": tax["logical_capacity_recovery_context"],
                "a4681_access_contract_totals_matched": True,
                **result,
            })
        by_label = {row["label"]: row for row in rows}
        if endpoint_payload(by_label["layer_shared_unbounded"]) != endpoint_payload(by_label["hierarchical_q0_shared_endpoint"]):
            raise AssertionError("q=0 endpoint changed access-epoch/lifetime state")
        if endpoint_payload(by_label["head_local_private_unbounded"]) != endpoint_payload(by_label["hierarchical_qpeak_head_local_endpoint"]):
            raise AssertionError("large-q endpoint changed access-epoch/lifetime state")
        horizon_rows.append({
            "evaluation_horizon_append_opportunities": horizon,
            "horizon_completion_state": tax_horizon["horizon_completion_state"],
            "fixed_causal_outcome": ownership_horizon["causal_outcome"],
            "access_epoch_rows": rows,
            "access_epoch_guards": {
                "fixed_a464_grants_replayed_without_rescheduling": True,
                "a4670_canonical_fifo_replayed_after_each_event": True,
                "a4680_span_inventory_matched": True,
                "a4681_primitive_totals_matched_phase_by_phase": True,
                "completed_and_right_censored_lifetimes_separated": True,
                "phase_separated_occupancy_and_peak_plateau_recorded": True,
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
    a4681 = read_completed(args.a4681_report, A4681_SCHEMA, "A4.6.8.1")
    source, causal, ownership, tax = validate_chain(a461=a461, a464=a464, a4670=a4670, a4671=a4671, args=args)
    validate_a4680(a4680=a4680, args=args)
    validate_a4681(a4681=a4681, args=args)
    a4680_rows = {(row["anchor"], row["workload"]): row for row in a4680["anchor_rows"]}
    a4681_rows = {(row["anchor"], row["workload"]): row for row in a4681["anchor_rows"]}
    if set(source) != set(a4680_rows) or set(source) != set(a4681_rows) or len(source) != 6:
        raise ValueError("A4.6.8.0/A4.6.8.1 six-row coverage mismatch")
    if args.preflight_only:
        print("A4.6.8.2.0 preflight passed: A4.6.1/A4.6.4/A4.6.7.0/A4.6.7.1/A4.6.8.0/A4.6.8.1 hash chain and semantic guards validated; no output created.")
        return
    config = {
        "a461_report": str(args.a461_report),
        "a464_report": str(args.a464_report),
        "a4670_report": str(args.a4670_report),
        "a4671_report": str(args.a4671_report),
        "a4680_report": str(args.a4680_report),
        "a4681_report": str(args.a4681_report),
        "evaluation_horizons_append_opportunities": list(HORIZONS),
        "representation": REPRESENTATION,
        "logical_access_epoch": "activation=0; append(t)=2t-1; dequeue(t)=2t. Epoch order is replay bookkeeping only, never a cycle, wall-clock duration, latency, or throughput measure.",
        "span_lifetime": "Span life begins at immutable source-affiliation create and ends at release; spans live at the fixed horizon are right-censored. Active-span residence counts post-phase logical checkpoints only.",
        "event_trace": "One ordered record per A4.6.8.1 logical primitive, retaining phase/opportunity/layer/head/source/span identity but no token text, K/V payload, bytes, or physical address.",
        "boundary": "No descriptor width, physical record, metadata/payload movement, byte count, access width, port, bank, traffic, cycle, timing, latency, throughput, energy, area, finite capacity, hardware parameter, architecture specification, or RTL is selected.",
    }
    args.output_dir.mkdir(parents=True)
    trace_path = args.output_dir / "a4682_access_epoch_trace.jsonl.gz"
    trace = AccessEpochTraceWriter(trace_path)
    try:
        anchor_rows = [
            analyze_row(
                source_row=source[key], a464_row=causal[key], a4670_row=ownership[key], a4671_row=tax[key],
                a4680_row=a4680_rows[key], a4681_row=a4681_rows[key], trace=trace,
            )
            for key in sorted(source)
        ]
    finally:
        trace.close()
    report = {
        "schema_version": SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model functional ordered event replay over trace-derived lifecycle inputs; logical checkpoint/lifetime statistics are neither measured time nor modeled physical hardware cost",
        "input_artifacts": {
            "a461_report_sha256": sha256_file(args.a461_report),
            "a464_report_sha256": sha256_file(args.a464_report),
            "a4670_report_sha256": sha256_file(args.a4670_report),
            "a4671_report_sha256": sha256_file(args.a4671_report),
            "a4680_report_sha256": sha256_file(args.a4680_report),
            "a4681_report_sha256": sha256_file(args.a4681_report),
        },
        "access_epoch_trace": {
            "schema_version": TRACE_SCHEMA,
            "relative_path": trace_path.name,
            "sha256": sha256_file(trace_path),
            "record_count": trace.record_count,
            "contains": ["logical lifecycle primitives", "hardware-agnostic metadata primitives", "payload-reference lifecycle only", "span identity", "logical phase/opportunity/layer/head/source order"],
            "does_not_contain_or_imply": ["token text", "K/V payload", "payload movement", "physical address", "descriptor/PTE width", "bytes", "HBM/DMA traffic", "ports", "banks", "cycles", "latency", "throughput", "energy", "area"],
        },
        "anchor_rows": anchor_rows,
        "semantic_guards": {
            "complete_hash_chain_validated": True,
            "a4681_access_contract_required_and_validated": True,
            "fixed_a464_grants_not_rescheduled": True,
            "a4670_canonical_fifo_replayed_after_each_event": True,
            "exact_pending_birth_order_oldest_and_source_ownership_reconstructible": True,
            "a4680_span_create_release_inventory_matched": True,
            "a4681_primitive_totals_matched_phase_by_phase": True,
            "completed_and_right_censored_span_lifetimes_separated": True,
            "active_span_residence_and_peak_plateau_use_logical_checkpoints_only": True,
            "tail_extension_cross_birth_or_noncontiguous_not_introduced": True,
            "no_payload_movement_inferred_from_lifecycle": True,
            "no_finite_allocator_migration_drop_fallback_or_backing_action": True,
            "no_model_or_runtime_loaded": True,
            "no_physical_width_byte_port_bank_traffic_cycle_or_hardware_parameter_selected": True,
            "qwen_llama_rows_separate": True,
        },
        "boundaries": [
            "The event trace is a lossless ordered functional replay input for a later metadata organization study. Primitive records and logical checkpoints are not physical accesses, records, descriptor/PTE widths, bytes, payload movement, HBM/DMA traffic, ports, banks, cycles, timing, latency, throughput, energy, area, or capacity.",
            "Span lifetime, active-span residence, and peak plateau are logical checkpoint statistics. They do not establish elapsed time, hardware cache residency time, metadata-cache benefit, descriptor retention policy, or a physical storage requirement.",
            "No lifecycle transition automatically becomes K/V movement. The fixed grant/FIFO/source assignment is preserved; there is no allocator, finite capacity, migration, spill, compaction, DROP, fallback, Full-KV backing, protection, scheduler, banking/port model, architecture specification, or RTL.",
        ],
    }
    output = args.output_dir / "a4682_access_epoch_trace_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.8.2.0 access-epoch trace closure completed: {output}")


if __name__ == "__main__":
    main()
