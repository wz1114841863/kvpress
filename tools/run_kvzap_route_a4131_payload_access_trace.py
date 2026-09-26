#!/usr/bin/env python3
"""A4.13.1 direct scalar Route-A payload-access trace; deliberately untimed."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from transformers import DynamicCache, pipeline

from kvpress.route_a_attention import RouteALifecycleTransitionRecorder, RouteALogicalEventRecorder
from kvpress.route_a_policy_backend import RouteAQwenExternalColdStorageAttentionBackendSet
from kvpress.route_a_qwen_cache import RouteAQwenMultiLayerExternalColdCache
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a4112b_external_storage_lifecycle import ALL_LAYERS, answer_hash, coverage_complete, expected_heads, final_state, read_source, run_dense, run_external, sha256_file, token_ids_hash, validate_fixed_inputs
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


SCHEMA = "kvzap-route-a4131-payload-access-trace-1.0"
EXPECTED_A4112B = ("kvzap-route-a4112b-external-storage-binding-1.0", "57da81a6fb7e3a9540fad2d0a45ba28ae418ffc69d9e81ef2fbf02090dcdc3a3")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.13.1 prefill-armed external-storage payload-access recorder. It records scalar logical source traversal counts only; it is not a timing, HBM traffic, PPA, or RTL run.")
    request = p.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    p.add_argument("--request-id")
    p.add_argument("--context-repetitions", type=int, default=12)
    p.add_argument("--model-name", default=DEFAULT_MODEL)
    p.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    p.add_argument("--predictor-name", default=DEFAULT_PREDICTOR)
    p.add_argument("--predictor-revision", default=GATE_A_PREDICTOR_REVISION)
    p.add_argument("--threshold", type=float, default=-4.0)
    p.add_argument("--window-size", type=int, default=128)
    p.add_argument("--page-tokens", type=int, default=64)
    p.add_argument("--admission-budget", type=int, required=True)
    p.add_argument("--target-layers", nargs="+", default=["all"])
    p.add_argument("--target-kv-head", choices=("all",), default="all")
    p.add_argument("--max-new-tokens", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--rtol", type=float, default=1e-4)
    p.add_argument("--atol", type=float, default=1e-5)
    p.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    p.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    p.add_argument("--device", default="cuda")
    p.add_argument("--replay-source-dir", type=Path, required=True)
    p.add_argument("--a4111-report", type=Path, required=True)
    p.add_argument("--a4112b-report", type=Path, required=True, help="Exact accepted A4.11.2b binding report.")
    p.add_argument("--require-single-visible-cuda-device", action="store_true")
    p.add_argument("--preflight-only", action="store_true", help="Validate frozen inputs without loading a model or creating output.")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def validate_accepted_binding(path: Path, workload: str) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != EXPECTED_A4112B[1]:
        raise ValueError("A4.13.1 requires the exact accepted A4.11.2b binding report")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != EXPECTED_A4112B[0] or report.get("status") != "complete":
        raise ValueError("A4.11.2b report is incomplete or schema-incompatible")
    row = next((item for item in report.get("workloads", []) if item.get("workload") == workload), None)
    if row is None or not isinstance(row.get("exact_generated_token_ids_sha256"), str):
        raise ValueError("A4.11.2b workload/digest binding is absent")
    guards = report.get("semantic_guards", {})
    needed = ("a4111_external_storage_exact_token_guard_remains_bound", "trace_on_external_storage_is_token_identical_to_trace_off_and_dense", "prefill_armed_external_storage_lifecycle_observed", "fixed_a410_parameters_not_retuned", "unmapped_hardware_fields_not_synthesized")
    if not all(guards.get(key) is True for key in needed):
        raise ValueError("A4.11.2b semantic binding guard is incomplete")
    return row


def write_gzip_jsonl(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return {"path": path.name, "sha256": sha256_file(path), "event_count": len(rows), "timestamps_recorded": False}


def require_one_cuda_device(args: argparse.Namespace) -> dict[str, Any]:
    count = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
    state = {"cuda_available": bool(torch.cuda.is_available()), "visible_cuda_device_count": count}
    if args.require_single_visible_cuda_device and count != 1:
        raise RuntimeError("A4.13.1 requires exactly one visible CUDA device")
    return state


def validate_payload_events(recorder: RouteALogicalEventRecorder, heads: dict[int, tuple[int, ...]]) -> dict[str, Any]:
    summary = recorder.summary()
    if not recorder.events:
        raise AssertionError("A4.13.1 observed no Route-A logical attention events")
    observed = {int(row["layer"]): tuple(int(head) for head in row["kv_heads"]) for row in summary["observed_layer_kv_heads"]}
    if observed != heads:
        raise AssertionError("A4.13.1 logical attention trace lacks all selected layers/KV heads")
    for expected, event in enumerate(recorder.events):
        if event.get("logical_event_sequence") != expected or event.get("merge_after_source_decisions") is not True:
            raise AssertionError("logical attention event ordering/merge guard failed")
        rows = event.get("source_decisions", [])
        if [row.get("source") for row in rows] != ["hot", "pending", "packed"]:
            raise AssertionError("logical attention source order changed")
        if any(not isinstance(row.get("record_count"), int) or row["record_count"] < 0 for row in rows):
            raise AssertionError("logical attention trace has invalid source count")
    return summary


def main() -> None:
    args = parse_args()
    # This reuses the fixed A4.11.2b preflight, including its A4.11.1/replay binding.
    events, _source, event_sha256, a4111_row = validate_fixed_inputs(args)
    accepted = validate_accepted_binding(args.a4112b_report, args.preset)
    if args.preflight_only:
        print("A4.13.1 preflight passed: A4.11.1/replay plus exact A4.11.2b external-storage binding validated; no model or output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    cuda = require_one_cuda_device(args)
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    heads = expected_heads(pipe.model)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids, question_ids = tokenized["context_ids"].to(pipe.model.device), tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size:
        raise ValueError("request does not create prefill maturity")
    dense = run_dense(pipe=pipe, context_ids=context_ids, question_ids=question_ids, events=events, args=args, heads=heads)
    trace_off = run_external(pipe=pipe, context_ids=context_ids, question_ids=question_ids, events=events, args=args, heads=heads, recorder=None)
    lifecycle_recorder, payload_recorder = RouteALifecycleTransitionRecorder(), RouteALogicalEventRecorder()
    trace_on = run_external(pipe=pipe, context_ids=context_ids, question_ids=question_ids, events=events, args=args, heads=heads, recorder=lifecycle_recorder, logical_event_recorder=payload_recorder)
    if dense["generated_token_ids_sha256"] != trace_on["generated_token_ids_sha256"] or trace_off["generated_token_ids_sha256"] != trace_on["generated_token_ids_sha256"]:
        raise AssertionError("A4.13.1 recorder changed exact external-storage generated tokens")
    if trace_on["generated_token_ids_sha256"] != accepted["exact_generated_token_ids_sha256"]:
        raise AssertionError("A4.13.1 external-storage tokens differ from accepted A4.11.2b binding")
    if trace_off["final_state"] != trace_on["final_state"]:
        raise AssertionError("A4.13.1 recorders changed packed/pending/cold final state")
    lifecycle_summary = lifecycle_recorder.summary()
    payload_summary = validate_payload_events(payload_recorder, heads)
    args.output_dir.mkdir(parents=True)
    lifecycle_trace = write_gzip_jsonl(args.output_dir / "a4131_external_storage_lifecycle.jsonl.gz", lifecycle_recorder.events)
    payload_trace = write_gzip_jsonl(args.output_dir / "a4131_external_storage_payload_access.jsonl.gz", payload_recorder.events)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key not in {"output_dir", "preflight_only"}}
    manifest = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(),
        "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "a4112b_binding": {"report": str(args.a4112b_report), "report_sha256": EXPECTED_A4112B[1], "accepted_workload_token_digest": accepted["exact_generated_token_ids_sha256"]},
        "a4111_binding": {"report": str(args.a4111_report), "report_sha256": sha256_file(args.a4111_report), "measurement_manifest": a4111_row["measurement"], "measurement_sha256": a4111_row["measurement_sha256"]},
        "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256},
        "outcomes": {"same_mask_dense": dense, "external_storage_trace_off": trace_off, "external_storage_trace_on": trace_on},
        "lifecycle_transition_trace": {"schema_version": RouteALifecycleTransitionRecorder.SCHEMA, **lifecycle_trace, "summary": lifecycle_summary, "recording_semantics": "scalar lifecycle state before maturity, after maturity, and after logical admission service; not timing or hardware service"},
        "payload_access_trace": {"schema_version": RouteALogicalEventRecorder.SCHEMA, **payload_trace, "summary": payload_summary, "recording_semantics": "one scalar software-reference Route-A attention evaluation per selected query head, recording hot/pending/packed logical source record counts and merge marker; not physical memory reads, traffic, timing, ports, or bandwidth"},
        "observational_guards": {"payload_recorder_armed_on_prefill_armed_external_storage_path": True, "trace_off_trace_on_generated_token_ids_equal": True, "trace_on_same_mask_dense_generated_token_ids_equal": True, "a4131_token_digest_equals_accepted_a4112b": True, "replay_mask_consumption_complete_all_paths": True, "all_layers_all_kv_heads_external_storage_covered": True, "recorders_final_packed_pending_cold_state_unchanged": True, "no_drop_or_reorder_or_new_full_kv_fallback": True, "timestamps_recorded": False},
        "boundaries": ["The payload-access trace observes scalar list lengths passed to the existing software reference attention. It is not a physical cache access trace, HBM transaction trace, port trace, timing trace, or bandwidth measurement.", "A4.13.1 introduces no pruning, admission, queue, execution-granularity, or scheduling variant. The model/replay/window/page/budget are fixed to the accepted A4.11.2b conditions."],
        "cuda_environment": cuda,
    }
    path = args.output_dir / "a4131_payload_access_trace_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.13.1 payload-access trace complete: {path} sha256={sha256_file(path)} events={payload_trace['event_count']}")


if __name__ == "__main__":
    main()
