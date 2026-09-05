"""A4.1.4 repeated all-layer Qwen external-storage whole-decode measurement."""

from __future__ import annotations

import argparse
import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import DynamicCache, pipeline

from kvpress.route_a_measurement import A4147_RAW_SCHEMA, cuda_memory_snapshot, initialize_output_directory, raw_record, require_cuda_device, reset_cuda_peak_memory, time_cuda_region, write_raw_repetitions
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAQwenExternalColdStorageAttentionBackendSet
from kvpress.route_a_qwen_cache import RouteAQwenMultiLayerExternalColdCache
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a412_whole_decode_gate import WHOLE_DECODE_COMPONENT, answer_hash, read_source, schedule_runs, token_ids_hash, whole_decode_summary
from tools.run_kvzap_route_a4142_qwen_multilayer_allhead_native_storage_gate import require_multilayer_replacement
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


A4147_SCHEMA = "kvzap-route-a4147-qwen-external-storage-whole-decode-measurement-1.0"
EXTERNAL_STORAGE_PATH = "same_mask_route_a_external_storage_replay"
MEASUREMENT_PATHS = ("full_kv_bypass", "same_mask_dense_replay", EXTERNAL_STORAGE_PATH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.4 repeated Qwen external-storage whole-decode measurement. It reports software timing and PyTorch allocator observations, not HBM traffic or hardware performance.")
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
    parser.add_argument("--warmup-repetitions", type=int, default=3)
    parser.add_argument("--measured-repetitions", type=int, default=10)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--replay-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def compact_route_state(*, coverage: dict[str, Any], page_coverage: dict[str, Any], ulp: dict[str, Any]) -> dict[str, Any]:
    """Persist bounded state/guard summaries, never repeated tensor-like coverage."""
    heads = [head for layer in coverage["layers"] for head in layer["heads"]]
    rows = ulp["layers"]
    return {
        "selected_layer_count": len(coverage["layers"]),
        "selected_kv_head_count": len(heads),
        "pending_head_count": sum(bool(head["ever_pending"]) for head in heads),
        "page_witness_count": len(page_coverage["witnesses"]),
        "max_packed_page_count": max((int(head["max_packed_page_count"]) for head in heads), default=0),
        "max_packed_full_page_count": max((int(head["max_packed_full_page_count"]) for head in heads), default=0),
        "max_packed_tail_tokens": max((int(head["max_packed_tail_tokens"]) for head in heads), default=0),
        "execution_dtype_ulp_breach_count": sum(int(row["breach_count"]) for row in rows),
        "execution_dtype_ulp_max": max((float(row["max_observed_ulps"] or 0.0) for row in rows), default=0.0),
    }


def run_one_path(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, path: str, args: argparse.Namespace, layers: tuple[int, ...], expected_heads: dict[int, tuple[int, ...]], events, event_sha256: str, repetition: int, execution_order: int, warmup: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    backend = None
    cache = DynamicCache()
    if path == "same_mask_dense_replay":
        backend = DenseSameMaskAttentionBackendSet(pipe.model, None, layers=layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode="record_only", execution_dtype_close_mode="quantization_aware_enforce", ulp_breach_sample_limit=args.ulp_breach_sample_limit, replay_mask_events=events)
    elif path == EXTERNAL_STORAGE_PATH:
        backend = RouteAQwenExternalColdStorageAttentionBackendSet(pipe.model, None, layers=layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode="record_only", execution_dtype_close_mode="quantization_aware_enforce", ulp_breach_sample_limit=args.ulp_breach_sample_limit, replay_mask_events=events)
        cache = RouteAQwenMultiLayerExternalColdCache(selected_kv_heads_by_layer=expected_heads)
    elif path != "full_kv_bypass":
        raise ValueError(f"unknown A4.1.4 path: {path}")

    seed_everything(args.seed)
    context = backend if backend is not None else contextlib.nullcontext()
    with torch.no_grad(), context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        memory_before = reset_cuda_peak_memory(args.device)
        result, timing = time_cuda_region(lambda: pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True), device=args.device)
        memory_after = cuda_memory_snapshot(args.device)
    assert_no_runtime_mask_state(pipe.model)
    if not isinstance(result, tuple) or len(result) != 2 or not isinstance(result[0], str) or not isinstance(result[1], list) or not result[1]:
        raise AssertionError("A4.1.4 whole-decode path did not return a nonempty answer/token-ID pair")
    answer, token_ids = result
    record = raw_record(path=path, component=WHOLE_DECODE_COMPONENT, repetition=repetition, execution_order=execution_order, warmup=warmup, timing=timing, memory_before=memory_before, memory_after=memory_after, schema_version=A4147_RAW_SCHEMA)
    record.update({"generated_token_count": len(token_ids), "generated_token_ids_sha256": token_ids_hash(token_ids), "answer_sha256": answer_hash(answer), "timed_region": "question_forward_plus_greedy_decode", "replay_event_file_sha256": event_sha256})
    outcome: dict[str, Any] = {"path": path, "repetition": repetition, "execution_order": execution_order, "warmup": warmup, "answer_sha256": record["answer_sha256"], "generated_token_count": len(token_ids), "generated_token_ids_sha256": record["generated_token_ids_sha256"]}
    if backend is None:
        outcome["full_kv_bypass_zero_route_a_admission"] = True
    else:
        backend.assert_replay_complete()
        if any(count <= 0 for count in backend.policy_decode_calls.values()):
            raise AssertionError(f"{path} did not execute policy attention in every selected layer")
        outcome["policy_decode_call_count_by_layer"] = backend.policy_decode_calls
        if path == EXTERNAL_STORAGE_PATH:
            coverage, storage, page_coverage = require_multilayer_replacement(backend=backend, cache=cache, expected_heads=expected_heads, args=args)
            if any(row["persistent_unselected_kv_heads"] or row["persistent_selected_native_cold_tensor_tokens"] for row in storage["layers"]):
                raise AssertionError("external-storage path retained prohibited persistent target-layer K/V")
            outcome["external_storage_guard"] = compact_route_state(coverage=coverage, page_coverage=page_coverage, ulp=backend.execution_dtype_ulp_breach_summary())
        else:
            outcome["execution_dtype_ulp_breach_count"] = sum(int(row["breach_count"]) for row in backend.execution_dtype_ulp_breach_summary()["layers"])
    return record, outcome


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512:
        raise ValueError("A4.1.4 requires --target-layers all --target-kv-head all --admission-budget 512")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit, args.warmup_repetitions, args.measured_repetitions) <= 0 or args.window_size < 0:
        raise ValueError("invalid A4.1.4 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("A4.1.4 is bounded to frozen Qwen3-8B and official MLP revisions")
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
        raise ValueError("replay source admission budget differs from A4.1.4 external-storage configuration")
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokenized["context_ids"].to(pipe.model.device)
    question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    config.update({"replay_event_file_sha256": event_sha256, "execution_dtype_ulp_mode": "record_only", "execution_dtype_close_mode": "quantization_aware_enforce", "timed_region": "question_forward_plus_greedy_decode_after_untimed_context_prefill"})
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a4147_external_storage_whole_decode_started.json", schema_version=A4147_SCHEMA, boundaries=["A4.1.4 times only question forward plus greedy decode after a fresh, untimed context prefill per reset run.", "The Route-A path uses the A4.1.3 external-storage Qwen cache; Full-KV and same-mask dense are separate control paths.", "Allocator fields are PyTorch allocator observations in bytes, not HBM traffic. This Python reference is not a packed-attention kernel or hardware benchmark."])
    records: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for execution_order, (path, repetition, warmup) in enumerate(schedule_runs(warmups=args.warmup_repetitions, measured=args.measured_repetitions, seed=args.seed, paths=MEASUREMENT_PATHS)):
        print(f"{('Warmup' if warmup else 'Measured')} {repetition + 1}: {path} (execution_order={execution_order})")
        record, outcome = run_one_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, path=path, args=args, layers=layers, expected_heads=expected_heads, events=events, event_sha256=event_sha256, repetition=repetition, execution_order=execution_order, warmup=warmup)
        records.append(record)
        outcomes.append(outcome)
    raw_path = write_raw_repetitions(args.output_dir, records)
    summary = whole_decode_summary(records, outcomes)
    summary["raw_path"] = raw_path.name
    manifest = {"schema_version": A4147_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"], "source_answer_sha256": source["answer_sha256"]}, "summary": summary, "source_artifact_sha256": source["source_artifact_sha256"], "observational_guards": {"paired_mask_mode": "replayed_dense_mask", "full_kv_bypass_zero_route_a_admission": True, "route_a_predictor_scored_online": False, "replay_mask_consumption_complete": True, "all_layers_all_kv_heads_external_storage_substituted": True, "persistent_selected_native_cold_absent": True, "required_any_full_multi_tail_packed_coverage": True, "fp32_same_mask_guard": {"rtol": args.rtol, "atol": args.atol}, "execution_dtype_ulp_mode": "record_only", "execution_dtype_close_mode": "quantization_aware_enforce", "execution_dtype_close_enforced": True, "one_timed_region_per_reset_run": True, "component_timer_installed": False}, "boundaries": ["This is an A4.1.4 Python-reference software measurement after untimed context prefill; it is not a packed-attention kernel benchmark.", "Full-KV bypass, same-mask dense replay, and same-mask Route-A external-storage replay are distinct paths. Answer equality is recorded, not required by the measurement protocol.", "Allocator counters are PyTorch allocator observations, not HBM traffic. This does not establish throughput, energy, area, frequency, hardware acceleration, or RTL evidence."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    path = args.output_dir / "a4147_external_storage_whole_decode_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.4 external-storage whole-decode measurement completed: {path}")


if __name__ == "__main__":
    main()
