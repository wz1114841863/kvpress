#!/usr/bin/env python3
"""A4.11.2b external-storage trace-on lifecycle binding gate (no timing claim)."""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import DynamicCache, pipeline

from kvpress.route_a_attention import RouteALifecycleTransitionRecorder
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAQwenExternalColdStorageAttentionBackendSet
from kvpress.route_a_qwen_cache import RouteAQwenMultiLayerExternalColdCache
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a412_whole_decode_gate import answer_hash, read_source, token_ids_hash
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


SCHEMA = "kvzap-route-a4112b-external-storage-lifecycle-1.0"
ALL_LAYERS = tuple(range(36))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.11.2b external-storage lifecycle binding gate. It is untimed and is not a hardware queue measurement.")
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
    p.add_argument("--require-single-visible-cuda-device", action="store_true")
    p.add_argument("--preflight-only", action="store_true", help="Validate fixed A4.11.1/replay inputs without model loading or output.")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_heads(model) -> dict[int, tuple[int, ...]]:
    language_model = model.model.language_model if hasattr(model.model, "language_model") else model.model
    if len(language_model.layers) != len(ALL_LAYERS):
        raise ValueError("A4.11.2b is fixed to the 36-layer Qwen3-8B model")
    return {
        layer: tuple(range(int(language_model.layers[layer].self_attn.config.num_key_value_heads)))
        for layer in ALL_LAYERS
    }


def validate_fixed_inputs(args: argparse.Namespace) -> tuple[dict[int, dict[tuple[int, int], tuple[bool, float]]], dict[str, Any], str, dict[str, Any]]:
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512:
        raise ValueError("A4.11.2b requires all layers/all KV heads and admission budget 512")
    if args.page_tokens != 64 or args.window_size != 128 or args.max_new_tokens != 8 or args.context_repetitions != 12:
        raise ValueError("A4.11.2b fixed Qwen lifecycle configuration differs from A4.11.1")
    if (args.model_name, args.model_revision, args.predictor_name, args.predictor_revision) != (DEFAULT_MODEL, GATE_B_MODEL_REVISION, DEFAULT_PREDICTOR, GATE_A_PREDICTOR_REVISION):
        raise ValueError("A4.11.2b is fixed to Qwen3-8B and the frozen KVzap predictor revisions")
    report = json.loads(args.a4111_report.read_text(encoding="utf-8"))
    if report.get("schema_version") != "kvzap-route-a4111-trace-off-measurement-matrix-1.0" or report.get("status") != "complete":
        raise ValueError("A4.11.1 report is incomplete or incompatible")
    rows = {row.get("workload"): row for row in report.get("input_artifacts", {}).get("workloads", [])}
    row = rows.get(args.preset)
    if row is None or row.get("same_mask_dense_route_a_token_digest_equal") is not True:
        raise ValueError("A4.11.1 exact-token external-storage guard is absent for this workload")
    events, source, digest = read_source(args.replay_source_dir, args=args, layers=ALL_LAYERS)
    if row.get("replay_event_file_sha256") != digest:
        raise ValueError("A4.11.1 replay-mask source differs from supplied A4.11.2b source")
    return events, source, digest, row


def require_one_cuda_device(args: argparse.Namespace) -> dict[str, Any]:
    count = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
    state = {"cuda_available": bool(torch.cuda.is_available()), "visible_cuda_device_count": count}
    if args.require_single_visible_cuda_device and count != 1:
        raise RuntimeError("A4.11.2b requires exactly one visible CUDA device")
    return state


def final_state(backend: RouteAQwenExternalColdStorageAttentionBackendSet, cache: RouteAQwenMultiLayerExternalColdCache, heads: dict[int, tuple[int, ...]]) -> dict[str, Any]:
    backend.assert_replay_complete()
    backend.assert_external_storage_interface_complete()
    cache.assert_target_storage_contracts(adapters_by_layer=backend.external_adapters_by_layer())
    rows = []
    for layer in ALL_LAYERS:
        adapter = backend.backends[layer].external_cold_storage
        if adapter is None:
            raise AssertionError("external storage was not initialized for a selected layer")
        rows.append({
            "layer": layer,
            "heads": [{"kv_head": head, **adapter.state.state_summary(head)} for head in heads[layer]],
            "external_storage": cache.target_storage_summary(layer_idx=layer, adapter=adapter),
        })
    return {"layers": rows}


def coverage_complete(coverage: dict[str, Any], heads: dict[int, tuple[int, ...]]) -> None:
    rows = coverage.get("layers", [])
    if [row.get("layer") for row in rows] != list(ALL_LAYERS):
        raise AssertionError("external-storage coverage lacks a selected layer")
    for row in rows:
        layer = int(row["layer"])
        if row.get("selected_kv_heads") != list(heads[layer]):
            raise AssertionError("external-storage coverage lacks a selected KV head")


