#!/usr/bin/env python3
"""A4.6.7.0 exact per-head FIFO reference for pending ownership organizations.

The reference is deliberately unbounded: it establishes whether private/shared
ownership can preserve Route-A pending semantics before any finite-capacity
allocator, migration strategy, or physical storage model is considered.
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
from tools.analyze_kvzap_route_a4630_physicalization_mapping import SCHEMA as A4630_SCHEMA
from tools.analyze_kvzap_route_a4632_temporal_contention_replay import HORIZONS, source_streams
from tools.analyze_kvzap_route_a464_causal_elastic_contract import SCHEMA as A464_SCHEMA
from tools.analyze_kvzap_route_a465_causal_capacity_envelope import (
    SCHEMA as A465_SCHEMA,
    expected_a464,
    run_causal_observer,
    validate_against_a464,
)
from tools.analyze_kvzap_route_a466_pending_organization_contract import SCHEMA as A466_SCHEMA
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4670-pending-ownership-reference-1.0"
GLOBAL_HIERARCHICAL_PRIVATE_QUOTAS = (128, 256, 512)
Stream = tuple[int, int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.6.7.0 no-model Route-A pending ownership reference: fixed A4.6.4 grants and "
            "per-head FIFO only; no migration, finite allocator, scheduler, DROP, fallback, or hardware selection."
        )
    )
    parser.add_argument("--a461-report", type=Path, required=True)
    parser.add_argument("--a4630-report", type=Path, required=True)
    parser.add_argument("--a464-report", type=Path, required=True)
    parser.add_argument("--a465-report", type=Path, required=True)
    parser.add_argument("--a466-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate the completed hash-bound input chain without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


@dataclass
class Segment:
    birth_opportunity: int
    sequence_start: int
    count: int

    @property
    def key(self) -> tuple[int, int]:
        return self.birth_opportunity, self.sequence_start

    def consume(self, count: int) -> None:
        if count <= 0 or count > self.count:
            raise ValueError("invalid segment consumption")
        self.sequence_start += count
        self.count -= count


class PendingOwnershipState:
    """One head's immutable-source ownership state and canonical FIFO oracle."""

    def __init__(self, *, organization: str, private_quota: int | None) -> None:
        if organization not in {"head_local", "layer_shared", "hierarchical"}:
            raise ValueError("unknown ownership organization")
        if organization == "hierarchical" and (private_quota is None or private_quota < 0):
            raise ValueError("hierarchical organization requires nonnegative private quota")
        self.organization = organization
        self.private_quota = private_quota
        self.canonical: deque[Segment] = deque()
        self.sources: dict[str, deque[Segment]] = {"private": deque(), "shared": deque()}
        self.live: dict[str, int] = {"private": 0, "shared": 0}
        self.next_sequence = 0
        self.max_pending = 0
        self.max_active_spans = 0
        self.max_active_sources = 0
        self.source_age_inversion_count = 0
        self.migration_event_count = 0
        self.operation_counts: dict[str, int] = defaultdict(int)

    @property
    def pending(self) -> int:
        return self.live["private"] + self.live["shared"]

    def active_spans(self) -> int:
        return len(self.sources["private"]) + len(self.sources["shared"])

    def active_sources(self) -> int:
        return sum(bool(self.sources[source]) for source in ("private", "shared"))

    def _append(self, *, source: str, count: int, birth_opportunity: int) -> dict[str, int]:
        if source not in self.sources or count <= 0:
            raise ValueError("invalid source append")
        segment = Segment(birth_opportunity=birth_opportunity, sequence_start=self.next_sequence, count=count)
        self.next_sequence += count
        self.canonical.append(Segment(birth_opportunity=segment.birth_opportunity, sequence_start=segment.sequence_start, count=count))
        self.sources[source].append(segment)
        self.live[source] += count
        self.operation_counts[f"{source}_enqueue_token_units"] += count
        self.operation_counts[f"{source}_enqueue_segment_count"] += 1
        return {"source": source, "count": count}

    def enqueue(self, *, count: int, birth_opportunity: int) -> list[dict[str, int]]:
        """Assign source once at enqueue; no later private/shared migration exists."""
        if count < 0 or birth_opportunity < 0:
            raise ValueError("invalid enqueue")
        events: list[dict[str, int]] = []
        if not count:
            return events
        if self.organization == "head_local":
            events.append(self._append(source="private", count=count, birth_opportunity=birth_opportunity))
        elif self.organization == "layer_shared":
            events.append(self._append(source="shared", count=count, birth_opportunity=birth_opportunity))
        else:
            assert self.private_quota is not None
            private_count = min(count, max(0, self.private_quota - self.live["private"]))
            if private_count:
                events.append(self._append(source="private", count=private_count, birth_opportunity=birth_opportunity))
            if count - private_count:
                events.append(self._append(source="shared", count=count - private_count, birth_opportunity=birth_opportunity))
        self.max_pending = max(self.max_pending, self.pending)
        self.max_active_spans = max(self.max_active_spans, self.active_spans())
        self.max_active_sources = max(self.max_active_sources, self.active_sources())
        return events

    def dequeue(self, *, count: int) -> list[dict[str, int | bool]]:
        """Consume exact canonical FIFO order by comparing private/shared fronts."""
        if count < 0 or count > self.pending:
            raise ValueError("invalid dequeue grant")
        chunks: list[dict[str, int | bool]] = []
        previous_source: str | None = None
        while count:
            candidates = [source for source in ("private", "shared") if self.sources[source]]
            if not candidates:
                raise AssertionError("pending accounting lost a source segment")
            compared_sources = len(candidates) == 2
            if compared_sources:
                self.operation_counts["oldest_source_comparison_count"] += 1
            source = min(candidates, key=lambda item: self.sources[item][0].key)
            selected = self.sources[source][0]
            for other in candidates:
                if self.sources[other][0].key < selected.key:
                    self.source_age_inversion_count += 1
                    raise AssertionError("source-age inversion")
            canonical = self.canonical[0]
            if selected.key != canonical.key:
                self.source_age_inversion_count += 1
                raise AssertionError("selected source is not canonical oldest entry")
            amount = min(count, selected.count, canonical.count)
            switched = previous_source is not None and previous_source != source
            if switched:
                self.operation_counts["cross_source_switch_count"] += 1
            selected.consume(amount)
            canonical.consume(amount)
            self.live[source] -= amount
            self.operation_counts[f"{source}_dequeue_token_units"] += amount
            count -= amount
            released = selected.count == 0
            if released:
                self.sources[source].popleft()
                self.operation_counts[f"{source}_release_segment_count"] += 1
            if canonical.count == 0:
                self.canonical.popleft()
            chunks.append({"source": source, "count": amount, "compared_sources": compared_sources, "source_switch": switched, "released_segment": released})
            previous_source = source
        if self.pending != sum(segment.count for segment in self.canonical):
            raise AssertionError("source and canonical pending totals diverged")
        return chunks


