"""A4.1.7.2 execution-only paired phase-profiler diagnostic.

Profiler ranges are deliberately separate from the A4.1.7.1 timing
distribution.  The only change from the guarded phase profiler is execution
mode: per-query same-mask dense/FP32/dtype/ULP reference work is elided after
the corresponding semantic certificates have passed.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from torch.profiler import ProfilerActivity, profile
from transformers import pipeline

from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a412_profiler import operator_rows
from tools.run_kvzap_route_a412_whole_decode_gate import answer_hash, read_source, token_ids_hash
from tools.run_kvzap_route_a4147_qwen_external_storage_whole_decode_measurement import EXTERNAL_STORAGE_PATH
from tools.run_kvzap_route_a4148_qwen_external_storage_profiler import make_backend_and_cache, run_decode
from tools.run_kvzap_route_a4149_qwen_external_storage_phase_profiler import PHASE_PREFIX, PhaseRecorder, coalesced_phase_rows, phase_coverage
from tools.run_kvzap_route_a4152_certified_execution_mode_whole_decode_measurement import certify_dense_execution_only, validate_route_certificate, verify_backend
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request


A4153_SCHEMA = "kvzap-route-a4153-execution-mode-paired-phase-profiler-1.0"
ARTIFACT_STEM = "a4153_execution_mode_paired_phase_profiler"
PHASE_PATHS = ("same_mask_dense_replay", EXTERNAL_STORAGE_PATH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.7.2 certified execution-only paired phase profiler for Qwen Route-A. Diagnostic only; not a timing benchmark.")
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
    parser.add_argument("--warmup-repetitions", type=int, default=1, help="Unprofiled fresh-cache warm-ups per paired path.")
    parser.add_argument("--top-operators", type=int, default=30)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--replay-source-dir", type=Path, required=True)
    parser.add_argument("--route-a-execution-certification", type=Path, required=True, help="Completed matching A4.1.7.0 manifest.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512:
        raise ValueError("A4.1.7.2 requires --target-layers all --target-kv-head all --admission-budget 512")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit, args.warmup_repetitions, args.top_operators) <= 0 or args.window_size < 0:
        raise ValueError("invalid A4.1.7.2 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("A4.1.7.2 is bounded to frozen Qwen3-8B and official MLP revisions")
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
        raise ValueError("replay source admission budget differs from A4.1.7.2 configuration")
    route_certificate = validate_route_certificate(path=args.route_a_execution_certification, args=args, event_sha256=event_sha256)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokenized["context_ids"].to(pipe.model.device)
    question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    config.update({"replay_event_file_sha256": event_sha256, "same_mask_numerical_guard_mode": "execution_only", "phase_prefix": PHASE_PREFIX, "profiler_scope": "question_forward_plus_greedy_decode_after_untimed_context_prefill"})
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name=f"{ARTIFACT_STEM}_started.json", schema_version=A4153_SCHEMA, boundaries=["A4.1.7.2 is one execution-only paired profiler capture per path after separate dense and Route-A semantic certificates; it is not a timing repetition.", "Replay, external ownership/native-cold exclusion and page-state guards remain enabled. Only per-query numerical-reference work is elided.", "Nested profiler time/memory values are diagnostic software observations, not HBM traffic, latency, throughput, energy, hardware acceleration, or RTL evidence."])
    dense_certificate = certify_dense_execution_only(pipe=pipe, context_ids=context_ids, question_ids=question_ids, layers=layers, expected_heads=expected_heads, events=events, args=args)
    expected_digests = {"same_mask_dense_replay": dense_certificate["execution_only_token_ids_sha256"], EXTERNAL_STORAGE_PATH: route_certificate["execution_only_token_ids_sha256"]}
    results: list[dict[str, Any]] = []
    for path in PHASE_PATHS:
        for warmup in range(args.warmup_repetitions):
            print(f"Unprofiled execution-only warm-up {warmup + 1}/{args.warmup_repetitions}: {path}")
            recorder = PhaseRecorder()
            backend, cache = make_backend_and_cache(path=path, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, component_measure=recorder.measure, same_mask_numerical_guard_mode="execution_only")
            answer, token_ids, _before, _after = run_decode(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, cache=cache, args=args)
            assert_no_runtime_mask_state(pipe.model)
            if token_ids_hash(token_ids) != expected_digests[path]:
                raise AssertionError(f"{path} execution-only warm-up token digest differs from its certificate")
            verify_backend(path=path, backend=backend, cache=cache, expected_heads=expected_heads, args=args)
        print(f"Execution-only paired phase-profiled diagnostic: {path}")
        recorder = PhaseRecorder()
        backend, cache = make_backend_and_cache(path=path, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, component_measure=recorder.measure, same_mask_numerical_guard_mode="execution_only")
        profiler = profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA], record_shapes=True, profile_memory=True, with_stack=False)
        answer, token_ids, memory_before, memory_after = run_decode(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, cache=cache, args=args, profiler=profiler)
        torch.cuda.synchronize(require_cuda_device(args.device))
        assert_no_runtime_mask_state(pipe.model)
        if token_ids_hash(token_ids) != expected_digests[path]:
            raise AssertionError(f"{path} execution-only profiler token digest differs from its certificate")
        guard = verify_backend(path=path, backend=backend, cache=cache, expected_heads=expected_heads, args=args)
        coverage = phase_coverage(backend=backend, language_model=language_model, recorder=recorder, path=path)
        results.append({"path": path, "answer_sha256": answer_hash(answer), "generated_token_count": len(token_ids), "generated_token_ids_sha256": token_ids_hash(token_ids), "memory_before": memory_before, "memory_after": memory_after, "phase_operators": coalesced_phase_rows(profiler.key_averages()), "phase_operator_row_mode": "coalesced_cpu_cuda_views", "phase_label_coverage": coverage, "generic_top_operators": operator_rows(profiler.key_averages(), top_operators=args.top_operators), **guard})
    summary_path = args.output_dir / f"{ARTIFACT_STEM}_summary.json"
    summary_path.write_text(json.dumps({"schema_version": A4153_SCHEMA, "phase_prefix": PHASE_PREFIX, "phase_operator_row_mode": "coalesced_cpu_cuda_views", "results": results}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"schema_version": A4153_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"], "source_answer_sha256": source["answer_sha256"]}, "route_a_execution_certificate": route_certificate, "same_mask_dense_execution_certificate": dense_certificate, "phase_summary": summary_path.name, "phase_summary_units": {"device_time_total_us": "generic coalesced torch.profiler device time; nested/inclusive CUDA diagnostic only", "device_memory_usage_bytes": "generic torch.profiler device memory accounting; not allocator peak or HBM traffic"}, "source_artifact_sha256": source["source_artifact_sha256"], "observational_guards": {"route_a_execution_only_certification_verified": True, "same_mask_dense_guarded_vs_execution_only_certified": True, "execution_only_per_query_same_mask_numerical_guards_absent": True, "replay_mask_consumption_complete": True, "all_layers_all_kv_heads_external_storage_substituted": True, "persistent_selected_native_cold_absent": True, "required_any_full_multi_tail_packed_coverage": True, "execution_only_profiler_token_digests_match_certificates": True, "phase_rows_coalesced": True, "phase_label_coverage_enforced": True, "profiler_is_separate_from_timing_repetitions": True, "context_prefill_profiled": False}, "boundaries": ["Profiler labels are nested, possibly inclusive reference-phase ranges; their values must not be summed or interpreted as latency/throughput measurements.", "This compares execution-only Python-reference dense and Route-A external-storage paths after untimed context prefill, not a packed-attention kernel.", "Profiler time/memory values are not HBM traffic, energy, area, frequency, hardware acceleration, or RTL evidence."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    manifest_path = args.output_dir / f"{ARTIFACT_STEM}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.7.2 execution-mode paired phase profiler completed: {manifest_path}")


if __name__ == "__main__":
    main()
