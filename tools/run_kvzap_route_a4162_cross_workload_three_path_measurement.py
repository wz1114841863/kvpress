"""A4.1.7.11 summarization three-path execution-only software measurement.

The timer sees only question-forward plus greedy decode after a freshly built,
untimed context cache.  Full-KV bypass is deliberately separate from the two
replayed-mask paths.  This remains a Python-reference measurement, not a
packed kernel or hardware benchmark.
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
from transformers import pipeline

from kvpress.route_a_measurement import cuda_memory_snapshot, initialize_output_directory, raw_record, require_cuda_device, reset_cuda_peak_memory, time_cuda_region, write_raw_repetitions
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a412_whole_decode_gate import WHOLE_DECODE_COMPONENT, answer_hash, read_source, schedule_runs, token_ids_hash, whole_decode_summary
from tools.run_kvzap_route_a4147_qwen_external_storage_whole_decode_measurement import EXTERNAL_STORAGE_PATH
from tools.run_kvzap_route_a4148_qwen_external_storage_profiler import make_backend_and_cache
from tools.run_kvzap_route_a4151_guard_elided_execution_semantic_gate import A4151_SCHEMA
from tools.run_kvzap_route_a4152_certified_execution_mode_whole_decode_measurement import certify_dense_execution_only, validate_route_certificate, verify_backend
from tools.run_kvzap_route_a4155_empty_source_elision_paired_measurement import validate_a4154_certificate
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


A4162_SCHEMA = "kvzap-route-a4162-cross-workload-three-path-measurement-1.0"
A4162_RAW_SCHEMA = "kvzap-route-a4162-cross-workload-three-path-raw-1.0"
ROUTE_ELIDED_PATH = "same_mask_route_a_external_storage_empty_source_elision"
PATHS = ("full_kv_bypass", "same_mask_dense_replay", ROUTE_ELIDED_PATH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.7.11 repeated Qwen three-path software measurement; not an HBM or hardware benchmark.")
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="summarization")
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
    parser.add_argument("--max-new-tokens", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    parser.add_argument("--warmup-repetitions", type=int, default=2)
    parser.add_argument("--measured-repetitions", type=int, default=10)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--replay-source-dir", type=Path, required=True)
    parser.add_argument("--route-a-execution-certification", type=Path, required=True, help="Completed matching A4151 manifest.")
    parser.add_argument("--empty-source-elision-certification", type=Path, required=True, help="Completed matching A4154 manifest.")
    parser.add_argument("--require-cross-workload-source-coverage", action="store_true", help="Require A4154/A4151 provenance to bind the current source.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def run_one_path(*, pipe, context_ids, question_ids, path: str, args: argparse.Namespace, layers, expected_heads, events, event_sha256: str, repetition: int, execution_order: int, warmup: bool, expected_token_digest: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    backend_path = EXTERNAL_STORAGE_PATH if path == ROUTE_ELIDED_PATH else path
    backend, cache = make_backend_and_cache(path=backend_path, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, same_mask_numerical_guard_mode="execution_only", elide_empty_sources=path == ROUTE_ELIDED_PATH)
    seed_everything(args.seed)
    with torch.no_grad(), (backend if backend is not None else contextlib.nullcontext()):
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        memory_before = reset_cuda_peak_memory(args.device)
        result, timing = time_cuda_region(lambda: pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True), device=args.device)
        memory_after = cuda_memory_snapshot(args.device)
    assert_no_runtime_mask_state(pipe.model)
    if not isinstance(result, tuple) or len(result) != 2 or not result[1]:
        raise AssertionError("A4.1.7.11 path did not return a nonempty answer/token-ID pair")
    answer, token_ids = result
    digest = token_ids_hash(token_ids)
    if expected_token_digest is not None and digest != expected_token_digest:
        raise AssertionError(f"{path} timed token digest differs from its certified reference")
    record = raw_record(path=path, component=WHOLE_DECODE_COMPONENT, repetition=repetition, execution_order=execution_order, warmup=warmup, timing=timing, memory_before=memory_before, memory_after=memory_after, schema_version=A4162_RAW_SCHEMA)
    record.update({"generated_token_count": len(token_ids), "generated_token_ids_sha256": digest, "answer_sha256": answer_hash(answer), "timed_region": "question_forward_plus_greedy_decode", "replay_event_file_sha256": event_sha256, "same_mask_numerical_guard_mode": "execution_only", "empty_source_elision": path == ROUTE_ELIDED_PATH})
    outcome: dict[str, Any] = {"path": path, "repetition": repetition, "execution_order": execution_order, "warmup": warmup, "answer_sha256": record["answer_sha256"], "generated_token_count": len(token_ids), "generated_token_ids_sha256": digest}
    if backend is None:
        outcome["full_kv_bypass_zero_route_a_admission"] = True
    else:
        outcome.update(verify_backend(path=backend_path, backend=backend, cache=cache, expected_heads=expected_heads, args=args))
        if path == ROUTE_ELIDED_PATH:
            outcome["empty_source_elision"] = backend.empty_source_elision_summary()
    return record, outcome


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512:
        raise ValueError("A4.1.7.11 requires --target-layers all --target-kv-head all --admission-budget 512")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit, args.warmup_repetitions, args.measured_repetitions) <= 0 or args.window_size < 0:
        raise ValueError("invalid A4.1.7.11 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("A4.1.7.11 is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    lm = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    layers = tuple(range(len(lm.layers)))
    expected_heads = {layer: tuple(range(int(lm.layers[layer].self_attn.config.num_key_value_heads))) for layer in layers}
    args.resolved_target_layers = list(layers)
    args.resolved_target_kv_heads_by_layer = {str(layer): list(heads) for layer, heads in expected_heads.items()}
    args.require_any_pending, args.require_any_full_multi_tail_packed = False, True
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=layers)
    if source["config"].get("admission_budget") != args.admission_budget:
        raise ValueError("replay source admission budget differs from A4.1.7.11 configuration")
    route_certificate = validate_route_certificate(path=args.route_a_execution_certification, args=args, event_sha256=event_sha256)
    elision_certificate = validate_a4154_certificate(path=args.empty_source_elision_certification, args=args, event_sha256=event_sha256)
    if args.require_cross_workload_source_coverage and elision_certificate["cross_workload_source_coverage"] is None:
        raise AssertionError("required cross-workload source coverage was not retained")
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids, question_ids = tokenized["context_ids"].to(pipe.model.device), tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    config.update({"replay_event_file_sha256": event_sha256, "same_mask_numerical_guard_mode": "execution_only", "timed_region": "question_forward_plus_greedy_decode_after_untimed_context_prefill", "schedule": "fresh_reset_runs_randomized_within_repetition"})
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a4162_cross_workload_three_path_started.json", schema_version=A4162_SCHEMA, boundaries=["A4.1.7.11 is a repeated fixed-request Python-reference software measurement after independent A4151/A4154 semantic certification.", "Full-KV bypass, same-mask dense replay, and empty-source-elided external Route-A are separate paths; Full-KV token equality is recorded, not required.", "Timing and PyTorch allocator observations are not HBM traffic, throughput, energy, hardware acceleration, or RTL evidence."])
    dense_certificate = certify_dense_execution_only(pipe=pipe, context_ids=context_ids, question_ids=question_ids, layers=layers, expected_heads=expected_heads, events=events, args=args)
    expected = {"full_kv_bypass": None, "same_mask_dense_replay": dense_certificate["execution_only_token_ids_sha256"], ROUTE_ELIDED_PATH: elision_certificate["token_ids_sha256"]}
    records: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    observed: dict[str, str] = {}
    for execution_order, (path, repetition, warmup) in enumerate(schedule_runs(warmups=args.warmup_repetitions, measured=args.measured_repetitions, seed=args.seed, paths=PATHS)):
        print(f"{('Warmup' if warmup else 'Measured')} {repetition + 1}: {path} (execution_order={execution_order})")
        record, outcome = run_one_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, path=path, args=args, layers=layers, expected_heads=expected_heads, events=events, event_sha256=event_sha256, repetition=repetition, execution_order=execution_order, warmup=warmup, expected_token_digest=expected[path])
        previous = observed.setdefault(path, record["generated_token_ids_sha256"])
        if previous != record["generated_token_ids_sha256"]:
            raise AssertionError(f"{path} token digest drifted across fresh reset runs")
        records.append(record); outcomes.append(outcome)
    raw_path = write_raw_repetitions(args.output_dir, records)
    summary = whole_decode_summary(records, outcomes)
    summary["raw_path"] = raw_path.name
    reported_digests = {path: observed.get(path) for path in PATHS}
    manifest = {"schema_version": A4162_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"]}, "route_a_execution_certificate": route_certificate, "empty_source_elision_certificate": elision_certificate, "same_mask_dense_execution_certificate": dense_certificate, "summary": summary, "reported_token_digests": reported_digests, "same_mask_dense_route_a_token_digest_equal": reported_digests["same_mask_dense_replay"] == reported_digests[ROUTE_ELIDED_PATH], "observational_guards": {"full_kv_bypass_zero_route_a_admission_each_reset_run": True, "route_a_execution_only_certification_verified": True, "a4154_empty_source_elision_semantics_certified": True, "required_cross_workload_source_coverage_verified": bool(args.require_cross_workload_source_coverage), "same_mask_dense_guarded_vs_execution_only_certified": True, "execution_only_per_query_same_mask_numerical_guards_absent": True, "replay_mask_consumption_complete_each_reset_run": True, "all_layers_all_kv_heads_external_storage_substituted_each_route_a_reset_run": True, "persistent_selected_native_cold_absent_each_route_a_reset_run": True, "required_any_full_multi_tail_packed_coverage_each_route_a_reset_run": True, "execution_only_timed_token_digests_match_certificates": True, "fresh_reset_run_token_digests_stable": True, "allocator_peaks_are_run_local_maxima": True}, "boundaries": ["This is a fixed-request repeated Python-reference software measurement, not a packed-attention kernel benchmark.", "Full-KV bypass is distinct from the same-mask dense/Route-A pair; Full-KV equality is not required. Dense/Route-A digest equality is recorded, not inferred from timing.", "Timing and allocator observations are not HBM traffic, throughput, energy, area, frequency, hardware acceleration, or RTL evidence."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    path = args.output_dir / "a4162_cross_workload_three_path_measurement_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.7.11 cross-workload three-path measurement completed: {path}")


if __name__ == "__main__":
    main()