def a465_horizon(row: dict[str, Any], horizon: int) -> dict[str, Any]:
    return next(item for item in row["horizon_rows"] if int(item["evaluation_horizon_append_opportunities"]) == horizon)


def a466_horizon(row: dict[str, Any], horizon: int) -> dict[str, Any]:
    return next(item for item in row["horizon_rows"] if int(item["evaluation_horizon_append_opportunities"]) == horizon)


def validate_against_a465(observed: dict[str, Any], prior: dict[str, Any]) -> None:
    for field in ("B_max", "B_final", "deadline_miss_head_count", "T_drain"):
        if observed[field] != prior["causal_outcome"][field]:
            raise ValueError(f"A4.6.7.0 observer replay disagrees with A4.6.5 for {field}")
    left = {(row["layer"], row["kv_head"]): row for row in observed["per_head"]}
    right = {(row["layer"], row["kv_head"]): row for row in prior["per_head_age_backlog_tail"]}
    if set(left) != set(right):
        raise ValueError("A4.6.7.0/A4.6.5 per-head coverage mismatch")
    for key in left:
        for field in ("B_max_h", "B_final_h", "T_drain_h"):
            if left[key][field] != right[key][field]:
                raise ValueError(f"A4.6.7.0 observer replay disagrees with A4.6.5 for {key} {field}")


