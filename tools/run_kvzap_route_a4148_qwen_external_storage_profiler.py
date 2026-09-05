"""A4.1.5 separate profiler attribution for the A4.1.4 external-cache paths.

This is deliberately one fresh-cache diagnostic capture per paired path.  Its
operator counters are not timing repetitions and must never be pooled with
the A4.1.4 measured wall/CUDA-event distributions.
"""

from __future__ import annotations

import argparse
import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from torch.profiler import ProfilerActivity, profile
from transformers import DynamicCache, pipeline

from kvpress.route_a_measurement import cuda_memory_snapshot, initialize_output_directory, require_cuda_device
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAQwenExternalColdStorageAttentionBackendSet
from kvpress.route_a_qwen_cache import RouteAQwenMultiLayerExternalColdCache
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a412_profiler import operator_rows
from tools.run_kvzap_route_a412_whole_decode_gate import answer_hash, read_source, token_ids_hash
from tools.run_kvzap_route_a4142_qwen_multilayer_allhead_native_storage_gate import require_multilayer_replacement
from tools.run_kvzap_route_a4147_qwen_external_storage_whole_decode_measurement import EXTERNAL_STORAGE_PATH, compact_route_state
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


A4148_SCHEMA = "kvzap-route-a4148-qwen-external-storage-profiler-1.0"
PROFILER_PATHS = ("full_kv_bypass", "same_mask_dense_replay", EXTERNAL_STORAGE_PATH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.5 separate torch.profiler attribution for all-layer Qwen external storage. Diagnostic only; not a timing benchmark.")
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--model-name", default=DEFAULT_MODEL)
    parser.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR)
    parser.add_argument("--predictor-revision", default=GATE_A_PREDICTOR_REVISION)
    parser.add_argument("--threshold", type=float, default=-4.0)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--page-tokens", type=int, default=64)
    parser.add_argument("--admission-budget", type=int, required=True)
    parser.add_argument("--target-layers", nargs="+", default=["all"], help="Must be the literal all.")
    parser.add_argument("--target-kv-head", choices=("all",), default="all")
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    parser.add_argument("--warmup-repetitions", type=int, default=1, help="Unprofiled fresh-cache warm-ups per path.")
    parser.add_argument("--top-operators", type=int, default=30)
    parser.add_argument("--export-chrome-traces", action="store_true", help="Also write one potentially large Chrome trace JSON per path.")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--replay-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def make_backend_and_cache(*, path: str, pipe, layers: tuple[int, ...], expected_heads: dict[int, tuple[int, ...]], events, args: argparse.Namespace, component_measure=None):
    if path == "full_kv_bypass":
        return None, DynamicCache()
    common = dict(model=pipe.model, predictor=None, layers=layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode="record_only", execution_dtype_close_mode="quantization_aware_enforce", ulp_breach_sample_limit=args.ulp_breach_sample_limit, replay_mask_events=events, component_measure=component_measure)
    if path == "same_mask_dense_replay":
        return DenseSameMaskAttentionBackendSet(**common), DynamicCache()
    if path == EXTERNAL_STORAGE_PATH:
        return RouteAQwenExternalColdStorageAttentionBackendSet(**common), RouteAQwenMultiLayerExternalColdCache(selected_kv_heads_by_layer=expected_heads)
    raise ValueError(f"unknown A4.1.5 path: {path}")


def run_decode(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, backend, cache, args: argparse.Namespace, profiler=None) -> tuple[str, list[int], dict[str, Any], dict[str, Any]]:
    """Build context state outside profiling, then profile exactly decode."""
    seed_everything(args.seed)
    backend_context = backend if backend is not None else contextlib.nullcontext()
    with torch.no_grad(), backend_context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        before = cuda_memory_snapshot(args.device)
        if profiler is None:
            result = pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True)
        else:
            with profiler:
                result = pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True)
        after = cuda_memory_snapshot(args.device)
    if not isinstance(result, tuple) or len(result) != 2 or not isinstance(result[0], str) or not isinstance(result[1], list) or not result[1]:
        raise AssertionError("A4.1.5 path did not return a nonempty answer/token-ID pair")
    return result[0], result[1], before.__dict__, after.__dict__


