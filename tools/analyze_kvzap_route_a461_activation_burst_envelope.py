#!/usr/bin/env python3
"""A4.6.1 hash-bound logical activation-commit / append envelope analysis."""
from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

SCHEMA = "kvzap-route-a461-activation-burst-logical-envelope-1.0"
A442_SCHEMA = "kvzap-route-a442-cross-anchor-activation-contract-1.0"
A460_SCHEMA = "kvzap-route-a460-route-a-active-steady-state-gate-1.0"
WORKLOADS = ("retrieval", "summarization", "reasoning")
ACTIVATION_FIELDS = ("matured_kept_tokens", "matured_dropped_tokens", "pending_tokens_after_commit", "admitted_tokens", "hot_tokens_after_commit", "packed_tokens_after_commit", "logical_page_count_after_commit")
APPEND_FIELDS = ("matured_kept_tokens", "matured_dropped_tokens", "admitted_tokens", "pending_tokens_before_maturity", "pending_tokens_after_maturity", "pending_tokens_after_service", "packed_tokens_before", "packed_tokens_after_service", "packed_page_count_after_service")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.6.1 hash-bound activation logical-envelope analysis; no model execution, hardware traffic, timing, or parameter selection.")
    p.add_argument("--a442-report", type=Path, required=True)
    p.add_argument("--qwen-a460-report", type=Path, required=True)
    p.add_argument("--llama-a460-report", type=Path, required=True)
    p.add_argument("--preflight-only", action="store_true", help="Validate reports/traces without creating output.")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def integer_summary(values: Iterable[int]) -> dict[str, int]:
    xs = sorted(map(int, values))
    if not xs:
        raise ValueError("cannot summarize an empty logical field")
    def q(point: int) -> int:
        return xs[(len(xs) - 1) * point // 100]
    return {"count": len(xs), "sum": sum(xs), "min": xs[0], "p50": q(50), "p95": q(95), "p99": q(99), "max": xs[-1]}


def read_completed(path: Path, schema: str, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} report absent: {path}")
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("schema_version") != schema or result.get("status") != "complete":
        raise ValueError(f"{label} is not a completed {schema} report")
    return result


def resolve_trace(report_path: Path, relative: str) -> Path:
    # A4.6.0 stores the trace relative to analysis/experiments, not its own dir.
    if not relative or Path(relative).is_absolute():
        raise ValueError("A4.6.0 trace path must be nonempty and experiments-relative")
    trace = report_path.parents[1] / relative
    if not trace.is_file():
        raise FileNotFoundError(f"A4.6.0 logical trace absent: {trace}")
    return trace


def load_trace(report_path: Path, entry: dict[str, Any], layers: int) -> list[dict[str, Any]]:
    trace = resolve_trace(report_path, str(entry.get("path", "")))
    if sha256_file(trace) != entry.get("sha256"):
        raise ValueError(f"A4.6.0 logical trace hash mismatch: {trace}")
    with gzip.open(trace, "rt", encoding="utf-8") as f:
        events = [json.loads(line) for line in f]
    if len(events) != int(entry.get("event_count", -1)) or not events:
        raise ValueError("A4.6.0 logical trace event count mismatch")
    if {int(x.get("layer", -1)) for x in events} != set(range(layers)):
        raise ValueError("A4.6.0 logical trace has incomplete layer coverage")
    if any(x.get("timestamps_recorded") is not False or x.get("phase") != "decode" or x.get("input_token_count") != 1 for x in events):
        raise ValueError("A4.6.0 trace is not timestamp-free q_len=1 decode evidence")
    return events


def validate_and_summarize_trace(events: list[dict[str, Any]], *, expected_layers: int, expected_heads: int) -> tuple[dict[str, Any], list[dict[str, int]]]:
    streams: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        for head in event.get("heads", []):
            streams[(int(event["layer"]), int(head["kv_head"]))].append(head)
    expected = {(layer, head) for layer in range(expected_layers) for head in range(expected_heads)}
    if set(streams) != expected:
        raise ValueError("A4.6.0 trace has incomplete layer/KV-head coverage")
    lengths = {len(v) for v in streams.values()}
    if len(lengths) != 1 or next(iter(lengths)) <= 0:
        raise ValueError("A4.6.0 trace has inconsistent post-commit append coverage")
    flat: list[dict[str, int]] = []
    for (layer, head), rows in sorted(streams.items()):
        for opportunity, row in enumerate(rows):
            if any(not isinstance(row.get(k), int) or int(row[k]) < 0 for k in APPEND_FIELDS):
                raise ValueError("A4.6.0 trace lacks nonnegative logical append field")
            if int(row["pending_tokens_after_maturity"]) != int(row["pending_tokens_before_maturity"]) + int(row["matured_kept_tokens"]):
                raise ValueError("pending-after-maturity conservation failure")
            if int(row["pending_tokens_after_service"]) != int(row["pending_tokens_after_maturity"]) - int(row["admitted_tokens"]):
                raise ValueError("pending-after-service conservation failure")
            if int(row["packed_tokens_after_service"]) != int(row["packed_tokens_before"]) + int(row["admitted_tokens"]):
                raise ValueError("packed-after-service conservation failure")
            flat.append({"layer": layer, "kv_head": head, "stream_append_opportunity": opportunity, **{k: int(row[k]) for k in APPEND_FIELDS}})
    return {"layer_kv_head_stream_count": len(streams), "post_commit_append_opportunities_per_stream": next(iter(lengths)), "event_count": len(events), "timestamps_recorded": False, "per_event_conservation_checked": True}, flat


def activation_rows(layers: list[dict[str, Any]], *, expected_layers: int, expected_heads: int) -> list[dict[str, int]]:
    if len(layers) != expected_layers or {int(row.get("layer", -1)) for row in layers} != set(range(expected_layers)):
        raise ValueError("A4.6.0 activation summary has incomplete layer coverage")
    rows: list[dict[str, int]] = []
    for layer in layers:
        event = layer.get("activation_event")
        if not layer.get("activation_committed") or layer.get("mode_at_trace_end") != "route_a_active" or not isinstance(event, dict):
            raise ValueError("A4.6.0 active activation contract changed")
        if (event.get("mode_before_commit"), event.get("mode_after_commit")) != ("full_kv_bypass", "route_a_active"):
            raise ValueError("A4.6.0 activation mode boundary changed")
        heads = event.get("heads")
        if not isinstance(heads, list) or len(heads) != expected_heads:
            raise ValueError("A4.6.0 activation event has incomplete KV-head coverage")
        for head in heads:
            if any(not isinstance(head.get(k), int) or int(head[k]) < 0 for k in ACTIVATION_FIELDS):
                raise ValueError("A4.6.0 activation event has incomplete logical inventory")
            rows.append({"layer": int(layer["layer"]), "kv_head": int(head["kv_head"]), **{k: int(head[k]) for k in ACTIVATION_FIELDS}})
    return sorted(rows, key=lambda row: (row["layer"], row["kv_head"]))


def summarize_workload(*, report_path: Path, report: dict[str, Any], anchor: str, workload: str, layers: int, heads: int) -> dict[str, Any]:
    row = report.get("per_workload", {}).get(workload)
    if not isinstance(row, dict):
        raise ValueError(f"{anchor}/{workload}: A4.6.0 workload absent")
    active = row.get("route_a_active_contract", {})
    tail = row.get("finite_horizon_tail_analysis", {})
    if active.get("full_kv_fallback_or_protection_entered") is not False or active.get("forced_token_inputs_equal_full_kv") is not True:
        raise ValueError(f"{anchor}/{workload}: A4.6.0 active path contract changed")
    if tail.get("sustained_non_decreasing_pending_growth_witness_count") != 0 or tail.get("tail_pending_after_service_max") != 0:
        raise ValueError(f"{anchor}/{workload}: A4.6.0 tail gate did not pass")
    activation = activation_rows(active.get("deferred_activation_summary", {}).get("layers", []), expected_layers=layers, expected_heads=heads)
    trace_contract, append = validate_and_summarize_trace(load_trace(report_path, row.get("post_commit_logical_trace", {}), layers), expected_layers=layers, expected_heads=heads)
    return {"anchor": anchor, "workload": workload, "context_tokens": int(row["request"]["context_tokens"]), "activation_commit_logical_inventory_by_layer_kv_head": activation, "activation_commit_logical_inventory_summary": {k: integer_summary(x[k] for x in activation) for k in ACTIVATION_FIELDS}, "post_commit_logical_append_events_by_layer_kv_head": append, "post_commit_logical_append_event_summary": {k: integer_summary(x[k] for x in append) for k in APPEND_FIELDS}, "post_commit_trace_contract": trace_contract, "finite_tail_gate": {k: tail[k] for k in ("tail_decode_events_per_layer", "layer_kv_head_stream_count", "sustained_non_decreasing_pending_growth_witness_count", "tail_pending_after_service_max")}, "interpretation": "Two source-separated timestamp-free logical inventories. Integer summaries cover recorded layer/KV-head rows, not hardware demand envelopes."}


def validate_anchor(*, a442: dict[str, Any], a442_path: Path, report_path: Path, anchor: str) -> dict[str, Any]:
    report = read_completed(report_path, A460_SCHEMA, anchor)
    if sha256_file(a442_path) != report.get("provenance", {}).get("a442_report_sha256"):
        raise ValueError(f"{anchor}: A4.6.0 does not bind this A4.4.2 report")
    source = a442.get("input_artifacts", {}).get(anchor, {})
    if not source.get("report_sha256"):
        raise ValueError(f"{anchor}: A4.4.2 anchor source absent")
    structure = report.get("model_structure", {}); layers = int(structure.get("layer_count", 0)); heads_by_layer = structure.get("kv_head_count_by_layer", {})
    if layers <= 0 or {int(k) for k in heads_by_layer} != set(range(layers)) or len({int(v) for v in heads_by_layer.values()}) != 1:
        raise ValueError(f"{anchor}: incomplete uniform model structure")
    heads = int(next(iter(heads_by_layer.values())))
    return {"anchor": anchor, "a460_report_path": str(report_path), "a460_report_sha256": sha256_file(report_path), "a460_schema": A460_SCHEMA, "a442_anchor_source_report_sha256": source["report_sha256"], "layer_count": layers, "kv_head_count_per_layer": heads, "workload_rows": [summarize_workload(report_path=report_path, report=report, anchor=anchor, workload=w, layers=layers, heads=heads) for w in WORKLOADS]}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a442 = read_completed(args.a442_report, A442_SCHEMA, "A4.4.2")
    qwen = validate_anchor(a442=a442, a442_path=args.a442_report, report_path=args.qwen_a460_report, anchor="qwen3_8b")
    llama = validate_anchor(a442=a442, a442_path=args.a442_report, report_path=args.llama_a460_report, anchor="llama31_8b_instruct")
    if args.preflight_only:
        print("A4.6.1 preflight passed: hash-bound A4.4.2 and six A4.6.0 logical traces; no output created.")
        return
    config = {"a442_report": str(args.a442_report), "qwen_a460_report": str(args.qwen_a460_report), "llama_a460_report": str(args.llama_a460_report), "comparison_rule": "per-anchor/per-workload separate activation-commit and post-commit logical inventories; no cross-anchor numeric pooling or hardware parameter derivation"}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model hash-bound analysis of functional timestamp-free lifecycle inventories; trace-derived logical workload inputs only, not measured or modeled hardware evidence", "input_artifacts": {x["anchor"]: {k: x[k] for k in ("a460_report_path", "a460_report_sha256", "a460_schema", "a442_anchor_source_report_sha256", "layer_count", "kv_head_count_per_layer")} for x in (qwen, llama)}, "anchor_rows": [r for x in (qwen, llama) for r in x["workload_rows"]], "observational_guards": {"a442_hash_bound_by_each_a460_report": True, "all_six_anchor_workload_rows_kept_separate": True, "all_activation_commits_route_a_active": True, "all_post_commit_traces_hash_checked_timestamp_free": True, "all_post_commit_head_conservation_checked": True, "a460_finite_tail_gate_passed_each_row": True, "activation_and_post_commit_sources_explicitly_separated": True, "cross_anchor_numeric_pooling_or_parameter_derivation_absent": True, "no_model_or_runtime_loaded": True, "no_hardware_parameter_selected": True}, "boundaries": ["A4.6.1 separates recorded logical activation-commit inventory from subsequent q_len=1 logical append opportunities. Neither source has arrival/service time or physical transfer semantics.", "The integer distributions are per anchor/workload layer/KV-head reference-state accounting, not FIFO occupancy/capacity, service rate, overflow, physical allocation/capacity, bytes, HBM/DMA traffic, bursts, bank/page/PTE requirements, timing, latency, throughput, energy, area, architecture specification, or RTL evidence.", "Qwen and Llama remain separate. This report neither pools, normalizes, range-reduces, nor derives a common hardware envelope or parameter from their fixed-request counts.", "A later explicit resource model may choose and declare service/backing assumptions, then consume these source-separated inputs. A4.6.1 does not make those assumptions or establish net benefit."]}
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a461_activation_burst_logical_envelope_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.1 activation logical envelope completed: {output}")


if __name__ == "__main__":
    main()
