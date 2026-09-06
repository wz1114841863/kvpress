"""A4.1.6 phase-attributed profiler for the guarded external-cache reference.

The optional labels do not alter KVzap replay, state ownership, attention, or
numerical guards.  They only make the A4.1.5 generic profiler counters
attributable to reference phases. This remains a diagnostic, not timing data.
"""

from __future__ import annotations

import argparse
import contextlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from torch.profiler import ProfilerActivity, profile, record_function
from transformers import pipeline

from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a412_profiler import operator_rows
from tools.run_kvzap_route_a412_whole_decode_gate import answer_hash, read_source, token_ids_hash
from tools.run_kvzap_route_a4147_qwen_external_storage_whole_decode_measurement import EXTERNAL_STORAGE_PATH
from tools.run_kvzap_route_a4148_qwen_external_storage_profiler import make_backend_and_cache, route_guard_summary, run_decode
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request


A4149_SCHEMA = "kvzap-route-a4149-qwen-external-storage-phase-profiler-1.0"
PHASE_PREFIX = "route_a_phase::"
PHASE_PATHS = ("same_mask_dense_replay", EXTERNAL_STORAGE_PATH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.6 phase-attributed profiler for all-layer Qwen replayed-mask references. Diagnostic only; not a timing benchmark.")
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
    parser.add_argument("--warmup-repetitions", type=int, default=1)
    parser.add_argument("--top-operators", type=int, default=30)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--replay-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def phase_measure(name: str, operation):
    """Profile-only wrapper; ``operation`` remains the sole semantic action."""
    with record_function(f"{PHASE_PREFIX}{name}"):
        return operation()


class PhaseRecorder:
    """Count labels at their semantic call site while emitting profiler ranges."""

    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()

    def measure(self, name: str, operation):
        self.calls[name] += 1
        return phase_measure(name, operation)


def phase_rows(events: Any) -> list[dict[str, Any]]:
    tagged = [event for event in events if str(getattr(event, "key", "")).startswith(PHASE_PREFIX)]
    return operator_rows(tagged, top_operators=max(1, len(tagged)))


def coalesced_phase_rows(events: Any) -> list[dict[str, Any]]:
    """Coalesce profiler CPU/CUDA split rows without double-counting calls.

    PyTorch may emit one CPU aggregate and one CUDA aggregate for one range.
    They are alternate accounting views, not two semantic invocations.  Keep
    the maximum count and each metric's maximal available accounting field.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in phase_rows(events):
        groups.setdefault(str(row["operator"]), []).append(row)
    numeric = ("count", "self_cpu_time_total_us", "cpu_time_total_us", "self_device_time_total_us", "device_time_total_us", "self_cpu_memory_usage_bytes", "cpu_memory_usage_bytes", "self_device_memory_usage_bytes", "device_memory_usage_bytes")
    result = []
    for operator, rows in groups.items():
        merged = {"operator": operator}
        for field in numeric:
            merged[field] = max(float(row[field]) for row in rows)
        merged["count"] = int(merged["count"])
        result.append(merged)
    return sorted(result, key=lambda row: (row["device_time_total_us"], row["cpu_time_total_us"], row["operator"]), reverse=True)


def phase_coverage(*, backend, language_model, recorder: PhaseRecorder, path: str) -> dict[str, Any]:
    """Require tagged Route-A attention calls to cover every policy execution."""
    query_heads = int(language_model.config.num_attention_heads)
    decode_calls = sum(int(item.policy_decode_calls) for item in backend.backends.values())
    multi_token_count = sum(int(getattr(item, "policy_multi_token_tokens", 0)) for item in backend.backends.values())
    expected = (decode_calls + multi_token_count) * query_heads
    if path == "same_mask_dense_replay":
        observed = int(recorder.calls["decode_dense_same_mask_attention"] + recorder.calls["multi_token_dense_same_mask_attention"])
    elif path == EXTERNAL_STORAGE_PATH:
        names = ("hot", "pending", "packed")
        observed_by_source = {source: int(recorder.calls[f"decode_route_a_attention_{source}"] + recorder.calls[f"multi_token_route_a_attention_{source}"]) for source in names}
        if any(value != expected for value in observed_by_source.values()):
            raise AssertionError(f"external Route-A phase labels do not cover policy attention: expected={expected}, observed={observed_by_source}")
        observed = observed_by_source["hot"]
    else:
        raise ValueError(f"unknown phase-coverage path: {path}")
    if observed != expected:
        raise AssertionError(f"{path} phase labels do not cover policy attention: expected={expected}, observed={observed}")
    return {"query_head_count": query_heads, "policy_decode_calls": decode_calls, "policy_multi_token_tokens": multi_token_count, "expected_attention_evaluations": expected, "tagged_attention_evaluations": observed, "label_call_counts": dict(sorted(recorder.calls.items()))}


def main(*, schema_version: str = A4149_SCHEMA, phase: str = "A4.1.6", artifact_stem: str = "a4149_external_storage_phase_profiler", coalesce_rows: bool = False, require_phase_coverage: bool = False) -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512:
        raise ValueError(f"{phase} requires --target-layers all --target-kv-head all --admission-budget 512")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit, args.warmup_repetitions, args.top_operators) <= 0 or args.window_size < 0:
        raise ValueError(f"invalid {phase} dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError(f"{phase} is bounded to frozen Qwen3-8B and official MLP revisions")
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
        raise ValueError("replay source admission budget differs from A4.1.6 configuration")
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokenized["context_ids"].to(pipe.model.device)
    question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    config.update({"replay_event_file_sha256": event_sha256, "execution_dtype_ulp_mode": "record_only", "execution_dtype_close_mode": "quantization_aware_enforce", "phase_prefix": PHASE_PREFIX, "profiler_scope": "question_forward_plus_greedy_decode_after_untimed_context_prefill"})
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name=f"{artifact_stem}_started.json", schema_version=schema_version, boundaries=[f"{phase} adds profiler labels only; it does not alter mask replay, state ownership, attention, or numerical guards.", "One diagnostic capture per reference path is separate from timing repetitions and cannot establish latency or throughput.", "Profiler time/memory values are software diagnostic observations, not HBM traffic, energy, area, hardware acceleration, or RTL evidence."])
    results: list[dict[str, Any]] = []
    for path in PHASE_PATHS:
        for warmup in range(args.warmup_repetitions):
            print(f"Unprofiled warm-up {warmup + 1}/{args.warmup_repetitions}: {path}")
            recorder = PhaseRecorder()
            backend, cache = make_backend_and_cache(path=path, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, component_measure=recorder.measure)
            run_decode(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, cache=cache, args=args)
            assert_no_runtime_mask_state(pipe.model)
            backend.assert_replay_complete()
            if path == EXTERNAL_STORAGE_PATH:
                route_guard_summary(backend=backend, cache=cache, expected_heads=expected_heads, args=args)
        print(f"Phase-profiled diagnostic: {path}")
        recorder = PhaseRecorder()
        backend, cache = make_backend_and_cache(path=path, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, component_measure=recorder.measure)
        profiler = profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA], record_shapes=True, profile_memory=True, with_stack=False)
        answer, token_ids, memory_before, memory_after = run_decode(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, cache=cache, args=args, profiler=profiler)
        torch.cuda.synchronize(require_cuda_device(args.device))
        assert_no_runtime_mask_state(pipe.model)
        backend.assert_replay_complete()
        rows = coalesced_phase_rows(profiler.key_averages()) if coalesce_rows else phase_rows(profiler.key_averages())
        result: dict[str, Any] = {"path": path, "answer_sha256": answer_hash(answer), "generated_token_count": len(token_ids), "generated_token_ids_sha256": token_ids_hash(token_ids), "memory_before": memory_before, "memory_after": memory_after, "phase_operators": rows, "phase_operator_row_mode": "coalesced_cpu_cuda_views" if coalesce_rows else "raw_profiler_rows", "generic_top_operators": operator_rows(profiler.key_averages(), top_operators=args.top_operators)}
        if any(count <= 0 for count in backend.policy_decode_calls.values()):
            raise AssertionError(f"{path} did not execute policy attention in every selected layer")
        result["policy_decode_call_count_by_layer"] = backend.policy_decode_calls
        if require_phase_coverage:
            result["phase_label_coverage"] = phase_coverage(backend=backend, language_model=language_model, recorder=recorder, path=path)
        if path == EXTERNAL_STORAGE_PATH:
            result["external_storage_guard"] = route_guard_summary(backend=backend, cache=cache, expected_heads=expected_heads, args=args)
        else:
            result["execution_dtype_ulp_breach_count"] = sum(int(row["breach_count"]) for row in backend.execution_dtype_ulp_breach_summary()["layers"])
        results.append(result)
    summary_path = args.output_dir / f"{artifact_stem}_summary.json"
    summary_path.write_text(json.dumps({"schema_version": schema_version, "phase_prefix": PHASE_PREFIX, "phase_operator_row_mode": "coalesced_cpu_cuda_views" if coalesce_rows else "raw_profiler_rows", "results": results}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"schema_version": schema_version, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"], "source_answer_sha256": source["answer_sha256"]}, "phase_summary": summary_path.name, "phase_summary_units": {"device_time_total_us": "generic torch.profiler device time; CUDA in this CUDA-only gate", "device_memory_usage_bytes": "generic torch.profiler device memory accounting; not allocator peak or HBM traffic"}, "source_artifact_sha256": source["source_artifact_sha256"], "observational_guards": {"paired_mask_mode": "replayed_dense_mask", "route_a_predictor_scored_online": False, "replay_mask_consumption_complete": True, "all_layers_all_kv_heads_external_storage_substituted": True, "persistent_selected_native_cold_absent": True, "required_any_full_multi_tail_packed_coverage": True, "fp32_same_mask_guard": {"rtol": args.rtol, "atol": args.atol}, "execution_dtype_ulp_mode": "record_only", "execution_dtype_close_mode": "quantization_aware_enforce", "execution_dtype_close_enforced": True, "phase_labels_only": True, "phase_rows_coalesced": coalesce_rows, "phase_label_coverage_enforced": require_phase_coverage, "profiler_is_separate_from_timing_repetitions": True, "context_prefill_profiled": False}, "boundaries": ["Profiler labels are nested reference-phase ranges and may be inclusive; their times must not be summed or interpreted as timing data.", "This is a Python-reference diagnostic after untimed context prefill, not a packed-attention kernel profile.", "Profiler time/memory values are not HBM traffic, energy, area, frequency, hardware acceleration, or RTL evidence."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    manifest_path = args.output_dir / f"{artifact_stem}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{phase} external-storage phase profiler completed: {manifest_path}")


if __name__ == "__main__":
    main()
