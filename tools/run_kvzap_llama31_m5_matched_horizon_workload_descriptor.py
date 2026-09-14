#!/usr/bin/env python3
"""M5 matched-horizon Llama Route-A source/fan-in descriptor.

This is a bounded functional and timestamp-free logical-event study.  It
replays an online same-mask dense source exactly once through Route-A and
records the existing Route-A logical source/merge events.  The events are not
source-ready timestamps, service times, or hardware measurements.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from huggingface_hub import snapshot_download
from transformers import pipeline

from kvpress.route_a_attention import RouteALogicalEventRecorder
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAPolicyAttentionBackendSet
from tools.analyze_kvzap_llama31_m4_bounded_workload_envelope import M4_SCHEMA
from tools.analyze_kvzap_llama31_m41_summarization_ulp_diagnostic import M41_SCHEMA
from tools.export_kvzap_predictor_trace import assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_llama31_m1_semantic_gate import (
    EXPECTED_STRUCTURE,
    answer_hash,
    assert_all_layer_head_coverage,
    assert_numerical_guard_work,
    make_predictor,
    read_completed_m0,
    source_coverage,
    validate_runtime_structure,
)
from tools.run_kvzap_llama31_m2_lifecycle_gate import (
    read_completed_m1,
)
from tools.run_kvzap_trace import build_builtin_request, seed_everything
from tools.validate_kvzap_llama31_m0_provenance import (
    DEFAULT_MODEL_REPO,
    DEFAULT_MODEL_REVISION,
    OFFICIAL_PREDICTOR_REPO,
)


M5_SCHEMA = "kvzap-llama31-m5-matched-horizon-workload-descriptor-1.0"
EVENT_SCHEMA = RouteALogicalEventRecorder.SCHEMA
WORKLOADS = ("retrieval", "summarization", "reasoning")
SOURCES = ("hot", "pending", "packed")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_completed(path: Path, schema: str, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != schema or value.get("status") != "complete":
        raise ValueError(f"{label} is not a completed {schema} artifact")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M5 matched-horizon Llama source/fan-in logical-event descriptor; no timing or hardware study."
    )
    parser.add_argument("--m0-manifest", type=Path, required=True)
    parser.add_argument("--m1-manifest", type=Path, required=True)
    parser.add_argument("--m4-report", type=Path, required=True)
    parser.add_argument("--m41-report", type=Path, required=True)
    parser.add_argument("--presets", nargs="+", choices=WORKLOADS, default=list(WORKLOADS))
    parser.add_argument("--model-name", default=DEFAULT_MODEL_REPO)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--predictor-repo-id-override", required=True)
    parser.add_argument("--threshold", type=float, default=-7.0)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--page-tokens", type=int, default=64, help="Functional reference input; not a hardware choice.")
    parser.add_argument("--admission-budget", type=int, default=512, help="Functional reference input; not a hardware choice.")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--max-new-tokens", type=int, default=8, help="Matched declared decode cap; actual policy calls are separately checked.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--execution-dtype-ulp-mode", choices=("enforce", "record_only"), default="record_only")
    parser.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    return sorted(values)[int((len(values) - 1) * fraction)]


def write_events(path: Path, events: list[dict[str, Any]]) -> str:
    """Write deterministic gzip JSONL; mtime is provenance only, never time data."""
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            for event in events:
                compressed.write(json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n")
    return sha256_file(path)


def validate_event_summary(summary: dict[str, Any], *, layers: int, heads: int) -> None:
    count = int(summary.get("event_count", -1))
    if count <= 0 or int(summary.get("merge_event_count", -1)) != count or summary.get("timestamps_recorded") is not False:
        raise ValueError("M5 logical-event summary has invalid event/merge/timestamp fields")
    expected = {layer: list(range(heads)) for layer in range(layers)}
    actual = {int(row["layer"]): list(row["kv_heads"]) for row in summary.get("observed_layer_kv_heads", [])}
    if actual != expected:
        raise ValueError("M5 logical events do not cover every Llama layer and KV head")
    for source in SOURCES:
        row = summary.get("by_source", {}).get(source, {})
        if int(row.get("partial_attention_events", -1)) + int(row.get("empty_source_skip_events", -1)) != count:
            raise ValueError(f"M5 {source} source decisions do not partition logical merges")


def _record_distribution(rows: list[dict[str, Any]], source: str) -> dict[str, Any]:
    values = [int(row["record_count"]) for row in rows if row["source"] == source and row["outcome"] == "partial"]
    return {"sample_count": len(values), "sum": sum(values), "p50": percentile(values, 0.50), "p95": percentile(values, 0.95), "max": max(values, default=None)}


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    combinations: Counter[str] = Counter()
    fan_in: Counter[str] = Counter()
    all_decisions: list[dict[str, Any]] = []
    pages: list[int] = []
    tails: list[int] = []
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        decisions = event["source_decisions"]
        active = [row["source"] for row in decisions if row["outcome"] == "partial"]
        combinations["+".join(active)] += 1
        fan_in[f"{len(active)}_active_sources"] += 1
        all_decisions.extend(decisions)
        pages.append(int(event["packed_page_count"]))
        tails.append(int(event["packed_tail_tokens"]))
        grouped[(int(event["layer"]), int(event["kv_head"]))].append(event)
    count = len(events)
    if count <= 0 or sum(fan_in.values()) != count:
        raise ValueError("M5 event accounting is incomplete")

    def group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        group_combinations: Counter[str] = Counter()
        group_fan_in: Counter[str] = Counter()
        group_decisions: list[dict[str, Any]] = []
        group_pages, group_tails = [], []
        for event in rows:
            decisions = event["source_decisions"]
            active = [row["source"] for row in decisions if row["outcome"] == "partial"]
            group_combinations["+".join(active)] += 1
            group_fan_in[f"{len(active)}_active_sources"] += 1
            group_decisions.extend(decisions)
            group_pages.append(int(event["packed_page_count"]))
            group_tails.append(int(event["packed_tail_tokens"]))
        return {
            "logical_event_count": len(rows),
            "fan_in_counts": dict(sorted(group_fan_in.items())),
            "source_combination_counts": dict(sorted(group_combinations.items())),
            "source_record_count_distribution": {source: _record_distribution(group_decisions, source) for source in SOURCES},
            "packed_page_tail_distribution": {"p50": percentile(group_pages, .50), "p95": percentile(group_pages, .95), "max": max(group_pages), "tail_p50": percentile(group_tails, .50), "tail_p95": percentile(group_tails, .95), "tail_max": max(group_tails)},
        }

    return {
        "logical_event_count": count,
        "source_outcome_counts": {source: {"partial": sum(row["source"] == source and row["outcome"] == "partial" for row in all_decisions), "skip": sum(row["source"] == source and row["outcome"] == "skip" for row in all_decisions)} for source in SOURCES},
        "fan_in_fractions": {name: value / count for name, value in sorted(fan_in.items())},
        "source_combination_fractions": {name: value / count for name, value in sorted(combinations.items())},
        "source_record_count_distribution": {source: _record_distribution(all_decisions, source) for source in SOURCES},
        "packed_page_tail_distribution": {"p50": percentile(pages, .50), "p95": percentile(pages, .95), "max": max(pages), "tail_p50": percentile(tails, .50), "tail_p95": percentile(tails, .95), "tail_max": max(tails)},
        "per_layer_kv_head": [
            {"layer": layer, "kv_head": head, **group_summary(rows)}
            for (layer, head), rows in sorted(grouped.items())
        ],
    }


def spread(rows: dict[str, dict[str, Any]], field: str) -> dict[str, dict[str, float]]:
    keys = sorted({key for row in rows.values() for key in row[field]})
    return {
        key: {
            "min": min(float(row[field].get(key, 0.0)) for row in rows.values()),
            "max": max(float(row[field].get(key, 0.0)) for row in rows.values()),
            "range": max(float(row[field].get(key, 0.0)) for row in rows.values()) - min(float(row[field].get(key, 0.0)) for row in rows.values()),
        }
        for key in keys
    }


def validate_prior_contracts(*, args: argparse.Namespace, m0_sha256: str, m1_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    m4 = load_completed(args.m4_report, M4_SCHEMA, label="M4 report")
    m41 = load_completed(args.m41_report, M41_SCHEMA, label="M4.1 report")
    shared = m4.get("shared_provenance", {})
    inputs = shared.get("matched_functional_reference_inputs", {})
    if shared.get("m0_manifest_sha256") != m0_sha256 or shared.get("m1_manifest_sha256") != m1_sha256:
        raise ValueError("M5 M4 provenance does not bind the supplied M0/M1 manifests")
    expected = {"threshold": -7.0, "window_size": 128, "page_tokens": 64, "packing_admission_budget": 512, "max_new_tokens": 8, "context_repetitions": 12, "max_executed_dtype_ulps": 16.0, "execution_dtype_ulp_mode": "record_only", "ulp_breach_sample_limit": 32}
    if any(inputs.get(name) != value for name, value in expected.items()):
        raise ValueError("M5 requires the completed M4 matched functional-reference contract")
    m41_m4 = m41.get("config", {}).get("m4_report", {})
    if m41_m4.get("sha256") != sha256_file(args.m4_report):
        raise ValueError("M4.1 does not hash-bind the supplied M4 report")
    if m41.get("m41_decision", {}).get("strict_16_ulp_contract_for_summarization") != "not passed; recorded breaches remain explicit":
        raise ValueError("M5 requires M4.1's explicit non-strict summarization ULP context")
    if not all(m4.get("observational_guards", {}).values()) or not all(m41.get("observational_guards", {}).values()):
        raise ValueError("M5 requires complete M4 and M4.1 observational guards")
    return m4, m41


def generate(pipe, request: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    seed_everything(args.seed)
    return pipe(str(request["context"]), question=str(request["question"]), max_new_tokens=args.max_new_tokens, enable_thinking=False)


def run_workload(*, workload: str, pipe, args: argparse.Namespace, revision: str, layers: int, heads: int, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    request = build_builtin_request(workload, args.context_repetitions)
    tokens = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    if int(tokens["context_ids"].shape[1]) <= args.window_size:
        raise ValueError(f"M5 {workload} request does not exceed the protected hot window")
    print(f"M5 {workload}: Full-KV bypass...", flush=True)
    full = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)
    selected_layers = tuple(range(layers))
    predictor = make_predictor(predictor_revision=revision, override=args.predictor_repo_id_override)
    dense_backend = DenseSameMaskAttentionBackendSet(
        pipe.model, predictor, layers=selected_layers, kv_head=None, threshold=args.threshold,
        window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget,
        rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps,
        execution_dtype_ulp_mode=args.execution_dtype_ulp_mode,
        ulp_breach_sample_limit=args.ulp_breach_sample_limit,
    )
    print(f"M5 {workload}: online same-mask dense source...", flush=True)
    with torch.no_grad(), dense_backend:
        dense = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)
    dense_coverage = dense_backend.coverage()
    assert_all_layer_head_coverage(dense_coverage, expected_layers=layers, expected_kv_heads=heads, label=f"M5 {workload} dense")
    assert_numerical_guard_work(dense_backend.same_mask_numerical_guard_work_summary(), layers, label=f"M5 {workload} dense")
    recorder = RouteALogicalEventRecorder()
    route_backend = RouteAPolicyAttentionBackendSet(
        pipe.model, None, layers=selected_layers, kv_head=None, threshold=args.threshold,
        window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget,
        rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps,
        execution_dtype_ulp_mode=args.execution_dtype_ulp_mode,
        ulp_breach_sample_limit=args.ulp_breach_sample_limit, replay_mask_events=dense_backend.mask_events(),
        elide_empty_sources=True, logical_event_recorder=recorder,
    )
    print(f"M5 {workload}: Route-A exact-mask replay with untimed event recorder...", flush=True)
    with torch.no_grad(), route_backend:
        route = generate(pipe, request, args)
    assert_no_runtime_mask_state(pipe.model)
    route_backend.assert_replay_complete()
    if dense_backend.mask_events() != route_backend.mask_events():
        raise AssertionError(f"M5 {workload}: Route-A replay events differ from online dense source")
    route_coverage = route_backend.coverage()
    assert_all_layer_head_coverage(route_coverage, expected_layers=layers, expected_kv_heads=heads, label=f"M5 {workload} Route-A")
    assert_numerical_guard_work(route_backend.same_mask_numerical_guard_work_summary(), layers, label=f"M5 {workload} Route-A")
    sources = source_coverage(route_backend.comparisons)
    if not sources["hot_observed"] or not sources["packed_observed"]:
        raise AssertionError(f"M5 {workload}: required hot/packed source is absent")
    summary = recorder.summary()
    validate_event_summary(summary, layers=layers, heads=heads)
    event_path = output_dir / "llama31_m5_ordered_logical_attention_events.jsonl.gz"
    event_sha256 = write_events(event_path, recorder.events)
    actual_calls = set(route_backend.policy_decode_calls.values())
    if len(actual_calls) != 1:
        raise ValueError(f"M5 {workload}: policy-decode calls differ across layers")
    return {
        "request": {"request_id": request["request_id"], "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}), "context_tokens": int(tokens["context_ids"].shape[1])},
        "full_kv_bypass": {"answer_sha256": answer_hash(full), "zero_route_a_admission": True},
        "online_same_mask_dense": {"answer_sha256": answer_hash(dense), "policy_decode_call_count_by_layer": dense_backend.policy_decode_calls, "policy_coverage": dense_coverage, "same_mask_numerical_guard_work": dense_backend.same_mask_numerical_guard_work_summary(), "execution_dtype_ulp_breach_summary": dense_backend.execution_dtype_ulp_breach_summary()},
        "replayed_same_mask_route_a": {"answer_sha256": answer_hash(route), "policy_decode_call_count_by_layer": route_backend.policy_decode_calls, "policy_coverage": route_coverage, "source_coverage": sources, "same_mask_numerical_guard_work": route_backend.same_mask_numerical_guard_work_summary(), "execution_dtype_ulp_breach_summary": route_backend.execution_dtype_ulp_breach_summary()},
        "same_mask_pairing": {"mode": "replayed_online_dense_mask", "route_a_replay_consumption_complete": True, "answer_digest_equal": answer_hash(dense) == answer_hash(route)},
        "logical_event_artifact": {"schema_version": EVENT_SCHEMA, "path": str(event_path.relative_to(output_dir.parents[1])), "sha256": event_sha256, "event_count": len(recorder.events), "recording_semantics": "global logical attention invocation order; no source completion, reduction arrival, Python timestamp, CUDA timestamp, or hardware time"},
        "logical_event_summary": summary,
        "actual_policy_decode_calls": actual_calls.pop(),
        "descriptor": summarize_events(recorder.events),
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if sorted(args.presets) != sorted(WORKLOADS) or len(set(args.presets)) != len(WORKLOADS):
        raise ValueError("M5 requires retrieval, summarization, and reasoning exactly once")
    if (args.model_name, args.model_revision, args.predictor_repo_id_override, args.threshold, args.window_size, args.page_tokens, args.admission_budget, args.context_repetitions, args.max_new_tokens, args.max_executed_dtype_ulps, args.execution_dtype_ulp_mode, args.ulp_breach_sample_limit) != (DEFAULT_MODEL_REPO, DEFAULT_MODEL_REVISION, OFFICIAL_PREDICTOR_REPO, -7.0, 128, 64, 512, 12, 8, 16.0, "record_only", 32):
        raise ValueError("M5 is fixed to the M4 matched Llama functional-reference contract and explicit record-only ULP context")
    if min(args.rtol, args.atol, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit) <= 0:
        raise ValueError("invalid M5 numerical guard dimensions")
    if args.device != "cuda":
        raise ValueError("M5 is bounded to the cached CUDA model environment")
    m0 = read_completed_m0(args.m0_manifest)
    m0_sha256 = sha256_file(args.m0_manifest)
    m1 = read_completed_m1(args.m1_manifest, m0_sha256=m0_sha256)
    m1_sha256 = sha256_file(args.m1_manifest)
    m4, m41 = validate_prior_contracts(args=args, m0_sha256=m0_sha256, m1_sha256=m1_sha256)
    revision = str(m1["config"]["predictor_revision"])
    args.output_dir.mkdir(parents=True)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    started = {"schema_version": M5_SCHEMA, "status": "started", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "boundaries": ["M5 is an untimed functional/logical-event study, not a performance benchmark.", "The M4.1 summarization record-only ULP context remains explicit and cannot select numerical hardware parameters."]}
    (args.output_dir / "llama31_m5_matched_horizon_started.json").write_text(json.dumps(started, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    print(f"Loading M5 base model: {args.model_name}", flush=True)
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise AssertionError("loaded base model revision differs from M0/M1")
    layers, heads = validate_runtime_structure(pipe.model)
    if (layers, heads) != (EXPECTED_STRUCTURE["layer_count"], EXPECTED_STRUCTURE["kv_head_count"]):
        raise AssertionError("loaded model dimensions differ from fixed M5 structure")
    snapshot = Path(snapshot_download(repo_id=OFFICIAL_PREDICTOR_REPO, revision=revision))
    if snapshot.name != revision:
        raise AssertionError("resolved Linear predictor snapshot differs from M1")
    per_workload = {workload: run_workload(workload=workload, pipe=pipe, args=args, revision=revision, layers=layers, heads=heads, output_dir=args.output_dir / workload) for workload in args.presets}
    calls = {row["actual_policy_decode_calls"] for row in per_workload.values()}
    if len(calls) != 1:
        raise ValueError(f"M5 matched declared cap produced unequal actual policy-decode-call counts: {sorted(calls)}")
    summaries = {workload: row["descriptor"] for workload, row in per_workload.items()}
    report = {
        "schema_version": M5_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "fixed-request functional and timestamp-free logical-event evidence; no modeled or measured hardware evidence",
        "provenance": {"m0_manifest_sha256": m0_sha256, "m1_manifest_sha256": m1_sha256, "m4_report_sha256": sha256_file(args.m4_report), "m41_report_sha256": sha256_file(args.m41_report), "predictor_revision": revision, "predictor_snapshot_path": str(snapshot), "m4_matched_functional_reference_inputs": m4["shared_provenance"]["matched_functional_reference_inputs"], "m41_strict_ulp_context": m41["m41_decision"]["strict_16_ulp_contract_for_summarization"]},
        "per_workload": per_workload,
        "cross_workload": {"workloads": list(args.presets), "shared_actual_policy_decode_calls": calls.pop(), "fan_in_fraction_spread": spread(summaries, "fan_in_fractions"), "source_combination_fraction_spread": spread(summaries, "source_combination_fractions"), "interpretation": "Three fixed Llama requests share one declared cap and actual policy-decode-call count. Their normalized descriptors can be compared with Qwen A4.2.8 fields, but neither set is a workload distribution or a common hardware envelope."},
        "observational_guards": {"m0_m1_m4_m41_hash_bound": True, "m41_non_strict_summarization_context_retained": True, "full_kv_bypass_zero_route_a_admission_each_workload": all(row["full_kv_bypass"]["zero_route_a_admission"] for row in per_workload.values()), "all_32_layers_all_8_kv_heads_covered_each_workload": True, "online_dense_mask_replayed_exactly_once_each_workload": True, "same_mask_numerical_guard_work_executed_each_workload": True, "all_workloads_hot_packed_observed": all(row["replayed_same_mask_route_a"]["source_coverage"]["hot_observed"] and row["replayed_same_mask_route_a"]["source_coverage"]["packed_observed"] for row in per_workload.values()), "event_source_decisions_partition_merges_each_workload": True, "event_all_layer_all_kv_head_coverage_each_workload": True, "logical_events_have_no_timestamps": True, "shared_actual_policy_decode_calls": True, "no_hardware_parameter_selected": True},
        "boundaries": ["M5 records logical invocation order and source partial-or-skip decisions only. It contains no source-ready or completion timestamps, queue/FIFO occupancy, backpressure, cycles, latency, throughput, HBM traffic, energy, area, hardware acceleration, architecture specification, or RTL evidence.", "The explicit record-only mode retains the completed M4.1 summarization strict-16-ULP non-pass; it does not weaken the default M2 guard or establish a merge precision.", "Cross-model field alignment is semantic/descriptor alignment, not proof that Qwen3-8B and Llama require identical hardware or that Route-A transfers to arbitrary models or pruning algorithms."],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    output = args.output_dir / "llama31_m5_matched_horizon_workload_descriptor_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"M5 matched-horizon Llama descriptor completed: {output}")


if __name__ == "__main__":
    main()
