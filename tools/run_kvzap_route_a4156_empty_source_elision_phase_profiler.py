"""A4.1.7.5 profiler attribution for semantically certified empty-source elision.

One unprofiled warm-up and one profiler capture are taken for each Route-A
variant. Profiler ranges are deliberately diagnostic and separate from the
A4.1.7.4 repeated timing distribution.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import torch
import transformers
from torch.profiler import ProfilerActivity, profile
from transformers import pipeline

from kvpress.route_a_measurement import cuda_memory_snapshot, initialize_output_directory, require_cuda_device
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a412_profiler import operator_rows
from tools.run_kvzap_route_a412_whole_decode_gate import answer_hash, read_source, token_ids_hash
from tools.run_kvzap_route_a4147_qwen_external_storage_whole_decode_measurement import EXTERNAL_STORAGE_PATH
from tools.run_kvzap_route_a4148_qwen_external_storage_profiler import make_backend_and_cache, run_decode
from tools.run_kvzap_route_a4149_qwen_external_storage_phase_profiler import PHASE_PREFIX, PhaseRecorder, coalesced_phase_rows
from tools.run_kvzap_route_a4152_certified_execution_mode_whole_decode_measurement import verify_backend
from tools.run_kvzap_route_a4155_empty_source_elision_paired_measurement import BASELINE_PATH, CANDIDATE_PATH
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request


A4156_SCHEMA = "kvzap-route-a4156-empty-source-elision-phase-profiler-1.0"
ARTIFACT_STEM = "a4156_empty_source_elision_phase_profiler"
PHASE_PATHS = ((BASELINE_PATH, False), (CANDIDATE_PATH, True))
REQUIRED_A4155_GUARDS = frozenset({
    "a4154_empty_source_elision_semantics_certified",
    "adjacent_paired_fresh_reset_runs",
    "all_layers_all_kv_heads_external_storage_substituted_each_reset_run",
    "execution_only_actual_numerical_guard_work_absent",
    "fresh_reset_run_token_digests_match_a4154_certificate",
    "persistent_selected_native_cold_absent_each_reset_run",
    "replay_mask_consumption_complete_each_reset_run",
    "required_any_full_multi_tail_packed_coverage_each_reset_run",
})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.7.5 paired unelided/empty-source-elision Route-A phase profiler; diagnostic only, not a timing benchmark.")
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
    parser.add_argument("--warmup-repetitions", type=int, default=1, help="Unprofiled fresh-cache warm-ups per Route-A variant.")
    parser.add_argument("--top-operators", type=int, default=30)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--replay-source-dir", type=Path, required=True)
    parser.add_argument("--paired-measurement-manifest", type=Path, required=True, help="Completed matching A4.1.7.4 manifest.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def source_phase_accounting(*, calls: Mapping[str, int], expected_attention_evaluations: int, elide_empty_sources: bool) -> dict[str, Any]:
    """Validate tagged source partial/skip calls against every merge evaluation."""
    if expected_attention_evaluations <= 0:
        raise ValueError("expected attention evaluations must be positive")
    result: dict[str, Any] = {}
    for source in ("hot", "pending", "packed"):
        partial = int(calls.get(f"decode_route_a_attention_{source}", 0) + calls.get(f"multi_token_route_a_attention_{source}", 0))
        skip = int(calls.get(f"decode_route_a_empty_source_skip_{source}", 0) + calls.get(f"multi_token_route_a_empty_source_skip_{source}", 0))
        if partial + skip != expected_attention_evaluations:
            raise AssertionError(f"{source} phase accounting differs from expected attention evaluations: partial={partial}, skip={skip}, expected={expected_attention_evaluations}")
        if not elide_empty_sources and skip != 0:
            raise AssertionError("unelided Route-A emitted an empty-source skip phase")
        result[source] = {"partial_attention_calls": partial, "empty_source_skip_calls": skip, "total_source_decisions": partial + skip}
    merge = int(calls.get("decode_route_a_online_softmax_merge", 0) + calls.get("multi_token_route_a_online_softmax_merge", 0))
    if merge != expected_attention_evaluations:
        raise AssertionError(f"merge phase calls differ from expected attention evaluations: merge={merge}, expected={expected_attention_evaluations}")
    if elide_empty_sources and result["pending"]["empty_source_skip_calls"] <= 0:
        raise AssertionError("empty-source-elision profiler did not observe a pending skip")
    return {"expected_attention_evaluations": expected_attention_evaluations, "merge_calls": merge, "by_source": result}


def validate_a4155_manifest(*, path: Path, args: argparse.Namespace, event_sha256: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"A4.1.7.4 paired-measurement manifest is missing: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a4155-empty-source-elision-paired-measurement-1.0" or manifest.get("status") != "complete":
        raise ValueError("paired-measurement manifest is not a completed A4.1.7.4 artifact")
    missing = sorted(name for name in REQUIRED_A4155_GUARDS if manifest.get("observational_guards", {}).get(name) is not True)
    if missing:
        raise ValueError(f"paired-measurement manifest lacks guards: {missing}")
    config = manifest.get("config", {})
    expected = {"model_name": args.model_name, "model_revision": args.model_revision, "predictor_name": args.predictor_name, "predictor_revision": args.predictor_revision, "threshold": args.threshold, "window_size": args.window_size, "page_tokens": args.page_tokens, "admission_budget": args.admission_budget, "max_new_tokens": args.max_new_tokens, "seed": args.seed, "replay_event_file_sha256": event_sha256}
    mismatch = {key: {"measurement": config.get(key), "requested": value} for key, value in expected.items() if config.get(key) != value}
    if mismatch:
        raise ValueError(f"paired-measurement configuration mismatch: {mismatch}")
    certificate = manifest.get("empty_source_elision_certificate", {})
    digest = certificate.get("token_ids_sha256")
    if not isinstance(digest, str) or not digest:
        raise ValueError("paired-measurement manifest lacks the A4.1.7.3 token digest")
    return {"manifest": str(path), "sha256": sha256_file(path), "a4154_certificate": certificate, "token_ids_sha256": digest}


def verify_profiled_backend(*, backend, cache, expected_heads, language_model, recorder: PhaseRecorder, args: argparse.Namespace, elide_empty_sources: bool) -> dict[str, Any]:
    guard = verify_backend(path=EXTERNAL_STORAGE_PATH, backend=backend, cache=cache, expected_heads=expected_heads, args=args)
    query_heads = int(language_model.config.num_attention_heads)
    decode_calls = sum(int(item.policy_decode_calls) for item in backend.backends.values())
    multi_token_tokens = sum(int(getattr(item, "policy_multi_token_tokens", 0)) for item in backend.backends.values())
    accounting = source_phase_accounting(calls=recorder.calls, expected_attention_evaluations=(decode_calls + multi_token_tokens) * query_heads, elide_empty_sources=elide_empty_sources)
    return {**guard, "source_phase_accounting": accounting}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512:
        raise ValueError("A4.1.7.5 requires --target-layers all --target-kv-head all --admission-budget 512")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit, args.warmup_repetitions, args.top_operators) <= 0 or args.window_size < 0:
        raise ValueError("invalid A4.1.7.5 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("A4.1.7.5 is bounded to frozen Qwen3-8B and official MLP revisions")
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
    args.require_any_pending, args.require_any_full_multi_tail_packed = False, True
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=layers)
    if source["config"].get("admission_budget") != args.admission_budget:
        raise ValueError("replay source admission budget differs from A4.1.7.5 configuration")
    paired_measurement = validate_a4155_manifest(path=args.paired_measurement_manifest, args=args, event_sha256=event_sha256)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids, question_ids = tokenized["context_ids"].to(pipe.model.device), tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    config.update({"replay_event_file_sha256": event_sha256, "same_mask_numerical_guard_mode": "execution_only", "phase_prefix": PHASE_PREFIX, "profiler_scope": "question_forward_plus_greedy_decode_after_untimed_context_prefill", "profiler_paths": [path for path, _elide in PHASE_PATHS]})
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name=f"{ARTIFACT_STEM}_started.json", schema_version=A4156_SCHEMA, boundaries=["A4.1.7.5 captures one profiler diagnostic per A4.1.7.4 Route-A variant, separate from all timing repetitions.", "The candidate elides only empty source partials; replay, external ownership/native-cold exclusion, page coverage, token digest, and execution-only guards remain enforced.", "Nested profiler ranges and profiler memory values are diagnostic software observations, not latency, HBM traffic, throughput, energy, hardware acceleration, or RTL evidence."])
    results: list[dict[str, Any]] = []
    for path, elide in PHASE_PATHS:
        for warmup in range(args.warmup_repetitions):
            print(f"Unprofiled warm-up {warmup + 1}/{args.warmup_repetitions}: {path}")
            recorder = PhaseRecorder()
            backend, cache = make_backend_and_cache(path=EXTERNAL_STORAGE_PATH, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, component_measure=recorder.measure, same_mask_numerical_guard_mode="execution_only", elide_empty_sources=elide)
            _answer, token_ids, _before, _after = run_decode(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, cache=cache, args=args)
            assert_no_runtime_mask_state(pipe.model)
            if token_ids_hash(token_ids) != paired_measurement["token_ids_sha256"]:
                raise AssertionError(f"{path} warm-up token digest differs from A4.1.7.4 certificate")
            verify_profiled_backend(backend=backend, cache=cache, expected_heads=expected_heads, language_model=language_model, recorder=recorder, args=args, elide_empty_sources=elide)
        print(f"Phase-profiled diagnostic: {path}")
        recorder = PhaseRecorder()
        backend, cache = make_backend_and_cache(path=EXTERNAL_STORAGE_PATH, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, component_measure=recorder.measure, same_mask_numerical_guard_mode="execution_only", elide_empty_sources=elide)
        profiler = profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA], record_shapes=True, profile_memory=True, with_stack=False)
        answer, token_ids, memory_before, memory_after = run_decode(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, cache=cache, args=args, profiler=profiler)
        torch.cuda.synchronize(require_cuda_device(args.device))
        assert_no_runtime_mask_state(pipe.model)
        if token_ids_hash(token_ids) != paired_measurement["token_ids_sha256"]:
            raise AssertionError(f"{path} profiler token digest differs from A4.1.7.4 certificate")
        guard = verify_profiled_backend(backend=backend, cache=cache, expected_heads=expected_heads, language_model=language_model, recorder=recorder, args=args, elide_empty_sources=elide)
        results.append({"path": path, "elide_empty_sources": elide, "answer_sha256": answer_hash(answer), "generated_token_count": len(token_ids), "generated_token_ids_sha256": token_ids_hash(token_ids), "memory_before": memory_before, "memory_after": memory_after, "phase_operators": coalesced_phase_rows(profiler.key_averages()), "phase_operator_row_mode": "coalesced_cpu_cuda_views", "generic_top_operators": operator_rows(profiler.key_averages(), top_operators=args.top_operators), **guard})
    summary_path = args.output_dir / f"{ARTIFACT_STEM}_summary.json"
    summary_path.write_text(json.dumps({"schema_version": A4156_SCHEMA, "phase_prefix": PHASE_PREFIX, "phase_operator_row_mode": "coalesced_cpu_cuda_views", "results": results}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"schema_version": A4156_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"]}, "paired_measurement": paired_measurement, "phase_summary": summary_path.name, "phase_summary_units": {"device_time_total_us": "generic coalesced torch.profiler device time; nested/inclusive CUDA diagnostic only", "device_memory_usage_bytes": "generic torch.profiler device memory accounting; not allocator peak or HBM traffic"}, "observational_guards": {"a4155_paired_measurement_verified": True, "execution_only_actual_numerical_guard_work_absent": True, "replay_mask_consumption_complete": True, "all_layers_all_kv_heads_external_storage_substituted": True, "persistent_selected_native_cold_absent": True, "required_any_full_multi_tail_packed_coverage": True, "profiler_token_digests_match_a4154_certificate": True, "source_partial_or_skip_accounting_matches_merge": True, "unelided_has_no_empty_source_skips": True, "elided_pending_skip_observed": True, "phase_rows_coalesced": True, "profiler_is_separate_from_timing_repetitions": True, "context_prefill_profiled": False}, "boundaries": ["Profiler labels are nested and possibly inclusive; their ranges must not be summed or interpreted as latency/throughput measurements.", "This compares two execution-only Python-reference Route-A variants after untimed context prefill, not a packed-attention kernel.", "Profiler time/memory values are not HBM traffic, energy, area, frequency, hardware acceleration, or RTL evidence."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    path = args.output_dir / f"{ARTIFACT_STEM}_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.7.5 empty-source-elision paired phase profiler completed: {path}")


if __name__ == "__main__":
    main()
