#!/usr/bin/env python3
"""A4.6.8.2.2.1 record-aware organization sensitivity for Route-A.

This observer fixes the A4.6.8.2.2.0 record-access stream and examines only
declared logical record-to-bucket mappings.  Buckets and issue units are
abstract sensitivity labels, never selected physical banks, ports, or cycles.
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
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a46821_metadata_organization_sensitivity import SCHEMA as A46821_SCHEMA
from tools.analyze_kvzap_route_a468220_metadata_recordization import SCHEMA as A468220_SCHEMA, TRACE_SCHEMA as A468220_TRACE_SCHEMA
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

SCHEMA = "kvzap-route-a468221-record-organization-sensitivity-1.0"
CURVES = ("conservative", "strict_same_record")
MAPPINGS = ("all_record_striped_v1", "head_source_affine_v1", "control_affine_span_striped_v1", "hierarchical_control_span_v1")
BUCKET_COUNTS = (1, 2, 4, 8)
ISSUE_UNITS = (1, 2, 4)
PHASES = ("activation", "steady_state_append", "steady_state_dequeue")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.6.8.2.2.1 no-model record-organization sensitivity; abstract access pressure only, not physical banking/ports/timing.")
    parser.add_argument("--a46821-report", type=Path, required=True)
    parser.add_argument("--a468220-report", type=Path, required=True)
    parser.add_argument("--a468220-trace", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate bound reports, guards, and record-trace hash without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def percentile(values: Iterable[float], p: float) -> float | None:
    values = sorted(values)
    if not values:
        return None
    return values[max(0, min(len(values) - 1, int((len(values) - 1) * p)))]


def distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    values = list(values)
    return {"count": len(values), "p50": percentile(values, .50), "p95": percentile(values, .95), "p99": percentile(values, .99), "max": max(values) if values else None, "sum": sum(values)}


def stable_bucket(parts: Iterable[Any], count: int) -> int:
    text = "|".join(str(part) for part in parts)
    value = 0
    for index, char in enumerate(text, 1):
        value = (value + index * ord(char)) & 0xFFFFFFFF
    return value % count


def bucket_for_record(op: dict[str, Any], mapping: str, count: int) -> int:
    record_type = str(op["record_type"])
    layer, head, source = int(op["layer"]), int(op["kv_head"]), op.get("source") or "control"
    identity = tuple(op["record_identity"])
    head_source = (layer, head, source)
    if mapping == "all_record_striped_v1":
        return stable_bucket((record_type, *identity), count)
    if mapping == "head_source_affine_v1":
        return stable_bucket(head_source, count)
    if mapping == "control_affine_span_striped_v1":
        return stable_bucket(head_source if record_type in {"frontier_control", "selection_control"} else (record_type, *identity), count)
    if mapping == "hierarchical_control_span_v1":
        return stable_bucket(head_source if record_type in {"frontier_control", "selection_control", "ownership_link"} else (record_type, *identity), count)
    raise ValueError(f"unknown mapping {mapping}")


def curve_weight(op: dict[str, Any], curve: str) -> int:
    if curve == "conservative":
        return int(op["conservative_record_op_count"])
    if curve == "strict_same_record":
        return int(op["strict_same_record_merged_op_count"])
    raise ValueError(f"unknown curve {curve}")


def context_key(op: dict[str, Any]) -> tuple[str, str, int, str]:
    return (str(op["anchor"]), str(op["workload"]), int(op["evaluation_horizon_append_opportunities"]), str(op["organization_label"]))


def category(op: dict[str, Any]) -> str:
    if op["record_type"] in {"frontier_control", "selection_control"}:
        return "control"
    if op["record_type"] == "span_descriptor":
        return "span"
    if op["record_type"] == "ownership_link":
        return "ownership"
    raise ValueError("unknown record type")


def contiguous_run(checkpoints: Iterable[int], phase: str) -> int:
    items = sorted(set(checkpoints))
    if not items:
        return 0
    stride = 2 if phase != "activation" else 1
    best = run = 1
    for prior, current in zip(items, items[1:]):
        run = run + 1 if current - prior == stride else 1
        best = max(best, run)
    return best


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    a46821 = read_completed(args.a46821_report, A46821_SCHEMA, "A4.6.8.2.1")
    a468220 = read_completed(args.a468220_report, A468220_SCHEMA, "A4.6.8.2.2.0")
    trace_sha = sha256_file(args.a468220_trace)
    if a468220.get("record_access_trace", {}).get("schema_version") != A468220_TRACE_SCHEMA or a468220["record_access_trace"].get("sha256") != trace_sha:
        raise ValueError("A4.6.8.2.2.0 record trace manifest mismatch")
    if a468220.get("input_artifacts", {}).get("a46821_report_sha256") != sha256_file(args.a46821_report):
        raise ValueError("A4.6.8.2.2.0 does not hash-bind supplied A4.6.8.2.1 report")
    required = ("a4682_and_a46821_hash_bound_contracts_validated", "a46821_primitive_totals_and_context_coverage_matched", "fixed_fifo_oldest_source_ownership_and_grants_not_rescheduled", "conservative_and_strict_curves_explainable_and_count_conserved", "strict_merge_never_crosses_birth_source_or_order_boundary", "no_physical_layout_width_byte_bank_port_cycle_or_cost_inferred")
    if not all(a468220.get("semantic_guards", {}).get(name) is True for name in required):
        raise ValueError("A4.6.8.2.2.0 semantic guards incomplete")
    return a46821, a468220


def summarize_context(context: tuple[str, str, int, str], ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    demands: dict[tuple[str, str, int], dict[tuple[str, int, int, int], Counter[str]]] = {
        (curve, mapping, buckets): defaultdict(Counter) for curve in CURVES for mapping in MAPPINGS for buckets in BUCKET_COUNTS
    }
    rmw: dict[tuple[str, str, int], Counter[tuple[str, int, int, tuple[Any, ...]]]] = {key: Counter() for key in demands}
    fanout: dict[tuple[str, str, int], dict[tuple[str, int, int, int], set[int]]] = {key: defaultdict(set) for key in demands}
    head_demand: dict[tuple[str, str, int], Counter[tuple[str, int, int, int]]] = {key: Counter() for key in demands}
    for op in ops:
        for curve in CURVES:
            weight = curve_weight(op, curve)
            for mapping in MAPPINGS:
                for buckets in BUCKET_COUNTS:
                    key = (curve, mapping, buckets)
                    bucket = bucket_for_record(op, mapping, buckets)
                    demand_key = (str(op["phase"]), int(op["logical_checkpoint"]), int(op["layer"]), bucket)
                    demands[key][demand_key][category(op)] += weight
                    if op["access_kind"] == "rmw":
                        rmw[key][(str(op["phase"]), int(op["logical_checkpoint"]), int(op["layer"]), tuple(op["record_identity"]))] += weight
                    head_key = (str(op["phase"]), int(op["logical_checkpoint"]), int(op["layer"]), int(op["kv_head"]))
                    fanout[key][head_key].add(bucket)
                    head_demand[key][head_key] += weight

    rows = []
    for curve, mapping, buckets in demands:
        rows.extend(_summarize_one(context, curve, mapping, buckets, demands[(curve, mapping, buckets)], rmw[(curve, mapping, buckets)], fanout[(curve, mapping, buckets)], head_demand[(curve, mapping, buckets)]))
    return rows


def _summarize_one(context: tuple[str, str, int, str], curve: str, mapping: str, buckets: int, demand: dict[tuple[str, int, int, int], Counter[str]], rmw: Counter[tuple[str, int, int, tuple[Any, ...]]], fanout: dict[tuple[str, int, int, int], set[int]], head_demand: Counter[tuple[str, int, int, int]]) -> list[dict[str, Any]]:
    by_phase: dict[str, list[tuple[tuple[str, int, int, int], Counter[str]]]] = defaultdict(list)
    for key, counts in demand.items():
        by_phase[key[0]].append((key, counts))
    rows = []
    for issue in ISSUE_UNITS:
        phase_rows = {}
        hotspots = []
        for phase in PHASES:
            entries = by_phase[phase]
            total_values = [sum(counts.values()) for _, counts in entries]
            control_values = [counts["control"] for _, counts in entries]
            span_values = [counts["span"] for _, counts in entries]
            ownership_values = [counts["ownership"] for _, counts in entries]
            shortfalls = [max(0, value - issue) for value in total_values]
            rmw_values = [value for (p, _, _, _), value in rmw.items() if p == phase]
            rmw_shortfalls = [max(0, value - issue) for value in rmw_values]
            runs = []
            for (p, layer, bucket), checkpoints in _hot_checkpoint_sets(entries, issue).items():
                if p == phase:
                    runs.append(contiguous_run(checkpoints, phase))
            head_values = [value for (p, _, _, _), value in head_demand.items() if p == phase]
            skew_values = _head_skews(head_demand, phase)
            phase_rows[phase] = {
                "total_bucket_demand": distribution(total_values), "control_bucket_demand": distribution(control_values), "span_bucket_demand": distribution(span_values), "ownership_bucket_demand": distribution(ownership_values),
                "same_epoch_abstract_shortfall": sum(shortfalls), "peak_same_epoch_abstract_shortfall": max(shortfalls, default=0),
                "same_record_rmw_demand": distribution(rmw_values), "same_record_rmw_abstract_serialization": sum(rmw_shortfalls), "peak_same_record_rmw_abstract_serialization": max(rmw_shortfalls, default=0),
                "head_checkpoint_bucket_fanout": distribution([len(value) for key, value in fanout.items() if key[0] == phase]), "per_head_checkpoint_demand": distribution(head_values), "per_head_skew_ratio": distribution(skew_values), "contiguous_hot_logical_checkpoint_runs": distribution(runs),
            }
            for (key, counts), value, shortfall in zip(entries, total_values, shortfalls):
                hotspots.append({"phase": phase, "logical_checkpoint": key[1], "layer": key[2], "abstract_bucket": key[3], "total_demand": value, "control_demand": counts["control"], "span_demand": counts["span"], "ownership_demand": counts["ownership"], "abstract_shortfall": shortfall})
        hotspots.sort(key=lambda row: (-row["abstract_shortfall"], -row["total_demand"], row["logical_checkpoint"], row["layer"], row["abstract_bucket"]))
        all_entries = [item for phase in PHASES for item in by_phase[phase]]
        rows.append({
            "anchor": context[0], "workload": context[1], "evaluation_horizon_append_opportunities": context[2], "organization_label": context[3], "record_curve": curve, "record_bucket_mapping": mapping, "abstract_bucket_count_per_layer": buckets, "abstract_issue_units_per_bucket_per_logical_checkpoint": issue,
            "all_phase_total_bucket_demand": distribution([sum(counts.values()) for _, counts in all_entries]), "phase_rows": phase_rows, "top_hotspots": hotspots[:5],
        })
    return rows


def _hot_checkpoint_sets(entries: list[tuple[tuple[str, int, int, int], Counter[str]]], issue: int) -> dict[tuple[str, int, int], list[int]]:
    output: dict[tuple[str, int, int], list[int]] = defaultdict(list)
    for (phase, checkpoint, layer, bucket), counts in entries:
        if sum(counts.values()) > issue:
            output[(phase, layer, bucket)].append(checkpoint)
    return output


def _head_skews(head_demand: Counter[tuple[str, int, int, int]], phase: str) -> list[float]:
    grouped: dict[tuple[int, int], list[int]] = defaultdict(list)
    for (p, checkpoint, layer, _), value in head_demand.items():
        if p == phase:
            grouped[(checkpoint, layer)].append(value)
    return [max(values) / (sum(values) / len(values)) for values in grouped.values() if values]


def main() -> None:
    args = parse_args()
    a46821, a468220 = validate_inputs(args)
    if args.preflight_only:
        print("A4.6.8.2.2.1 preflight passed: A4.6.8.2.1/A4.6.8.2.2.0 contracts, guards, and record trace hash validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    current = None
    ops: list[dict[str, Any]] = []
    seen = set()
    rows: list[dict[str, Any]] = []
    trace_count = 0
    with gzip.open(args.a468220_trace, "rt", encoding="utf-8") as handle:
        for line in handle:
            op = json.loads(line)
            if op.get("schema_version") != A468220_TRACE_SCHEMA:
                raise ValueError("unexpected A4.6.8.2.2.0 record trace schema")
            key = context_key(op)
            if current is None:
                current = key
            if key != current:
                if current in seen:
                    raise ValueError("record trace context reappeared after closure")
                seen.add(current); rows.extend(summarize_context(current, ops)); current, ops = key, []
            ops.append(op); trace_count += 1
    if current is not None:
        if current in seen:
            raise ValueError("final record trace context reappeared after closure")
        rows.extend(summarize_context(current, ops))
    if trace_count != int(a468220["record_access_trace"]["record_count"]):
        raise AssertionError("record trace count mismatch")
    contexts = {(row["anchor"], row["workload"], row["evaluation_horizon_append_opportunities"], row["organization_label"]) for row in rows}
    expected_contexts = {(row["anchor"], row["workload"], row["evaluation_horizon_append_opportunities"], row["organization_label"]) for row in a46821["sensitivity_rows"]}
    if contexts != expected_contexts or len(rows) != len(contexts) * len(CURVES) * len(MAPPINGS) * len(BUCKET_COUNTS) * len(ISSUE_UNITS):
        raise AssertionError("unexpected A4.6.8.2.2.1 coverage")
    config = {"record_curves": list(CURVES), "record_bucket_mappings": list(MAPPINGS), "abstract_bucket_counts_per_layer": list(BUCKET_COUNTS), "abstract_issue_units_per_bucket_per_logical_checkpoint": list(ISSUE_UNITS), "mapping_boundary": "mapping is separate from fixed pending organization/FIFO/grants and is not a physical bank or port selection", "fanout_definition": "distinct abstract buckets touched by records for one phase/checkpoint/layer/head; it is a logical organization complexity indicator, not simultaneous physical accesses", "boundary": "No descriptor width, physical layout/address, bytes, payload movement, HBM/DMA traffic, port, bank, cycle, timing, latency, throughput, energy, area, capacity, hardware parameter, architecture specification, or RTL is selected or inferred."}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model functional observer over the fixed A4.6.8.2.2.0 logical record trace; abstract issue sensitivity is not physical banking, ports, timing, or cost", "input_artifacts": {"a46821_report_sha256": sha256_file(args.a46821_report), "a468220_report_sha256": sha256_file(args.a468220_report), "a468220_trace_sha256": sha256_file(args.a468220_trace)}, "record_trace_validation": {"schema_version": A468220_TRACE_SCHEMA, "record_count": trace_count, "sha256": sha256_file(args.a468220_trace)}, "sensitivity_rows": rows, "semantic_guards": {"a46821_and_a468220_hash_bound_contracts_validated": True, "fixed_record_trace_fifo_grants_source_and_order_not_rescheduled": True, "conservative_and_strict_record_curves_kept_separate": True, "record_mapping_axis_separate_from_pending_organization": True, "control_span_ownership_and_same_record_rmw_pressures_separated": True, "cross_bucket_fanout_phase_checkpoint_head_definition_explicit": True, "shortfall_and_serialization_do_not_propagate_or_change_replay": True, "p95_p99_contiguous_hot_run_and_per_head_skew_reported": True, "qwen_llama_rows_separate": True, "no_model_runtime_profiler_or_hardware_parameter_loaded": True, "no_payload_movement_or_physical_cost_inferred": True, "no_drop_fallback_migration_backing_or_protection_action": True}}
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a468221_record_organization_sensitivity_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.8.2.2.1 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} rows={len(rows)} record_trace={trace_count}")


if __name__ == "__main__":
    main()
