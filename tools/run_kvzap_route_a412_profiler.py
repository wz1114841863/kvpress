"""A4.1.2.1 separate operator profiler for the whole-decode reference paths.

Profiler output is diagnostic only: it identifies where the Python reference
spends operator time and allocator activity.  It is never mixed with A4.1.2
timing repetitions or used as a latency/throughput measurement.
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
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAPolicyAttentionBackendSet
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a412_whole_decode_gate import A412_SCHEMA, answer_hash, manifest_config, read_source, resolve_target_layers, token_ids_hash
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


PROFILER_SCHEMA = "kvzap-route-a412-profiler-diagnostic-1.1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.2.1 separate torch.profiler diagnostic for replayed whole-decode paths; not a timing benchmark.")
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
    parser.add_argument("--target-layers", nargs="+", default=["0", "18", "35"])
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--warmup-repetitions", type=int, default=1, help="Unprofiled fresh-cache warm-ups per path.")
    parser.add_argument("--top-operators", type=int, default=30)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--replay-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def _event_number(event: Any, *fields: str) -> float:
    """Read current generic device fields, with legacy CUDA-field fallback."""
    missing = object()
    for field in fields:
        value = getattr(event, field, missing)
        if value is not missing and value is not None:
            return float(value)
    return 0.0


def operator_rows(events: Any, *, top_operators: int) -> list[dict[str, Any]]:
    """Normalize profiler aggregates without depending on a particular sort table."""
    rows = [
        {
            "operator": str(getattr(event, "key", "<unknown>")),
            "count": int(getattr(event, "count", 0)),
            "self_cpu_time_total_us": _event_number(event, "self_cpu_time_total"),
            "cpu_time_total_us": _event_number(event, "cpu_time_total"),
            "self_device_time_total_us": _event_number(event, "self_device_time_total", "self_cuda_time_total"),
            "device_time_total_us": _event_number(event, "device_time_total", "cuda_time_total"),
            "self_cpu_memory_usage_bytes": _event_number(event, "self_cpu_memory_usage"),
            "cpu_memory_usage_bytes": _event_number(event, "cpu_memory_usage"),
            "self_device_memory_usage_bytes": _event_number(event, "self_device_memory_usage", "self_cuda_memory_usage"),
            "device_memory_usage_bytes": _event_number(event, "device_memory_usage", "cuda_memory_usage"),
        }
        for event in events
    ]
    return sorted(rows, key=lambda row: (row["device_time_total_us"], row["cpu_time_total_us"], row["operator"]), reverse=True)[:top_operators]


def make_backend(*, path: str, model, layers: tuple[int, ...], events, args: argparse.Namespace):
    if path == "same_mask_dense_replay":
        backend_type = DenseSameMaskAttentionBackendSet
    elif path == "same_mask_route_a_replay":
        backend_type = RouteAPolicyAttentionBackendSet
    else:
        return None
    return backend_type(model, None, layers=layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=events)


def execute_decode(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, backend, args: argparse.Namespace, profiler=None) -> tuple[str, list[int], dict[str, Any], dict[str, Any]]:
    """Prefill outside profiling, then execute exactly one profiled decode region."""
    seed_everything(args.seed)
    cache = DynamicCache()
    context = backend if backend is not None else contextlib.nullcontext()
    with torch.no_grad(), context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        before = cuda_memory_snapshot(args.device)
        if profiler is None:
            result = pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True)
        else:
            with profiler:
                result = pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True)
        after = cuda_memory_snapshot(args.device)
    if not isinstance(result, tuple) or len(result) != 2 or not isinstance(result[0], str) or not isinstance(result[1], list):
        raise AssertionError("profiler decode did not return answer plus generated token IDs")
    return result[0], result[1], before.__dict__, after.__dict__


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens, args.max_executed_dtype_ulps, args.warmup_repetitions, args.top_operators) <= 0 or args.window_size < 0:
        raise ValueError("invalid profiler dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("profiler gate is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    layers = resolve_target_layers(args.target_layers, len(language_model.layers))
    args.resolved_target_layers = list(layers)
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=layers)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokenized["context_ids"].to(pipe.model.device)
    question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = manifest_config(args)
    config["replay_event_file_sha256"] = event_sha256
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a412_profiler_started.json", schema_version=PROFILER_SCHEMA, boundaries=["A4.1.2.1 profiler diagnostic; profiler execution is not a timing repetition.", "Context prefill is outside profiler scope; profiler scope is question-forward plus greedy decode.", "Allocator counters are PyTorch allocator bytes, not HBM traffic."])
    paths = ["full_kv_bypass", "same_mask_dense_replay", "same_mask_route_a_replay"]
    results: list[dict[str, Any]] = []
    for path in paths:
        print(f"Unprofiled warm-up(s): {path}")
        for _ in range(args.warmup_repetitions):
            backend = make_backend(path=path, model=pipe.model, layers=layers, events=events, args=args)
            answer, token_ids, _before, _after = execute_decode(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, args=args)
            assert_no_runtime_mask_state(pipe.model)
            if backend is not None:
                backend.assert_replay_complete()
        backend = make_backend(path=path, model=pipe.model, layers=layers, events=events, args=args)
        trace_path = args.output_dir / f"a412_profiler_{path}.json"
        print(f"Profiled diagnostic: {path}")
        profiler = profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA], record_shapes=True, profile_memory=True, with_stack=False)
        answer, token_ids, memory_before, memory_after = execute_decode(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, args=args, profiler=profiler)
        torch.cuda.synchronize(require_cuda_device(args.device))
        profiler.export_chrome_trace(str(trace_path))
        assert_no_runtime_mask_state(pipe.model)
        result: dict[str, Any] = {"path": path, "chrome_trace": trace_path.name, "answer_sha256": answer_hash(answer), "generated_token_count": len(token_ids), "generated_token_ids_sha256": token_ids_hash(token_ids), "memory_before": memory_before, "memory_after": memory_after, "operators": operator_rows(profiler.key_averages(), top_operators=args.top_operators)}
        if backend is None:
            result["full_kv_bypass_zero_route_a_admission"] = True
        else:
            backend.assert_replay_complete()
            if not backend.comparisons or not all(backend.policy_decode_calls.get(layer, 0) > 0 for layer in layers):
                raise AssertionError(f"{path}: no policy decode coverage in every selected layer")
            result["policy_decode_call_count_by_layer"] = backend.policy_decode_calls
            result["policy_coverage"] = backend.coverage()
        results.append(result)
    summary_path = args.output_dir / "a412_profiler_operator_summary.json"
    summary_path.write_text(json.dumps({"schema_version": PROFILER_SCHEMA, "results": results}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"schema_version": PROFILER_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"], "source_answer_sha256": source["answer_sha256"]}, "operator_summary": summary_path.name, "operator_summary_units": {"device_time_total_us": "generic torch.profiler device time; CUDA in this CUDA-only gate", "device_memory_usage_bytes": "generic torch.profiler device memory accounting; not allocator peak or HBM traffic"}, "source_artifact_sha256": source["source_artifact_sha256"], "observational_guards": {"paired_mask_mode": "replayed_dense_mask", "full_kv_bypass_zero_route_a_admission": True, "route_a_predictor_scored_online": False, "replay_mask_consumption_complete": True, "profiler_is_separate_from_timing_repetitions": True, "profiler_scope": "question_forward_plus_greedy_decode", "context_prefill_profiled": False}, "boundaries": ["torch.profiler alters execution and these operator values must not be compared as latency or throughput measurements.", "This profiles the Python reference after untimed context prefill; it is not a packed-attention kernel profile.", "Allocator counters are PyTorch allocator observations, not HBM traffic, energy, area, frequency, hardware acceleration, or RTL evidence."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    manifest_path = args.output_dir / "a412_profiler_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.2.1 profiler diagnostic completed: {manifest_path}")


if __name__ == "__main__":
    main()