def validate_against_a466(observed: dict[str, Any], prior: dict[str, Any]) -> None:
    for field in ("B_max", "B_final", "deadline_miss_head_count", "T_drain"):
        if observed[field] != prior["causal_outcome"][field]:
            raise ValueError(f"A4.6.7.0 observer replay disagrees with A4.6.6 for {field}")
    left = {(row["layer"], row["kv_head"]): row for row in observed["per_head"]}
    right = {(row["layer"], row["kv_head"]): row for row in prior["per_head_age_backlog_tail_unchanged"]}
    if set(left) != set(right):
        raise ValueError("A4.6.7.0/A4.6.6 per-head coverage mismatch")
    for key in left:
        for field in ("B_max_h", "B_final_h", "T_drain_h"):
            if left[key][field] != right[key][field]:
                raise ValueError(f"A4.6.7.0 observer replay disagrees with A4.6.6 for {key} {field}")


def derive_fixed_grants(*, observed: dict[str, Any], arrivals: dict[Stream, list[int]]) -> list[dict[Stream, tuple[int, int, int]]]:
    """Derive pre/grant/post directly from the fixed A4.6.4 replay state.

    This intentionally does not re-run a scheduler or choose an allocation.
    """
    final = {(row["layer"], row["kv_head"]): int(row["B_final_h"]) for row in observed["per_head"]}
    output = []
    for index, epoch in enumerate(observed["epochs"]):
        pre = {(row["layer"], row["kv_head"]): int(row["pending"]) for row in epoch["head_pending_after_arrivals"]}
        if index + 1 < len(observed["epochs"]):
            next_pre = {(row["layer"], row["kv_head"]): int(row["pending"]) for row in observed["epochs"][index + 1]["head_pending_after_arrivals"]}
            post = {key: next_pre[key] - arrivals[key][index + 1] for key in pre}
        else:
            post = final
        if set(pre) != set(post) or any(post[key] < 0 or post[key] > pre[key] for key in pre):
            raise ValueError("cannot derive a valid fixed per-head grant schedule")
        output.append({key: (pre[key], pre[key] - post[key], post[key]) for key in pre})
    return output


def capacity_context(a466: dict[str, Any], *, organization: str, private_quota: int | None) -> dict[str, Any]:
    frontier = a466["Cmin_zero_breach_capacity_efficiency_frontier"]
    if organization == "head_local":
        value = frontier["head_local_equal_quota"]["Cmin_zero_breach_logical_tokens_per_layer"]
    elif organization == "layer_shared":
        value = frontier["layer_shared"]["Cmin_zero_breach_logical_tokens_per_layer"]
    else:
        assert private_quota is not None
        item = next(entry for entry in frontier["hierarchical_private_quota_sweep"] if int(entry["private_quota_per_head"]) == private_quota)
        value = item["Cmin_zero_breach_logical_tokens_per_layer"]
    return {"a466_Cmin_zero_breach_logical_tokens_per_layer": value, "logical_observer_only": True}


