#!/usr/bin/env python3
"""A4.6.8.2.1 metadata-organization sensitivity over the A4.6.8.2.0 trace.

This no-model, hardware-independent observer fixes FIFO/grants/source/event
order and only projects metadata events onto explicit replaceable buckets.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import SCHEMA as A461_SCHEMA, read_completed
from tools.analyze_kvzap_route_a464_causal_elastic_contract import SCHEMA as A464_SCHEMA
from tools.analyze_kvzap_route_a4670_pending_ownership_reference import SCHEMA as A4670_SCHEMA
from tools.analyze_kvzap_route_a4671_pending_organization_tax_recovery import SCHEMA as A4671_SCHEMA
from tools.analyze_kvzap_route_a4680_pending_representation_sufficiency import REPRESENTATION, SCHEMA as A4680_SCHEMA, validate_chain
from tools.analyze_kvzap_route_a4681_representation_access_contract import SCHEMA as A4681_SCHEMA
from tools.analyze_kvzap_route_a4682_access_epoch_trace import SCHEMA as A4682_SCHEMA, TRACE_SCHEMA as A4682_TRACE_SCHEMA, validate_a4681
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

SCHEMA = "kvzap-route-a46821-metadata-organization-sensitivity-1.0"
MAPPINGS = ("span_identity_striped_v1", "head_source_affine_v1")
BUCKET_COUNTS = (1, 2, 4, 8)
SERVICE_UNITS = (1, 2, 4)
PHASES = ("activation", "steady_state_append", "steady_state_dequeue")
METADATA_CLASSES = ("source_head_read", "source_compare", "mutable_head_update", "release_update", "creation_link")
PAYLOAD_REFERENCE_PRIMITIVES = {"payload_reference_create", "payload_reference_release"}
PRIMITIVE_CLASS = {
    "source_head_metadata_read": "source_head_read", "oldest_source_compare": "source_compare",
    "span_partial_dequeue": "mutable_head_update", "span_head_remaining_update": "mutable_head_update",
    "source_head_update": "mutable_head_update", "span_release": "release_update",
    "ownership_unlink": "release_update", "span_create": "creation_link", "ownership_link": "creation_link",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.6.8.2.1 no-model metadata bucket sensitivity; fixed A4.6.8.2.0 event trace, not physical banking or timing.")
    for name in ("a461", "a464", "a4670", "a4671", "a4680", "a4681", "a4682"):
        parser.add_argument(f"--{name}-report", type=Path, required=True)
    parser.add_argument("--a4682-trace", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate hash-bound inputs and trace manifest without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction)))]


def distribution(values: Iterable[int]) -> dict[str, int | None]:
    items = list(values)
    return {"count": len(items), "min": min(items) if items else None, "p50": percentile(items, .50), "p95": percentile(items, .95), "max": max(items) if items else None, "sum": sum(items)}


def context_key(event: dict[str, Any]) -> tuple[str, str, int, str]:
    return (str(event["anchor"]), str(event["workload"]), int(event["evaluation_horizon_append_opportunities"]), str(event["organization_label"]))


def bucket_for_event(*, event: dict[str, Any], mapping: str, bucket_count: int) -> int:
    """Declared logical bucket mapping, deliberately not a physical bank mapping."""
    layer, head = int(event["layer"]), int(event["kv_head"])
    if str(event["primitive"]) == "oldest_source_compare":
        return (layer * 131 + head * 17 + 7) % bucket_count
    span_id = int(event["span_id"])
    if mapping == "span_identity_striped_v1":
        return ((span_id ^ (span_id >> 32) ^ layer) * 1315423911) % bucket_count
    if mapping == "head_source_affine_v1":
        source_code = {"private": 0, "shared": 1}[str(event["source"])]
        return (layer * 131 + head * 17 + source_code * 7 + 3) % bucket_count
    raise ValueError(f"unknown mapping {mapping}")


def summarize_demands(*, demands: dict[tuple[str, int, int, int], Counter[str]], service: int, context: tuple[str, str, int, str], mapping: str, bucket_count: int) -> dict[str, Any]:
    """Same-epoch observer only; no service or shortfall carries forward."""
    by_phase: dict[str, list[tuple[tuple[str, int, int, int], Counter[str]]]] = defaultdict(list)
    for key, counts in demands.items():
        by_phase[key[0]].append((key, counts))

    def one(rows: list[tuple[tuple[str, int, int, int], Counter[str]]]) -> dict[str, Any]:
        totals = [sum(counts.values()) for _, counts in rows]
        shortfalls = [max(0, total - service) for total in totals]
        classes = {name: sum(counts[name] for _, counts in rows) for name in METADATA_CLASSES}
        total = sum(totals)
        return {
            "nonzero_layer_checkpoint_bucket_count": len(rows),
            "logical_demand_per_nonzero_layer_checkpoint_bucket": distribution(totals),
            "same_epoch_shortfall_logical_units": sum(shortfalls),
            "peak_same_epoch_shortfall_logical_units": max(shortfalls, default=0),
            "metadata_class_totals": classes,
            "metadata_class_shares": {name: (classes[name] / total if total else 0.0) for name in METADATA_CLASSES},
            "class_isolated_shortfall_logical_units": {name: sum(max(0, counts[name] - service) for _, counts in rows) for name in METADATA_CLASSES},
            "leave_one_out_shortfall_relief_logical_units": {name: sum(max(0, sum(counts.values()) - service) - max(0, sum(counts.values()) - counts[name] - service) for _, counts in rows) for name in METADATA_CLASSES},
        }

    all_rows = [item for rows in by_phase.values() for item in rows]
    hotspots = []
    for (phase, layer, checkpoint, bucket), counts in all_rows:
        demand = sum(counts.values())
        hotspots.append({"phase": phase, "layer": layer, "logical_checkpoint": checkpoint, "abstract_bucket": bucket, "logical_metadata_demand": demand, "same_epoch_shortfall_logical_units": max(0, demand - service), "metadata_class_counts": {name: counts[name] for name in METADATA_CLASSES}})
    hotspots.sort(key=lambda row: (-row["same_epoch_shortfall_logical_units"], -row["logical_metadata_demand"], row["logical_checkpoint"], row["layer"], row["abstract_bucket"]))
    return {
        "anchor": context[0], "workload": context[1], "evaluation_horizon_append_opportunities": context[2], "organization_label": context[3],
        "metadata_bucket_mapping": mapping, "abstract_bucket_count_per_layer": bucket_count, "abstract_service_units_per_bucket_per_logical_checkpoint": service,
        "all_phases": one(all_rows), "phase_rows": {phase: one(by_phase[phase]) for phase in PHASES}, "top_hotspots": hotspots[:10],
    }


def validate_inputs(args: argparse.Namespace) -> dict[str, Any]:
    a461 = read_completed(args.a461_report, A461_SCHEMA, "A4.6.1")
    a464 = read_completed(args.a464_report, A464_SCHEMA, "A4.6.4")
    a4670 = read_completed(args.a4670_report, A4670_SCHEMA, "A4.6.7.0")
    a4671 = read_completed(args.a4671_report, A4671_SCHEMA, "A4.6.7.1")
    a4680 = read_completed(args.a4680_report, A4680_SCHEMA, "A4.6.8.0")
    a4681 = read_completed(args.a4681_report, A4681_SCHEMA, "A4.6.8.1")
    validate_chain(a461=a461, a464=a464, a4670=a4670, a4671=a4671, args=args)
    validate_a4681(a4681=a4681, args=args)
    a4682 = read_completed(args.a4682_report, A4682_SCHEMA, "A4.6.8.2.0")
    hashes = {f"{name}_report_sha256": sha256_file(getattr(args, f"{name}_report")) for name in ("a461", "a464", "a4670", "a4671", "a4680", "a4681")}
    if a4682.get("input_artifacts") != hashes:
        raise ValueError("A4.6.8.2.0 does not hash-bind supplied predecessor reports")
    if a4682.get("access_epoch_trace", {}).get("schema_version") != A4682_TRACE_SCHEMA or sha256_file(args.a4682_trace) != a4682["access_epoch_trace"]["sha256"]:
        raise ValueError("A4.6.8.2.0 finalized trace manifest mismatch")
    required = ("complete_hash_chain_validated", "a4681_access_contract_required_and_validated", "fixed_a464_grants_not_rescheduled", "a4670_canonical_fifo_replayed_after_each_event", "exact_pending_birth_order_oldest_and_source_ownership_reconstructible", "a4680_span_create_release_inventory_matched", "a4681_primitive_totals_matched_phase_by_phase", "no_payload_movement_inferred_from_lifecycle", "no_model_or_runtime_loaded", "no_physical_width_byte_port_bank_traffic_cycle_or_hardware_parameter_selected")
    if not all(a4682.get("semantic_guards", {}).get(name) is True for name in required):
        raise ValueError("A4.6.8.2.0 semantic guards incomplete")
    if a4682.get("config", {}).get("representation") != REPRESENTATION:
        raise ValueError("A4.6.8.2.0 representation mismatch")
    return {"a4682": a4682, "hashes": hashes}


def stream_contexts(path: Path) -> Iterable[tuple[tuple[str, str, int, str], list[dict[str, Any]]]]:
    current: tuple[str, str, int, str] | None = None
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, str]] = set()
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            event = json.loads(line)
            if event.get("schema_version") != A4682_TRACE_SCHEMA:
                raise ValueError(f"unexpected trace schema at line {line_number}")
            key = context_key(event)
            if current is None:
                current = key
            if key != current:
                if current in seen:
                    raise ValueError("A4.6.8.2.0 context reappeared after closure")
                seen.add(current)
                yield current, records
                current, records = key, []
            records.append(event)
    if current is not None:
        if current in seen:
            raise ValueError("A4.6.8.2.0 final context reappeared after closure")
        yield current, records


def expected_contexts_from_a4682(report: dict[str, Any]) -> set[tuple[str, str, int, str]]:
    """Derive coverage from the hash-bound predecessor, never a literal count."""
    return {
        (str(anchor_row["anchor"]), str(anchor_row["workload"]), int(horizon_row["evaluation_horizon_append_opportunities"]), str(access_row["label"]))
        for anchor_row in report["anchor_rows"]
        for horizon_row in anchor_row["horizon_rows"]
        for access_row in horizon_row["access_epoch_rows"]
    }


def analyze_context(context: tuple[str, str, int, str], events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter[str], Counter[str]]:
    demands: dict[tuple[str, int], dict[tuple[str, int, int, int], Counter[str]]] = {(mapping, buckets): defaultdict(Counter) for mapping in MAPPINGS for buckets in BUCKET_COUNTS}
    primitives: Counter[str] = Counter()
    excluded: Counter[str] = Counter()
    for event in events:
        primitive = str(event["primitive"])
        primitives[primitive] += 1
        if primitive in PAYLOAD_REFERENCE_PRIMITIVES:
            excluded[primitive] += 1
            continue
        category = PRIMITIVE_CLASS.get(primitive)
        if category is None:
            raise ValueError(f"unclassified A4.6.8.2.0 primitive: {primitive}")
        for mapping in MAPPINGS:
            for buckets in BUCKET_COUNTS:
                bucket = bucket_for_event(event=event, mapping=mapping, bucket_count=buckets)
                demands[(mapping, buckets)][(str(event["phase"]), int(event["layer"]), int(event["logical_checkpoint"]), bucket)][category] += 1
    return ([summarize_demands(demands=demands[(mapping, buckets)], service=service, context=context, mapping=mapping, bucket_count=buckets) for mapping in MAPPINGS for buckets in BUCKET_COUNTS for service in SERVICE_UNITS], primitives, excluded)


def main() -> None:
    args = parse_args()
    validated = validate_inputs(args)
    if args.preflight_only:
        print("A4.6.8.2.1 preflight passed: predecessor hash chain, semantic guards, and finalized trace hash validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    rows: list[dict[str, Any]] = []
    primitive_totals: Counter[str] = Counter()
    excluded_totals: Counter[str] = Counter()
    trace_records = 0
    for context, events in stream_contexts(args.a4682_trace):
        context_rows, primitives, excluded = analyze_context(context, events)
        rows.extend(context_rows); primitive_totals.update(primitives); excluded_totals.update(excluded); trace_records += len(events)
    a4682 = validated["a4682"]
    if trace_records != int(a4682["access_epoch_trace"]["record_count"]):
        raise AssertionError("streamed trace record count differs from A4.6.8.2.0 manifest")
    contexts = {(r["anchor"], r["workload"], r["evaluation_horizon_append_opportunities"], r["organization_label"]) for r in rows}
    expected_contexts = expected_contexts_from_a4682(a4682)
    if contexts != expected_contexts or len(rows) != len(expected_contexts) * len(MAPPINGS) * len(BUCKET_COUNTS) * len(SERVICE_UNITS):
        raise AssertionError("unexpected A4.6.8.2.1 coverage")
    config = {
        "representation": REPRESENTATION, "metadata_bucket_mappings": list(MAPPINGS), "abstract_bucket_counts_per_layer": list(BUCKET_COUNTS), "abstract_service_units_per_bucket_per_logical_checkpoint": list(SERVICE_UNITS),
        "organization_axis": "fixed A4.6.8.2.0 organization labels; no FIFO/grant/source assignment changes", "mapping_axis": "replaceable logical projection separate from organization, not physical banking", "same_epoch_service_observer": "sum(max(0, demand-service)) per independent logical checkpoint/bucket; no backlog propagation or replay-state change", "boundary": "No physical descriptor/PTE width, metadata/payload bytes, address, HBM/DMA traffic, port, bank, cycle, timing, latency, throughput, energy, area, capacity, hardware parameter, architecture specification, or RTL is selected or inferred.",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "execution_classification": "no-model functional replay observer over a trace-derived ordered logical primitive trace; abstract bucket/service sensitivity is not physical banking, ports, timing, or hardware cost",
        "input_artifacts": {**validated["hashes"], "a4682_report_sha256": sha256_file(args.a4682_report), "a4682_trace_sha256": sha256_file(args.a4682_trace)},
        "trace_validation": {"schema_version": A4682_TRACE_SCHEMA, "record_count": trace_records, "sha256": sha256_file(args.a4682_trace)},
        "metadata_class_definition": {"source_head_read": ["source_head_metadata_read"], "source_compare": ["oldest_source_compare"], "mutable_head_update": ["span_partial_dequeue", "span_head_remaining_update", "source_head_update"], "release_update": ["span_release", "ownership_unlink"], "creation_link": ["span_create", "ownership_link"], "explicitly_excluded_payload_reference_primitives": sorted(PAYLOAD_REFERENCE_PRIMITIVES)},
        "primitive_totals_from_a4682_trace": dict(sorted(primitive_totals.items())), "explicitly_excluded_payload_reference_totals": dict(sorted(excluded_totals.items())), "sensitivity_rows": rows,
        "semantic_guards": {"complete_hash_chain_and_finalized_a4682_trace_validated": True, "fixed_a4682_fifo_grants_source_affiliation_and_event_order_not_rescheduled": True, "all_three_pending_organization_labels_observed_without_organization_mutation": True, "organization_and_metadata_bucket_mapping_axes_separated": True, "metadata_classes_cover_all_nonpayload_trace_primitives": True, "payload_reference_primitives_explicitly_excluded_from_metadata_service_observer": True, "same_epoch_shortfall_does_not_propagate_backlog_or_change_fifo": True, "abstract_bucket_and_service_units_not_physical_bank_port_or_cycle_parameters": True, "qwen_llama_rows_separate": True, "no_model_runtime_or_profiler_loaded": True, "no_payload_movement_or_hardware_cost_inferred": True, "no_drop_fallback_migration_backing_or_protection_action": True},
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a46821_metadata_organization_sensitivity_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.8.2.1 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} rows={len(rows)} trace_records={trace_records}")


if __name__ == "__main__":
    main()
