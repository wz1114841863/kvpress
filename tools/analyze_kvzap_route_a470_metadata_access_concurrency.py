#!/usr/bin/env python3
"""A4.7.0 metadata-access concurrency contract over fixed Route-A record traces."""
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
from tools.analyze_kvzap_route_a468220_metadata_recordization import SCHEMA as A468220_SCHEMA, TRACE_SCHEMA as TRACE_SCHEMA
from tools.analyze_kvzap_route_a468221_record_organization_sensitivity import SCHEMA as A468221_SCHEMA, bucket_for_record, curve_weight
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

SCHEMA = "kvzap-route-a470-metadata-access-concurrency-1.0"
# These literals are part of the preregistered A4.7.0 contract.  Do not add
# edge kinds after inspecting a workload: new dependencies require a new study.
EDGE_TYPES = ("same-record", "same-head-control", "span-lifecycle", "ownership-order")
CURVES = ("conservative", "strict_same_record")
MAPPINGS = ("all_record_striped_v1", "head_source_affine_v1", "control_affine_span_striped_v1", "hierarchical_control_span_v1")
BUCKET_COUNTS = (1, 2, 4, 8)
PHASES = ("activation", "steady_state_append", "steady_state_dequeue")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.7.0 no-model metadata dependency/concurrency contract; logical work only, never timing or physical hardware.")
    parser.add_argument("--a468220-report", type=Path, required=True)
    parser.add_argument("--a468220-trace", type=Path, required=True)
    parser.add_argument("--a468221-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate bound reports, guards, and trace hash without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def percentile(values: Iterable[float], fraction: float) -> float | None:
    values = sorted(values)
    if not values:
        return None
    return values[max(0, min(len(values) - 1, int((len(values) - 1) * fraction)))]


def distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    values = list(values)
    return {"count": len(values), "p50": percentile(values, .50), "p95": percentile(values, .95), "p99": percentile(values, .99), "max": max(values) if values else None, "sum": sum(values)}


def context_key(op: dict[str, Any]) -> tuple[str, str, int, str]:
    return (str(op["anchor"]), str(op["workload"]), int(op["evaluation_horizon_append_opportunities"]), str(op["organization_label"]))


def phase_stride(phase: str) -> int:
    return 1 if phase == "activation" else 2


def contiguous(checkpoints: Iterable[int], phase: str) -> int:
    values = sorted(set(checkpoints))
    if not values:
        return 0
    run = best = 1
    for old, new in zip(values, values[1:]):
        run = run + 1 if new - old == phase_stride(phase) else 1
        best = max(best, run)
    return best


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    a468220 = read_completed(args.a468220_report, A468220_SCHEMA, "A4.6.8.2.2.0")
    a468221 = read_completed(args.a468221_report, A468221_SCHEMA, "A4.6.8.2.2.1")
    trace_sha = sha256_file(args.a468220_trace)
    if a468220.get("record_access_trace", {}).get("schema_version") != TRACE_SCHEMA or a468220["record_access_trace"].get("sha256") != trace_sha:
        raise ValueError("A4.6.8.2.2.0 record trace manifest mismatch")
    if a468221.get("input_artifacts", {}).get("a468220_report_sha256") != sha256_file(args.a468220_report) or a468221.get("input_artifacts", {}).get("a468220_trace_sha256") != trace_sha:
        raise ValueError("A4.6.8.2.2.1 does not hash-bind supplied A4.6.8.2.2.0 inputs")
    required = ("a4682_and_a46821_hash_bound_contracts_validated", "a46821_primitive_totals_and_context_coverage_matched", "fixed_fifo_oldest_source_ownership_and_grants_not_rescheduled", "strict_merge_never_crosses_birth_source_or_order_boundary", "conservative_and_strict_curves_explainable_and_count_conserved")
    if not all(a468220.get("semantic_guards", {}).get(name) is True for name in required):
        raise ValueError("A4.6.8.2.2.0 semantic guards incomplete")
    if not all(a468221.get("semantic_guards", {}).get(name) is True for name in ("a46821_and_a468220_hash_bound_contracts_validated", "fixed_record_trace_fifo_grants_source_and_order_not_rescheduled", "conservative_and_strict_record_curves_kept_separate", "control_span_ownership_and_same_record_rmw_pressures_separated")):
        raise ValueError("A4.6.8.2.2.1 semantic guards incomplete")
    return a468220, a468221


def dependencies(ops: list[dict[str, Any]], curve: str) -> tuple[list[dict[str, Any]], Counter[str]]:
    """Return fixed-order nodes with only the four preregistered direct edges."""
    last_record_checkpoint: dict[tuple[Any, ...], int] = {}
    last_control_checkpoint: dict[tuple[Any, ...], int] = {}
    last_span: dict[tuple[Any, ...], tuple[int, int]] = {}
    last_owner: dict[tuple[Any, ...], tuple[int, int]] = {}
    nodes = []
    edge_totals: Counter[str] = Counter()
    for index, op in enumerate(ops):
        phase, checkpoint = str(op["phase"]), int(op["logical_checkpoint"])
        record_id = (str(op["record_type"]), *tuple(op["record_identity"]))
        head_id = (int(op["layer"]), int(op["kv_head"]))
        node = {"index": index, "phase": phase, "checkpoint": checkpoint, "layer": head_id[0], "head": head_id[1], "source": op.get("source") or "control", "weight": curve_weight(op, curve), "record_type": str(op["record_type"]), "record_id": record_id, "edges": []}
        record_scope = (phase, checkpoint, record_id)
        if record_scope in last_record_checkpoint:
            node["edges"].append(("same-record", last_record_checkpoint[record_scope]))
        last_record_checkpoint[record_scope] = index
        if node["record_type"] in {"frontier_control", "selection_control"}:
            control_scope = (phase, checkpoint, head_id)
            if control_scope in last_control_checkpoint:
                node["edges"].append(("same-head-control", last_control_checkpoint[control_scope]))
            last_control_checkpoint[control_scope] = index
        if node["record_type"] == "span_descriptor":
            if record_id in last_span and last_span[record_id][0] != checkpoint:
                node["edges"].append(("span-lifecycle", last_span[record_id][1]))
            last_span[record_id] = (checkpoint, index)
        if node["record_type"] == "ownership_link":
            if record_id in last_owner and last_owner[record_id][0] != checkpoint:
                node["edges"].append(("ownership-order", last_owner[record_id][1]))
            last_owner[record_id] = (checkpoint, index)
        for name, _ in node["edges"]:
            edge_totals[name] += 1
        nodes.append(node)
    return nodes, edge_totals


def phase_summary(nodes: list[dict[str, Any]], phase: str, mapping: str, bucket_count: int) -> dict[str, Any]:
    phase_nodes = [node for node in nodes if node["phase"] == phase]
    selected = {node["index"] for node in phase_nodes}
    dp: dict[int, int] = {}
    edge_counts: Counter[str] = Counter()
    by_checkpoint: dict[int, list[dict[str, Any]]] = defaultdict(list)
    by_head_checkpoint: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for node in phase_nodes:
        parents = [dp[parent] for kind, parent in node["edges"] if parent in selected]
        dp[node["index"]] = node["weight"] + max(parents, default=0)
        for kind, parent in node["edges"]:
            if parent in selected:
                edge_counts[kind] += 1
        by_checkpoint[node["checkpoint"]].append(node)
        by_head_checkpoint[(node["checkpoint"], node["layer"], node["head"])].append(node)
    checkpoint_critical = []
    checkpoint_work = []
    checkpoint_parallel = []
    dependency_checkpoints = []
    for checkpoint, checkpoint_nodes in by_checkpoint.items():
        ids = {node["index"] for node in checkpoint_nodes}
        local_dp: dict[int, int] = {}
        for node in checkpoint_nodes:
            local_dp[node["index"]] = node["weight"] + max([local_dp[parent] for _, parent in node["edges"] if parent in ids], default=0)
        work, critical = sum(node["weight"] for node in checkpoint_nodes), max(local_dp.values(), default=0)
        checkpoint_work.append(work); checkpoint_critical.append(critical); checkpoint_parallel.append(1.0 - critical / work if work else 0.0)
        if any(parent in ids for node in checkpoint_nodes for _, parent in node["edges"]):
            dependency_checkpoints.append(checkpoint)
    fanouts = []
    skew = []
    for _, head_nodes in by_head_checkpoint.items():
        touched = {bucket_for_record({"record_type": node["record_type"], "record_identity": list(node["record_id"][1:]), "layer": node["layer"], "kv_head": node["head"], "source": node["source"]}, mapping, bucket_count) for node in head_nodes}
        fanouts.append(len(touched))
    grouped_heads: dict[tuple[int, int], list[int]] = defaultdict(list)
    for (checkpoint, layer, _), head_nodes in by_head_checkpoint.items():
        grouped_heads[(checkpoint, layer)].append(sum(node["weight"] for node in head_nodes))
    for values in grouped_heads.values():
        skew.append(max(values) / (sum(values) / len(values)))
    total = sum(node["weight"] for node in phase_nodes)
    critical = max(dp.values(), default=0)
    return {"total_record_work": total, "critical_path_work": critical, "critical_path_work_fraction": critical / total if total else 0.0, "parallel_record_work_fraction": 1.0 - critical / total if total else 0.0, "dependency_edge_counts": {name: edge_counts[name] for name in EDGE_TYPES}, "checkpoint_total_work": distribution(checkpoint_work), "checkpoint_critical_path_work": distribution(checkpoint_critical), "checkpoint_parallel_record_work_fraction": distribution(checkpoint_parallel), "dependency_bearing_contiguous_checkpoint_run": contiguous(dependency_checkpoints, phase), "head_checkpoint_cross_bucket_fanout": distribution(fanouts), "per_head_skew_ratio": distribution(skew)}


def summarize_context(context: tuple[str, str, int, str], ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for curve in CURVES:
        nodes, _ = dependencies(ops, curve)
        for mapping in MAPPINGS:
            for buckets in BUCKET_COUNTS:
                rows.append({"anchor": context[0], "workload": context[1], "evaluation_horizon_append_opportunities": context[2], "organization_label": context[3], "record_curve": curve, "record_bucket_mapping": mapping, "abstract_bucket_count_per_layer": buckets, "phase_rows": {phase: phase_summary(nodes, phase, mapping, buckets) for phase in PHASES}})
    return rows


def main() -> None:
    args = parse_args()
    a468220, a468221 = validate_inputs(args)
    if args.preflight_only:
        print("A4.7.0 preflight passed: A4.6.8.2.2.0/A4.6.8.2.2.1 contracts, guards, and record-trace hash validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    current = None; ops: list[dict[str, Any]] = []; seen = set(); rows: list[dict[str, Any]] = []; trace_count = 0
    with gzip.open(args.a468220_trace, "rt", encoding="utf-8") as handle:
        for line in handle:
            op = json.loads(line)
            if op.get("schema_version") != TRACE_SCHEMA:
                raise ValueError("unexpected A4.6.8.2.2.0 record trace schema")
            key = context_key(op)
            if current is None: current = key
            if key != current:
                if current in seen: raise ValueError("record trace context reappeared after closure")
                seen.add(current); rows.extend(summarize_context(current, ops)); current, ops = key, []
            ops.append(op); trace_count += 1
    if current is not None:
        if current in seen: raise ValueError("final record trace context reappeared after closure")
        rows.extend(summarize_context(current, ops))
    if trace_count != int(a468220["record_access_trace"]["record_count"]): raise AssertionError("record trace count mismatch")
    contexts = {(r["anchor"], r["workload"], r["evaluation_horizon_append_opportunities"], r["organization_label"]) for r in rows}
    expected = {(r["anchor"], r["workload"], r["evaluation_horizon_append_opportunities"], r["organization_label"]) for r in a468221["sensitivity_rows"]}
    if contexts != expected or len(rows) != len(contexts) * len(CURVES) * len(MAPPINGS) * len(BUCKET_COUNTS): raise AssertionError("unexpected A4.7.0 coverage")
    config = {"preregistered_dependency_edge_types": list(EDGE_TYPES), "record_curves": list(CURVES), "record_bucket_mappings": list(MAPPINGS), "abstract_bucket_counts_per_layer": list(BUCKET_COUNTS), "critical_path_definition": "weighted longest path in a phase-induced fixed-order logical dependency graph; logical work units are not cycles", "parallel_work_definition": "1 - critical_path_work / total_record_work; not measured hardware parallelism or throughput", "boundary": "No edge, work, fanout, or ratio selects physical layout, descriptor width, address, byte, payload movement, HBM/DMA traffic, bank, port, cycle, timing, latency, throughput, energy, area, capacity, architecture specification, or RTL."}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model functional fixed-order dependency analysis over trace-derived logical record operations; critical-path work is not hardware timing", "input_artifacts": {"a468220_report_sha256": sha256_file(args.a468220_report), "a468220_trace_sha256": sha256_file(args.a468220_trace), "a468221_report_sha256": sha256_file(args.a468221_report)}, "record_trace_validation": {"schema_version": TRACE_SCHEMA, "record_count": trace_count, "sha256": sha256_file(args.a468220_trace)}, "dependency_rows": rows, "semantic_guards": {"a468220_and_a468221_hash_bound_contracts_validated": True, "fixed_record_trace_fifo_grants_source_and_order_not_rescheduled": True, "only_four_preregistered_dependency_edge_types_emitted": True, "each_edge_derives_from_fixed_order_identity_and_declared_scope": True, "no_cross_birth_source_or_fifo_order_merge_or_reordering": True, "critical_path_and_parallel_work_defined_in_logical_work_only": True, "activation_append_and_dequeue_reported_separately": True, "qwen_llama_rows_separate": True, "no_model_runtime_profiler_or_hardware_parameter_loaded": True, "no_payload_movement_or_physical_cost_inferred": True, "no_drop_fallback_migration_backing_or_protection_action": True}}
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a470_metadata_access_concurrency_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.7.0 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} rows={len(rows)} record_trace={trace_count}")


if __name__ == "__main__": main()