def integer_summary(values: list[int]) -> dict[str, int]:
    if not values:
        raise ValueError("cannot summarize empty per-head state")
    ordered = sorted(values)
    return {
        "count": len(ordered), "sum": sum(ordered), "min": ordered[0],
        "p50": ordered[(len(ordered) - 1) * 50 // 100],
        "p95": ordered[(len(ordered) - 1) * 95 // 100], "max": ordered[-1],
    }


def summarize_per_head(per_head: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep a compact, hash-bound audit summary after per-head validation."""
    return {
        "per_head_state_sha256": stable_hash(per_head),
        "B_max_h": integer_summary([int(item["B_max_h"]) for item in per_head]),
        "B_final_h": integer_summary([int(item["B_final_h"]) for item in per_head]),
        "max_active_spans": integer_summary([int(item["max_active_spans"]) for item in per_head]),
        "max_active_sources": integer_summary([int(item["max_active_sources"]) for item in per_head]),
        "heads_with_two_active_sources": sum(int(item["max_active_sources"]) == 2 for item in per_head),
        "heads_with_nonzero_shared_final": sum(int(item["shared_live_final"]) > 0 for item in per_head),
        "source_age_inversion_count": sum(int(item["source_age_inversion_count"]) for item in per_head),
        "migration_event_count": sum(int(item["migration_event_count"]) for item in per_head),
    }


def summarize_layer_opportunity(states: dict[Stream, PendingOwnershipState], layer: int) -> dict[str, int]:
    members = [state for (item_layer, _), state in states.items() if item_layer == layer]
    return {
        "active_spans_after_arrival": sum(state.active_spans() for state in members),
        "heads_with_shared_after_arrival": sum(state.live["shared"] > 0 for state in members),
        "heads_with_two_sources_after_arrival": sum(state.active_sources() == 2 for state in members),
        "max_active_spans_one_head_after_arrival": max(state.active_spans() for state in members),
    }


def simulate_ownership(*, inventory: dict[Stream, dict[str, int]], arrivals: dict[Stream, list[int]], fixed_schedule: list[dict[Stream, tuple[int, int, int]]], organization: str, private_quota: int | None) -> dict[str, Any]:
    """Run an immutable-source ownership trace against a fixed per-head schedule."""
    states = {key: PendingOwnershipState(organization=organization, private_quota=private_quota) for key in sorted(inventory)}
    for key, state in states.items():
        state.enqueue(count=inventory[key]["pending"], birth_opportunity=0)
    layers = sorted({layer for layer, _ in states})
    layer_metrics: dict[int, dict[str, int]] = {layer: defaultdict(int) for layer in layers}
    global_max_pending = sum(state.pending for state in states.values())
    for index, schedule in enumerate(fixed_schedule):
        opportunity = index + 1
        event_ops: dict[int, dict[str, int]] = {layer: defaultdict(int) for layer in layers}
        for key, state in states.items():
            for event in state.enqueue(count=arrivals[key][index], birth_opportunity=opportunity):
                event_ops[key[0]][f"{event['source']}_enqueue_token_units"] += event["count"]
        for key, state in states.items():
            expected_pre, _, _ = schedule[key]
            if state.pending != expected_pre:
                raise AssertionError("ownership enqueue changed fixed pre-grant pending state")
        global_max_pending = max(global_max_pending, sum(state.pending for state in states.values()))
        for layer in layers:
            summary = summarize_layer_opportunity(states, layer)
            for name, value in summary.items():
                layer_metrics[layer][f"max_{name}"] = max(layer_metrics[layer][f"max_{name}"], value)
        for key, state in states.items():
            _, grant, expected_post = schedule[key]
            chunks = state.dequeue(count=grant)
            used_sources = {str(chunk["source"]) for chunk in chunks}
            if len(used_sources) == 2:
                event_ops[key[0]]["cross_source_dequeue_head_opportunity_count"] += 1
            for chunk in chunks:
                source = str(chunk["source"])
                event_ops[key[0]][f"{source}_dequeue_token_units"] += int(chunk["count"])
                event_ops[key[0]]["oldest_source_comparison_count"] += int(bool(chunk["compared_sources"]))
                event_ops[key[0]]["cross_source_switch_count"] += int(bool(chunk["source_switch"]))
                event_ops[key[0]][f"{source}_release_segment_count"] += int(bool(chunk["released_segment"]))
            if state.pending != expected_post:
                raise AssertionError("ownership dequeue changed fixed post-grant pending state")
        for layer in layers:
            for name, value in event_ops[layer].items():
                layer_metrics[layer][name] += value
                layer_metrics[layer][f"max_{name}_one_opportunity"] = max(layer_metrics[layer][f"max_{name}_one_opportunity"], value)
    per_head = []
    for (layer, head), state in sorted(states.items()):
        per_head.append({
            "layer": layer, "kv_head": head, "B_max_h": state.max_pending, "B_final_h": state.pending,
            "max_active_spans": state.max_active_spans, "max_active_sources": state.max_active_sources,
            "private_live_final": state.live["private"], "shared_live_final": state.live["shared"],
            "source_age_inversion_count": state.source_age_inversion_count, "migration_event_count": state.migration_event_count,
            "logical_queue_operations": dict(sorted(state.operation_counts.items())),
        })
    if any(item["source_age_inversion_count"] or item["migration_event_count"] for item in per_head):
        raise AssertionError("immutable ownership semantic guard failed")
    global_ops: dict[str, int] = defaultdict(int)
    for state in states.values():
        for name, value in state.operation_counts.items():
            global_ops[name] += value
    return {
        "organization": organization,
        "private_quota_per_head": private_quota,
        "global_B_max": global_max_pending,
        "global_B_final": sum(state.pending for state in states.values()),
        "per_head": per_head,
        "per_layer_logical_operation_and_concurrency_summary": [{"layer": layer, **dict(sorted(metrics.items()))} for layer, metrics in sorted(layer_metrics.items())],
        "global_logical_queue_operations": dict(sorted(global_ops.items())),
        "semantic_guards": {
            "per_head_canonical_fifo_exact": True,
            "source_age_inversion_count": 0,
            "migration_event_count": 0,
            "fixed_grants_consumed_without_recomputation": True,
            "source_residence_immutable_until_dequeue": True,
        },
    }


def validate_simulation(*, result: dict[str, Any], observed: dict[str, Any]) -> None:
    if result["global_B_max"] != observed["B_max"] or result["global_B_final"] != observed["B_final"]:
        raise AssertionError("ownership simulation changed aggregate fixed pending state")
    actual = {(item["layer"], item["kv_head"]): item for item in result["per_head"]}
    expected = {(item["layer"], item["kv_head"]): item for item in observed["per_head"]}
    if set(actual) != set(expected):
        raise AssertionError("ownership simulation head coverage differs from fixed replay")
    for key in actual:
        if actual[key]["B_max_h"] != expected[key]["B_max_h"] or actual[key]["B_final_h"] != expected[key]["B_final_h"]:
            raise AssertionError("ownership simulation changed per-head pending state")


def organization_variants(observed: dict[str, Any]) -> list[dict[str, Any]]:
    endpoint = max(int(item["B_max_h"]) for item in observed["per_head"])
    variants = [
        {"label": "head_local_private_unbounded", "organization": "head_local", "private_quota": None, "semantic_endpoint_only": False},
        {"label": "layer_shared_unbounded", "organization": "layer_shared", "private_quota": None, "semantic_endpoint_only": False},
        {"label": "hierarchical_q0_shared_endpoint", "organization": "hierarchical", "private_quota": 0, "semantic_endpoint_only": True},
    ]
    for quota in GLOBAL_HIERARCHICAL_PRIVATE_QUOTAS:
        variants.append({"label": f"hierarchical_q{quota}", "organization": "hierarchical", "private_quota": quota, "semantic_endpoint_only": False})
    if endpoint not in GLOBAL_HIERARCHICAL_PRIVATE_QUOTAS:
        variants.append({"label": "hierarchical_qpeak_head_local_endpoint", "organization": "hierarchical", "private_quota": endpoint, "semantic_endpoint_only": True})
    return variants


def validate_chain(*, a461: dict[str, Any], a4630: dict[str, Any], a464: dict[str, Any], a465: dict[str, Any], a466: dict[str, Any], args: argparse.Namespace) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    if a4630.get("input_artifacts", {}).get("a461_report_sha256") != sha256_file(args.a461_report):
        raise ValueError("A4.6.3.0 does not hash-bind this A4.6.1 report")
    a464_inputs = a464.get("input_artifacts", {})
    if a464_inputs.get("a461_report_sha256") != sha256_file(args.a461_report) or a464_inputs.get("a4630_report_sha256") != sha256_file(args.a4630_report):
        raise ValueError("A4.6.4 does not hash-bind supplied A4.6.1/A4.6.3.0 reports")
    a465_inputs = a465.get("input_artifacts", {})
    if a465_inputs != {"a461_report_sha256": sha256_file(args.a461_report), "a4630_report_sha256": sha256_file(args.a4630_report), "a464_report_sha256": sha256_file(args.a464_report)}:
        raise ValueError("A4.6.5 does not hash-bind supplied causal replay chain")
    a466_inputs = a466.get("input_artifacts", {})
    if a466_inputs != {"a461_report_sha256": sha256_file(args.a461_report), "a4630_report_sha256": sha256_file(args.a4630_report), "a464_report_sha256": sha256_file(args.a464_report), "a465_report_sha256": sha256_file(args.a465_report)}:
        raise ValueError("A4.6.6 does not hash-bind supplied organization chain")
    required466 = ("complete_hash_binding_validated", "same_total_logical_budget_per_layer_across_organizations", "organization_does_not_change_grants_controller_or_per_head_order", "no_drop_fallback_or_backing_action")
    if not all(a466.get("observational_guards", {}).get(name) is True for name in required466):
        raise ValueError("A4.6.6 organization guards are incomplete")
    source = {(row["anchor"], row["workload"]): row for row in a461["anchor_rows"]}
    causal = {(row["anchor"], row["workload"]): row for row in a464["anchor_rows"]}
    capacity = {(row["anchor"], row["workload"]): row for row in a465["anchor_rows"]}
    organization = {(row["anchor"], row["workload"]): row for row in a466["anchor_rows"]}
    if len(source) != 6 or set(source) != set(causal) or set(source) != set(capacity) or set(source) != set(organization):
        raise ValueError("A4.6.1/A4.6.4/A4.6.5/A4.6.6 six-row coverage mismatch")
    return source, causal, capacity, organization


def analyze_row(*, source_row: dict[str, Any], a464_row: dict[str, Any], a465_row: dict[str, Any], a466_row: dict[str, Any]) -> dict[str, Any]:
    inventory, arrivals = source_streams(source_row)
    horizon_rows = []
    for horizon in HORIZONS:
        observed = run_causal_observer(inventory=inventory, arrivals=arrivals, horizon=horizon)
        validate_against_a464(observed, expected_a464(a464_row, horizon))
        validate_against_a465(observed, a465_horizon(a465_row, horizon))
        a466 = a466_horizon(a466_row, horizon)
        validate_against_a466(observed, a466)
        fixed_schedule = derive_fixed_grants(observed=observed, arrivals=arrivals)
        variants = []
        for variant in organization_variants(observed):
            result = simulate_ownership(inventory=inventory, arrivals=arrivals, fixed_schedule=fixed_schedule, organization=variant["organization"], private_quota=variant["private_quota"])
            validate_simulation(result=result, observed=observed)
            result["label"] = variant["label"]
            result["semantic_endpoint_only"] = variant["semantic_endpoint_only"]
            result["a466_capacity_context"] = capacity_context(a466, organization=variant["organization"], private_quota=variant["private_quota"])
            variants.append(result)
        shared = next(item for item in variants if item["label"] == "layer_shared_unbounded")
        q0 = next(item for item in variants if item["label"] == "hierarchical_q0_shared_endpoint")
        for field in ("global_B_max", "global_B_final", "per_head", "global_logical_queue_operations"):
            if shared[field] != q0[field]:
                raise AssertionError("hierarchical q=0 does not degenerate to pure shared ownership")
        endpoint = next(item for item in variants if item["label"] == "hierarchical_qpeak_head_local_endpoint")
        head_local = next(item for item in variants if item["label"] == "head_local_private_unbounded")
        for field in ("global_B_max", "global_B_final", "per_head", "global_logical_queue_operations"):
            if endpoint[field] != head_local[field]:
                raise AssertionError("hierarchical large-quota endpoint does not degenerate to head-local ownership")
        compact_variants = []
        for variant in variants:
            compact = {key: value for key, value in variant.items() if key != "per_head"}
            compact["per_head_semantic_summary"] = summarize_per_head(variant["per_head"])
            compact_variants.append(compact)
        horizon_rows.append({
            "evaluation_horizon_append_opportunities": horizon,
            "a464_causal_replay_match": True,
            "a465_causal_replay_match": True,
            "a466_causal_replay_match": True,
            "causal_outcome": {field: observed[field] for field in ("B_max", "B_final", "deadline_miss_head_count", "T_drain")},
            "ownership_variants": compact_variants,
            "semantic_degeneracy_guards": {"hierarchical_q0_equals_layer_shared": True, "hierarchical_qpeak_equals_head_local": True},
        })
    return {"anchor": source_row["anchor"], "workload": source_row["workload"], "reasoning_priority_row": source_row["workload"] == "reasoning", "horizon_rows": horizon_rows}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a461 = read_completed(args.a461_report, A461_SCHEMA, "A4.6.1")
    a4630 = read_completed(args.a4630_report, A4630_SCHEMA, "A4.6.3.0")
    a464 = read_completed(args.a464_report, A464_SCHEMA, "A4.6.4")
    a465 = read_completed(args.a465_report, A465_SCHEMA, "A4.6.5")
    a466 = read_completed(args.a466_report, A466_SCHEMA, "A4.6.6")
    source, causal, capacity, organization = validate_chain(a461=a461, a4630=a4630, a464=a464, a465=a465, a466=a466, args=args)
    if args.preflight_only:
        print("A4.6.7.0 preflight passed: A4.6.1/A4.6.3.0/A4.6.4/A4.6.5/A4.6.6 hash chain, guards, and six-row coverage validated; no output created.")
        return
    rows = [analyze_row(source_row=source[key], a464_row=causal[key], a465_row=capacity[key], a466_row=organization[key]) for key in sorted(source)]
    config = {
        "a461_report": str(args.a461_report), "a4630_report": str(args.a4630_report), "a464_report": str(args.a464_report), "a465_report": str(args.a465_report), "a466_report": str(args.a466_report),
        "evaluation_horizons_append_opportunities": list(HORIZONS),
        "global_hierarchical_private_quota_sensitivities": list(GLOBAL_HIERARCHICAL_PRIVATE_QUOTAS),
        "source_assignment": "At enqueue only: head-local->private, layer-shared->shared, hierarchical->private until per-head q then shared overflow. Source residence is immutable until dequeue.",
        "dequeue_rule": "For each head, compare private/shared queue fronts by immutable (birth_opportunity, within_head_sequence) and consume the canonical oldest entry. No source-priority shortcut is permitted.",
        "finite_capacity_rule": "No finite C, allocator, spill, migration, DROP, fallback, backing, or protection action is modeled in this functional ownership reference.",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "execution_classification": "no-model functional pending-ownership semantic reference and logical operation inventory over fixed causal grants; not measured hardware evidence",
        "input_artifacts": {"a461_report_sha256": sha256_file(args.a461_report), "a4630_report_sha256": sha256_file(args.a4630_report), "a464_report_sha256": sha256_file(args.a464_report), "a465_report_sha256": sha256_file(args.a465_report), "a466_report_sha256": sha256_file(args.a466_report)},
        "anchor_rows": rows,
        "semantic_guards": {
            "complete_hash_binding_validated": True, "fixed_a464_grants_derived_not_rescheduled": True,
            "a464_a465_a466_replay_matches_each_horizon": True, "per_head_birth_order_fifo_exact": True,
            "cross_source_oldest_entry_selection_enforced": True, "source_age_inversion_rejected": True,
            "private_shared_migration_prohibited": True, "q0_shared_and_large_q_headlocal_degeneracy_validated": True,
            "no_finite_capacity_allocator_drop_fallback_or_backing_action": True, "qwen_llama_rows_separate": True,
            "no_model_or_runtime_loaded": True, "no_hardware_parameter_selected": True,
        },
        "boundaries": [
            "Private/shared/hierarchical labels are immutable logical ownership only. The reference has no finite capacity and does not model a storage allocator, private/shared migration, spill, compaction, protection action, DROP, fallback, or Full-KV backing.",
            "Enqueue/dequeue/release, span, source comparison, and concurrency fields are logical functional events and inventories. They are not descriptor byte widths, PTE formats, physical accesses, ports, bank conflicts, HBM/DMA traffic, cycles, timing, latency, throughput, energy, area, or hardware cost.",
            "A4.6.6 Cmin context is carried only to pair a later organization-tax study with capacity recovery. It is not allocated capacity in this reference and selects no organization or hardware configuration.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a4670_pending_ownership_reference_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.7.0 pending ownership reference completed: {output}")


if __name__ == "__main__":
    main()