def run_dense(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, events, args: argparse.Namespace, heads: dict[int, tuple[int, ...]]) -> dict[str, Any]:
    backend = DenseSameMaskAttentionBackendSet(pipe.model, None, layers=ALL_LAYERS, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode="record_only", execution_dtype_close_mode="quantization_aware_enforce", ulp_breach_sample_limit=args.ulp_breach_sample_limit, replay_mask_events=events)
    seed_everything(args.seed)
    with torch.no_grad(), backend:
        cache = DynamicCache()
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        answer, token_ids = pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True)
    backend.assert_replay_complete(); coverage_complete(backend.coverage(), heads); assert_no_runtime_mask_state(pipe.model)
    return {"answer_sha256": answer_hash(answer), "generated_token_count": len(token_ids), "generated_token_ids_sha256": token_ids_hash(token_ids), "replay_complete": True}


def run_external(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, events, args: argparse.Namespace, heads: dict[int, tuple[int, ...]], recorder: RouteALifecycleTransitionRecorder | None) -> dict[str, Any]:
    backend = RouteAQwenExternalColdStorageAttentionBackendSet(pipe.model, None, layers=ALL_LAYERS, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode="record_only", execution_dtype_close_mode="quantization_aware_enforce", ulp_breach_sample_limit=args.ulp_breach_sample_limit, replay_mask_events=events, lifecycle_transition_recorder=recorder)
    seed_everything(args.seed)
    with torch.no_grad(), backend:
        cache = RouteAQwenMultiLayerExternalColdCache(selected_kv_heads_by_layer=heads)
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        answer, token_ids = pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True)
    state = final_state(backend, cache, heads); coverage = backend.coverage(); coverage_complete(coverage, heads); assert_no_runtime_mask_state(pipe.model)
    return {"answer_sha256": answer_hash(answer), "generated_token_count": len(token_ids), "generated_token_ids_sha256": token_ids_hash(token_ids), "replay_complete": True, "coverage": coverage, "final_state": state, "final_state_sha256": stable_hash(state)}


def write_trace(path: Path, recorder: RouteALifecycleTransitionRecorder) -> dict[str, Any]:
    summary = recorder.summary()
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in recorder.events:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return {"schema_version": recorder.SCHEMA, "path": path.name, "sha256": sha256_file(path), "summary": summary, "recording_semantics": "external-storage scalar state before maturity, after maturity, and after bounded logical admission service; no timestamps, hardware queue events, or physical commit observation"}


def main() -> None:
    args = parse_args()
    events, source, event_sha256, a4111_row = validate_fixed_inputs(args)
    if args.preflight_only:
        print("A4.11.2b preflight passed: fixed A4.11.1 external-storage token guard and replay source validated; no model or output created.")
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
    recorder = RouteALifecycleTransitionRecorder()
    trace_on = run_external(pipe=pipe, context_ids=context_ids, question_ids=question_ids, events=events, args=args, heads=heads, recorder=recorder)
    if trace_off["generated_token_ids_sha256"] != trace_on["generated_token_ids_sha256"]:
        raise AssertionError("trace-on external storage changed the exact generated-token digest")
    if dense["generated_token_ids_sha256"] != trace_on["generated_token_ids_sha256"]:
        raise AssertionError("trace-on external storage differs from same-mask dense token digest")
    if trace_off["final_state"] != trace_on["final_state"]:
        raise AssertionError("lifecycle recorder changed external packed/pending/cold final state")
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key not in {"output_dir", "preflight_only"}}
    args.output_dir.mkdir(parents=True)
    trace = write_trace(args.output_dir / "a4112b_external_storage_lifecycle.jsonl.gz", recorder)
    manifest = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(),
        "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "a4111_binding": {"report": str(args.a4111_report), "report_sha256": sha256_file(args.a4111_report), "measurement_manifest": a4111_row["measurement"], "measurement_sha256": a4111_row["measurement_sha256"], "a4111_same_mask_dense_route_a_token_digest_equal": True},
        "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "event_count": source["event_count"], "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json")},
        "outcomes": {"same_mask_dense": dense, "external_storage_trace_off": trace_off, "external_storage_trace_on": trace_on}, "lifecycle_transition_trace": trace,
        "observational_guards": {"trace_armed_before_external_storage_prefill": True, "trace_off_trace_on_generated_token_ids_equal": True, "trace_on_same_mask_dense_generated_token_ids_equal": True, "replay_mask_consumption_complete_all_paths": True, "all_layers_all_kv_heads_external_storage_covered": True, "recorder_final_packed_pending_cold_state_unchanged": True, "no_drop_or_reorder_or_new_full_kv_fallback": True, "policy_reference_not_used_as_correctness_oracle": True, "timestamps_recorded": False},
        "boundaries": ["This is the final A4 software-to-model binding gate. It is not a timing, allocator, HBM, queue-depth, throughput, energy, area, architecture, or RTL result.", "The recorder observes scalar external-storage reference lifecycle state only. It does not expose ready groups, micro-op completion, bank ports, RMW service, physical commit timing, or credit latency."],
        "cuda_environment": cuda, "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__),
    }
    path = args.output_dir / "a4112b_external_storage_lifecycle_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.11.2b external-storage lifecycle complete: {path} sha256={sha256_file(path)}")


if __name__ == "__main__":
    main()