def route_guard_summary(*, backend, cache, expected_heads: dict[int, tuple[int, ...]], args: argparse.Namespace) -> dict[str, Any]:
    coverage, storage, pages = require_multilayer_replacement(backend=backend, cache=cache, expected_heads=expected_heads, args=args)
    if any(row["persistent_unselected_kv_heads"] or row["persistent_selected_native_cold_tensor_tokens"] for row in storage["layers"]):
        raise AssertionError("external-storage route profiler path retained prohibited persistent target-layer K/V")
    return compact_route_state(coverage=coverage, page_coverage=pages, ulp=backend.execution_dtype_ulp_breach_summary())


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512:
        raise ValueError("A4.1.5 requires --target-layers all --target-kv-head all --admission-budget 512")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit, args.warmup_repetitions, args.top_operators) <= 0 or args.window_size < 0:
        raise ValueError("invalid A4.1.5 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("A4.1.5 is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    layers = tuple(range(len(language_model.layers)))
    expected_heads = {layer: tuple(range(int(language_model.layers[layer].self_attn.config.num_key_value_heads))) for layer in layers}
    args.resolved_target_layers = list(layers)
    args.resolved_target_kv_heads_by_layer = {str(layer): list(heads) for layer, heads in expected_heads.items()}
    args.require_any_pending = False
    args.require_any_full_multi_tail_packed = True
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=layers)
    if source["config"].get("admission_budget") != args.admission_budget:
        raise ValueError("replay source admission budget differs from A4.1.5 external-storage configuration")
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokenized["context_ids"].to(pipe.model.device)
    question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    config.update({"replay_event_file_sha256": event_sha256, "execution_dtype_ulp_mode": "record_only", "execution_dtype_close_mode": "quantization_aware_enforce", "profiler_scope": "question_forward_plus_greedy_decode_after_untimed_context_prefill"})
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a4148_external_storage_profiler_started.json", schema_version=A4148_SCHEMA, boundaries=["A4.1.5 is one profiler diagnostic per path, not a timing-repetition benchmark.", "The Route-A path uses the A4.1.3 external-storage Qwen cache; Full-KV and same-mask dense are separate controls.", "Profiler device-memory and allocator snapshots are software observations, not HBM traffic, energy, area, throughput, hardware acceleration, or RTL evidence."])
    results: list[dict[str, Any]] = []
    for path in PROFILER_PATHS:
        for warmup in range(args.warmup_repetitions):
            print(f"Unprofiled warm-up {warmup + 1}/{args.warmup_repetitions}: {path}")
            backend, cache = make_backend_and_cache(path=path, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args)
            run_decode(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, cache=cache, args=args)
            assert_no_runtime_mask_state(pipe.model)
            if backend is not None:
                backend.assert_replay_complete()
                if path == EXTERNAL_STORAGE_PATH:
                    route_guard_summary(backend=backend, cache=cache, expected_heads=expected_heads, args=args)
        print(f"Profiled diagnostic: {path}")
        backend, cache = make_backend_and_cache(path=path, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args)
        profiler = profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA], record_shapes=True, profile_memory=True, with_stack=False)
        answer, token_ids, memory_before, memory_after = run_decode(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, cache=cache, args=args, profiler=profiler)
        torch.cuda.synchronize(require_cuda_device(args.device))
        assert_no_runtime_mask_state(pipe.model)
        result: dict[str, Any] = {"path": path, "answer_sha256": answer_hash(answer), "generated_token_count": len(token_ids), "generated_token_ids_sha256": token_ids_hash(token_ids), "memory_before": memory_before, "memory_after": memory_after, "operators": operator_rows(profiler.key_averages(), top_operators=args.top_operators)}
        if args.export_chrome_traces:
            trace_path = args.output_dir / f"a4148_profiler_{path}.json"
            profiler.export_chrome_trace(str(trace_path))
            result["chrome_trace"] = trace_path.name
        if backend is None:
            result["full_kv_bypass_zero_route_a_admission"] = True
        else:
            backend.assert_replay_complete()
            if any(count <= 0 for count in backend.policy_decode_calls.values()):
                raise AssertionError(f"{path} did not execute policy attention in every selected layer")
            result["policy_decode_call_count_by_layer"] = backend.policy_decode_calls
            if path == EXTERNAL_STORAGE_PATH:
                result["external_storage_guard"] = route_guard_summary(backend=backend, cache=cache, expected_heads=expected_heads, args=args)
            else:
                result["execution_dtype_ulp_breach_count"] = sum(int(row["breach_count"]) for row in backend.execution_dtype_ulp_breach_summary()["layers"])
        results.append(result)
    summary_path = args.output_dir / "a4148_external_storage_profiler_operator_summary.json"
    summary_path.write_text(json.dumps({"schema_version": A4148_SCHEMA, "results": results}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"schema_version": A4148_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"], "source_answer_sha256": source["answer_sha256"]}, "operator_summary": summary_path.name, "operator_summary_units": {"device_time_total_us": "generic torch.profiler device time; CUDA in this CUDA-only gate", "device_memory_usage_bytes": "generic torch.profiler device memory accounting; not allocator peak or HBM traffic"}, "source_artifact_sha256": source["source_artifact_sha256"], "observational_guards": {"paired_mask_mode": "replayed_dense_mask", "full_kv_bypass_zero_route_a_admission": True, "route_a_predictor_scored_online": False, "replay_mask_consumption_complete": True, "all_layers_all_kv_heads_external_storage_substituted": True, "persistent_selected_native_cold_absent": True, "required_any_full_multi_tail_packed_coverage": True, "fp32_same_mask_guard": {"rtol": args.rtol, "atol": args.atol}, "execution_dtype_ulp_mode": "record_only", "execution_dtype_close_mode": "quantization_aware_enforce", "execution_dtype_close_enforced": True, "profiler_is_separate_from_timing_repetitions": True, "context_prefill_profiled": False}, "boundaries": ["torch.profiler alters execution; its operator values must not be treated as or pooled into latency/throughput measurements.", "This profiles the Python reference after untimed context prefill; it is not a packed-attention kernel profile.", "Profiler device-memory and allocator fields are software observations, not HBM traffic, energy, area, frequency, hardware acceleration, or RTL evidence."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    manifest_path = args.output_dir / "a4148_external_storage_profiler_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.5 external-storage profiler completed: {manifest_path}")


if __name__ == "__main__":
    main()
