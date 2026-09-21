#!/usr/bin/env python3
"""A4.6.8.0 exact-sufficiency gate for Route-A pending span representations.

The study uses a birth-ordered source-span representation.  A span retains
source, immutable birth opportunity, within-head sequence start, and count;
therefore it is a lossless logical compression of same-birth contiguous entries,
not a physical descriptor or PTE proposal.
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
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4680-pending-representation-sufficiency-1.0"
REPRESENTATION = "birth_ordered_source_span_v1"
RowKey = tuple[str, str]
Stream = tuple[int, int]
REQUIRED_VARIANTS = {
    "head_local_private_unbounded",
    "layer_shared_unbounded",
    "hierarchical_q0_shared_endpoint",
    "hierarchical_q128",
    "hierarchical_q256",
    "hierarchical_q512",
    "hierarchical_qpeak_head_local_endpoint",
}
REQUIRED_A4670_GUARDS = (
    "complete_hash_binding_validated",
    "fixed_a464_grants_derived_not_rescheduled",
    "a464_a465_a466_replay_matches_each_horizon",
    "per_head_birth_order_fifo_exact",
    "cross_source_oldest_entry_selection_enforced",
    "source_age_inversion_rejected",
    "private_shared_migration_prohibited",
    "q0_shared_and_large_q_headlocal_degeneracy_validated",
    "no_finite_capacity_allocator_drop_fallback_or_backing_action",
    "qwen_llama_rows_separate",
    "no_model_or_runtime_loaded",
    "no_hardware_parameter_selected",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.6.8.0 no-model Route-A birth-ordered source-span representation sufficiency gate; "
            "fixed grants/FIFO only, with no descriptor width, allocator, banking, DROP, fallback, "
            "model, or hardware selection."
        )
    )
    parser.add_argument("--a461-report", type=Path, required=True)
    parser.add_argument("--a464-report", type=Path, required=True)
    parser.add_argument("--a4670-report", type=Path, required=True)
    parser.add_argument("--a4671-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate the hash-bound input chain without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


@dataclass
class SpanDescriptor:
    source: str
    birth_opportunity: int
    sequence_start: int
    count: int

    @property
    def key(self) -> tuple[int, int]:
        return self.birth_opportunity, self.sequence_start

    def consume(self, count: int) -> None:
        if count <= 0 or count > self.count:
            raise ValueError("invalid span consumption")
        self.sequence_start += count
        self.count -= count


class BirthOrderedSourceSpanRepresentation:
    """Lossless per-head representation made only of immutable birth/source spans."""

    def __init__(self) -> None:
        self.sources: dict[str, deque[SpanDescriptor]] = {"private": deque(), "shared": deque()}
        self.live = {"private": 0, "shared": 0}
        self.next_sequence = 0
        self.created_span_count = 0
        self.released_span_count = 0
        self.max_active_spans = 0
        self.max_active_sources = 0

    @property
    def pending(self) -> int:
        return self.live["private"] + self.live["shared"]

    def active_spans(self) -> int:
        return len(self.sources["private"]) + len(self.sources["shared"])

    def active_sources(self) -> int:
        return sum(bool(self.sources[source]) for source in self.sources)

    def enqueue_from_reference(self, *, events: list[dict[str, int]], birth_opportunity: int) -> None:
        """Consume the already-validated A4.6.7.0 source assignment, not a new policy."""
        for event in events:
            source, count = str(event["source"]), int(event["count"])
            if source not in self.sources or count <= 0 or birth_opportunity < 0:
                raise ValueError("invalid source-span enqueue")
            descriptor = SpanDescriptor(source=source, birth_opportunity=birth_opportunity, sequence_start=self.next_sequence, count=count)
            self.sources[source].append(descriptor)
            self.live[source] += count
            self.next_sequence += count
            self.created_span_count += 1
        self.max_active_spans = max(self.max_active_spans, self.active_spans())
        self.max_active_sources = max(self.max_active_sources, self.active_sources())

    def reconstruct_canonical_runs(self) -> list[tuple[str, int, int, int]]:
        """Merge source fronts by exact immutable key without consuming state."""
        offsets = {source: 0 for source in self.sources}
        output: list[tuple[str, int, int, int]] = []
        while True:
            candidates = []
            for source, queue in self.sources.items():
                index = offsets[source]
                if index < len(queue):
                    candidates.append((queue[index].key, source, queue[index]))
            if not candidates:
                return output
            _, source, descriptor = min(candidates, key=lambda item: item[0])
            if sum(item[0] == descriptor.key for item in candidates) != 1:
                raise AssertionError("birth/sequence key must identify a unique oldest entry")
            output.append((source, descriptor.birth_opportunity, descriptor.sequence_start, descriptor.count))
            offsets[source] += 1

    def oldest(self) -> tuple[str, int, int]:
        candidates = [(queue[0].key, source) for source, queue in self.sources.items() if queue]
        if not candidates:
            raise ValueError("empty representation has no oldest entry")
        key, source = min(candidates, key=lambda item: item[0])
        if sum(item[0] == key for item in candidates) != 1:
            raise AssertionError("oldest entry is ambiguous")
        return source, key[0], key[1]

    def dequeue(self, *, count: int) -> list[tuple[str, int]]:
        if count < 0 or count > self.pending:
            raise ValueError("invalid representation dequeue")
        chunks: list[tuple[str, int]] = []
        while count:
            source, _, _ = self.oldest()
            descriptor = self.sources[source][0]
            amount = min(count, descriptor.count)
            descriptor.consume(amount)
            self.live[source] -= amount
            count -= amount
            if descriptor.count == 0:
                self.sources[source].popleft()
                self.released_span_count += 1
            chunks.append((source, amount))
        return chunks


class SourceCountOnlyNegativeControl:
    """Deliberately lossy source totals: it must never satisfy the sufficiency gate."""

    def __init__(self) -> None:
        self.live = {"private": 0, "shared": 0}

    def enqueue(self, source: str, count: int) -> None:
        self.live[source] += count

    def dequeue(self, source: str, count: int) -> None:
        self.live[source] -= count

    def oldest(self) -> None:
        raise ValueError("source counts omit immutable birth/order and cannot identify oldest entry")


def source_snapshots(state: PendingOwnershipState) -> dict[str, list[tuple[int, int, int]]]:
    return {
        source: [(segment.birth_opportunity, segment.sequence_start, segment.count) for segment in state.sources[source]]
        for source in ("private", "shared")
    }


def assert_representation_sufficient(*, reference: PendingOwnershipState, representation: BirthOrderedSourceSpanRepresentation) -> None:
    """Prove all semantic information needed by FIFO exists in the span representation."""
    if representation.pending != reference.pending:
        raise AssertionError("representation cannot reconstruct current pending cardinality")
    if representation.next_sequence != reference.next_sequence:
        raise AssertionError("representation lost within-head sequence coverage")
    reconstructed = representation.reconstruct_canonical_runs()
    canonical = [(segment.birth_opportunity, segment.sequence_start, segment.count) for segment in reference.canonical]
    if [(birth, sequence, count) for _, birth, sequence, count in reconstructed] != canonical:
        raise AssertionError("representation cannot reconstruct exact canonical birth/order runs")
    for source in ("private", "shared"):
        actual = [(item.birth_opportunity, item.sequence_start, item.count) for item in representation.sources[source]]
        if actual != source_snapshots(reference)[source]:
            raise AssertionError("representation cannot reconstruct source ownership runs")
    if reference.pending:
        source, birth, sequence = representation.oldest()
        expected = reference.canonical[0]
        if (birth, sequence) != expected.key:
            raise AssertionError("representation cannot reconstruct canonical oldest entry")
        if reference.sources[source][0].key != expected.key:
            raise AssertionError("representation selected a source that does not own canonical oldest")


def run_negative_control() -> bool:
    """Show source totals alone fail the old-shared/new-private counterexample."""
    control = SourceCountOnlyNegativeControl()
    control.enqueue("private", 2)
    control.enqueue("shared", 3)
    control.dequeue("private", 2)
    control.dequeue("shared", 1)
    control.enqueue("private", 2)  # New private entries; older shared entries remain.
    try:
        control.oldest()
    except ValueError:
        return True
    return False


def operation_counts(states: dict[Stream, PendingOwnershipState]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for state in states.values():
        for name, value in state.operation_counts.items():
            totals[name] += value
    return dict(sorted(totals.items()))


def prior_horizon(row: dict[str, Any], horizon: int) -> dict[str, Any]:
    return next(item for item in row["horizon_rows"] if int(item["evaluation_horizon_append_opportunities"]) == horizon)


def a4671_variant(row: dict[str, Any], label: str) -> dict[str, Any]:
    return next(item for item in row["organization_tax_capacity_rows"] if item["label"] == label)


def prior_variant(row: dict[str, Any], label: str) -> dict[str, Any]:
    return next(item for item in row["ownership_variants"] if item["label"] == label)


def validate_chain(*, a461: dict[str, Any], a464: dict[str, Any], a4670: dict[str, Any], a4671: dict[str, Any], args: argparse.Namespace) -> tuple[dict[RowKey, dict[str, Any]], dict[RowKey, dict[str, Any]], dict[RowKey, dict[str, Any]], dict[RowKey, dict[str, Any]]]:
    hashes = a4670.get("input_artifacts", {})
    if hashes.get("a461_report_sha256") != sha256_file(args.a461_report) or hashes.get("a464_report_sha256") != sha256_file(args.a464_report):
        raise ValueError("A4.6.7.0 does not hash-bind supplied A4.6.1/A4.6.4 reports")
    if a4671.get("input_artifacts", {}).get("a4670_report_sha256") != sha256_file(args.a4670_report):
        raise ValueError("A4.6.7.1 does not hash-bind supplied A4.6.7.0 report")
    for name, value in hashes.items():
        if name.endswith("_sha256") and name in a4671.get("input_artifacts", {}) and a4671["input_artifacts"][name] != value:
            raise ValueError("A4.6.7.0/A4.6.7.1 upstream hash-binding mismatch")
    if not all(a4670.get("semantic_guards", {}).get(name) is True for name in REQUIRED_A4670_GUARDS):
        raise ValueError("A4.6.7.0 semantic guards are incomplete")
    if not all(a4671.get("semantic_guards", {}).values()):
        raise ValueError("A4.6.7.1 semantic guards are incomplete")
    source = {(row["anchor"], row["workload"]): row for row in a461["anchor_rows"]}
    causal = {(row["anchor"], row["workload"]): row for row in a464["anchor_rows"]}
    ownership = {(row["anchor"], row["workload"]): row for row in a4670["anchor_rows"]}
    tax = {(row["anchor"], row["workload"]): row for row in a4671["anchor_rows"]}
    if len(source) != 6 or set(source) != set(causal) or set(source) != set(ownership) or set(source) != set(tax):
        raise ValueError("A4.6.1/A4.6.4/A4.6.7.0/A4.6.7.1 six-row coverage mismatch")
    return source, causal, ownership, tax


def simulate_variant(*, inventory: dict[Stream, dict[str, int]], arrivals: dict[Stream, list[int]], fixed_schedule: list[dict[Stream, tuple[int, int, int]]], organization: str, private_quota: int | None) -> dict[str, Any]:
    references = {key: PendingOwnershipState(organization=organization, private_quota=private_quota) for key in sorted(inventory)}
    representations = {key: BirthOrderedSourceSpanRepresentation() for key in sorted(inventory)}
    checkpoints = {"after_activation": 0, "after_append": 0, "after_dequeue": 0}
    for key, reference in references.items():
        events = reference.enqueue(count=inventory[key]["pending"], birth_opportunity=0)
        representations[key].enqueue_from_reference(events=events, birth_opportunity=0)
        assert_representation_sufficient(reference=reference, representation=representations[key])
        checkpoints["after_activation"] += 1
    for index, schedule in enumerate(fixed_schedule):
        opportunity = index + 1
        for key, reference in references.items():
            events = reference.enqueue(count=arrivals[key][index], birth_opportunity=opportunity)
            representations[key].enqueue_from_reference(events=events, birth_opportunity=opportunity)
            expected_pre, _, _ = schedule[key]
            if reference.pending != expected_pre:
                raise AssertionError("reference enqueue changed fixed pre-grant pending")
            assert_representation_sufficient(reference=reference, representation=representations[key])
            checkpoints["after_append"] += 1
        for key, reference in references.items():
            _, grant, expected_post = schedule[key]
            reference_chunks = [(str(item["source"]), int(item["count"])) for item in reference.dequeue(count=grant)]
            representation_chunks = representations[key].dequeue(count=grant)
            if representation_chunks != reference_chunks:
                raise AssertionError("span representation dequeue disagrees with A4.6.7.0 canonical FIFO")
            if reference.pending != expected_post:
                raise AssertionError("reference dequeue changed fixed post-grant pending")
            assert_representation_sufficient(reference=reference, representation=representations[key])
            checkpoints["after_dequeue"] += 1
    reference_operations = operation_counts(references)
    span_created = sum(item.created_span_count for item in representations.values())
    span_released = sum(item.released_span_count for item in representations.values())
    token_units = sum(value for name, value in reference_operations.items() if name.endswith("_enqueue_token_units"))
    if span_created != sum(value for name, value in reference_operations.items() if name.endswith("_enqueue_segment_count")):
        raise AssertionError("one source-affiliation enqueue segment must create one lossless span")
    if span_released != sum(value for name, value in reference_operations.items() if name.endswith("_release_segment_count")):
        raise AssertionError("one released source-affiliation segment must release one lossless span")
    return {
        "reference_operations": reference_operations,
        "span_created_count": span_created,
        "span_released_count": span_released,
        "per_token_entry_reference_unit_count": token_units,
        "logical_entries_per_created_span": token_units / span_created if span_created else None,
        "peak_active_spans_one_head": max(item.max_active_spans for item in representations.values()),
        "peak_active_sources_one_head": max(item.max_active_sources for item in representations.values()),
        "terminal_pending": sum(item.pending for item in representations.values()),
        "sufficiency_checkpoints": checkpoints,
    }


def endpoint_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("reference_operations", "span_created_count", "span_released_count", "per_token_entry_reference_unit_count", "logical_entries_per_created_span", "peak_active_spans_one_head", "peak_active_sources_one_head", "terminal_pending")}


def analyze_row(*, source_row: dict[str, Any], a464_row: dict[str, Any], a4670_row: dict[str, Any], a4671_row: dict[str, Any]) -> dict[str, Any]:
    inventory, arrivals = source_streams(source_row)
    horizon_rows = []
    for horizon in HORIZONS:
        observed = run_causal_observer(inventory=inventory, arrivals=arrivals, horizon=horizon)
        validate_against_a464(observed, expected_a464(a464_row, horizon))
        ownership_horizon = prior_horizon(a4670_row, horizon)
        tax_horizon = prior_horizon(a4671_row, horizon)
        if ownership_horizon["causal_outcome"] != {field: observed[field] for field in ("B_max", "B_final", "deadline_miss_head_count", "T_drain")}:
            raise ValueError("A4.6.7.0 causal outcome mismatch")
        fixed_schedule = derive_fixed_grants(observed=observed, arrivals=arrivals)
        representation_rows = []
        for variant in organization_variants(observed):
            result = simulate_variant(inventory=inventory, arrivals=arrivals, fixed_schedule=fixed_schedule, organization=variant["organization"], private_quota=variant["private_quota"])
            prior = prior_variant(ownership_horizon, variant["label"])
            if result["reference_operations"] != prior["global_logical_queue_operations"]:
                raise AssertionError("A4.6.8.0 reference operations disagree with A4.6.7.0")
            tax = a4671_variant(tax_horizon, variant["label"])
            tax_creation = tax["logical_management_primitive_inventory"]["logical_source_affiliation_creation"]
            tax_release = tax["logical_management_primitive_inventory"]["logical_source_affiliation_release"]
            if result["span_created_count"] != tax_creation["total_enqueue_segment_count"] or result["span_released_count"] != tax_release["total_release_segment_count"]:
                raise AssertionError("A4.6.8.0 span inventory disagrees with A4.6.7.1")
            representation_rows.append({
                "label": variant["label"],
                "organization": variant["organization"],
                "private_quota_per_head": variant["private_quota"],
                "semantic_endpoint_only": variant["semantic_endpoint_only"],
                "representation": REPRESENTATION,
                "representation_sufficiency_gate": {
                    "current_pending_set_reconstructed": True,
                    "exact_birth_order_reconstructed": True,
                    "oldest_entry_unambiguous_and_exact": True,
                    "source_ownership_reconstructed": True,
                    "fixed_dequeue_replay_matches_a4670_canonical_fifo": True,
                    "source_residence_immutable": True,
                    "checkpoints": result.pop("sufficiency_checkpoints"),
                },
                "lossless_span_inventory": result,
                "a4671_capacity_recovery_context": tax["logical_capacity_recovery_context"],
            })
        by_label = {item["label"]: item for item in representation_rows}
        if endpoint_payload(by_label["layer_shared_unbounded"]["lossless_span_inventory"]) != endpoint_payload(by_label["hierarchical_q0_shared_endpoint"]["lossless_span_inventory"]):
            raise AssertionError("q=0 endpoint changed shared representation inventory")
        if endpoint_payload(by_label["head_local_private_unbounded"]["lossless_span_inventory"]) != endpoint_payload(by_label["hierarchical_qpeak_head_local_endpoint"]["lossless_span_inventory"]):
            raise AssertionError("large-q endpoint changed head-local representation inventory")
        horizon_rows.append({
            "evaluation_horizon_append_opportunities": horizon,
            "horizon_completion_state": tax_horizon["horizon_completion_state"],
            "fixed_causal_outcome": ownership_horizon["causal_outcome"],
            "representation_rows": representation_rows,
            "representation_sufficiency_guards": {
                "a464_fixed_grants_replayed_without_rescheduling": True,
                "a4670_canonical_fifo_operations_match": True,
                "a4671_span_creation_release_inventory_match": True,
                "q0_shared_and_large_q_headlocal_endpoints_match": True,
                "source_count_only_negative_control_rejected": True,
            },
        })
    return {"anchor": source_row["anchor"], "workload": source_row["workload"], "reasoning_priority_row": source_row["workload"] == "reasoning", "horizon_rows": horizon_rows}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a461 = read_completed(args.a461_report, A461_SCHEMA, "A4.6.1")
    a464 = read_completed(args.a464_report, A464_SCHEMA, "A4.6.4")
    a4670 = read_completed(args.a4670_report, A4670_SCHEMA, "A4.6.7.0")
    a4671 = read_completed(args.a4671_report, A4671_SCHEMA, "A4.6.7.1")
    source, causal, ownership, tax = validate_chain(a461=a461, a464=a464, a4670=a4670, a4671=a4671, args=args)
    if not run_negative_control():
        raise AssertionError("source-count-only negative control was not rejected")
    if args.preflight_only:
        print("A4.6.8.0 preflight passed: A4.6.1/A4.6.4/A4.6.7.0/A4.6.7.1 hash chain, guards, and lossiness negative control validated; no output created.")
        return
    config = {
        "a461_report": str(args.a461_report),
        "a464_report": str(args.a464_report),
        "a4670_report": str(args.a4670_report),
        "a4671_report": str(args.a4671_report),
        "evaluation_horizons_append_opportunities": list(HORIZONS),
        "representation": "Per-head private/shared source queues of immutable (source, birth_opportunity, within_head_sequence_start, count) spans. A span may represent only same-source, same-birth, contiguous sequence entries.",
        "sufficiency_gate": "After activation, every append, and every fixed dequeue, reconstruct pending runs, exact birth/order, source ownership, and unique oldest entry; replay must exactly match A4.6.7.0 canonical FIFO chunks.",
        "negative_control": "Source totals without birth/order are rejected by an old-shared/new-private counterexample; lower metadata is invalid if it loses oldest-entry semantics.",
        "mapping_boundary": "Span counts are logical candidate record counts only. No descriptor/PTE width, byte count, allocator, payload movement, access, port, bank, traffic, cycle, or hardware cost is assigned.",
    }
    report = {
        "schema_version": SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model functional representation-sufficiency replay over fixed causal grants and trace-derived lifecycle inputs; not measured or modeled physical hardware cost",
        "input_artifacts": {
            "a461_report_sha256": sha256_file(args.a461_report),
            "a464_report_sha256": sha256_file(args.a464_report),
            "a4670_report_sha256": sha256_file(args.a4670_report),
            "a4671_report_sha256": sha256_file(args.a4671_report),
        },
        "negative_control": {"source_count_only_representation_rejected": True, "reason": "It retains source totals but cannot identify an older shared entry ahead of newer private entries."},
        "anchor_rows": [analyze_row(source_row=source[key], a464_row=causal[key], a4670_row=ownership[key], a4671_row=tax[key]) for key in sorted(source)],
        "semantic_guards": {
            "complete_hash_chain_validated": True,
            "fixed_a464_grants_not_rescheduled": True,
            "a4670_canonical_fifo_replayed_exactly": True,
            "current_pending_birth_order_oldest_and_source_reconstructible": True,
            "source_count_only_lossy_negative_control_rejected": True,
            "a4671_span_inventory_and_capacity_context_matched": True,
            "q0_shared_and_large_q_headlocal_endpoints_validated": True,
            "no_finite_allocator_migration_drop_fallback_or_backing_action": True,
            "no_model_or_runtime_loaded": True,
            "no_descriptor_width_byte_access_port_bank_traffic_cycle_or_hardware_parameter_selected": True,
            "qwen_llama_rows_separate": True,
        },
        "boundaries": [
            "A birth-ordered source span is a logical candidate representation only. It has no physical descriptor/PTE width, layout, byte count, allocation, payload movement, access, port, bank, timing, or cost meaning.",
            "The fixed A4.6.4 grants, A4.6.7.0 source assignment, and canonical FIFO are inputs. This study neither schedules admission nor models finite capacity, allocator behavior, spill, migration, compaction, DROP, fallback, Full-KV backing, or protection.",
            "Per-token reference units and span counts are a semantic sufficiency comparison, not metadata compression, physical capacity, traffic, HBM/DMA, bandwidth, cycle, latency, throughput, energy, area, hardware selection, architecture specification, or RTL evidence.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a4680_pending_representation_sufficiency_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.8.0 pending representation sufficiency completed: {output}")


if __name__ == "__main__":
    main()
