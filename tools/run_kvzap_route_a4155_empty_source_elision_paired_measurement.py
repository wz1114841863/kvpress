"""A4.1.7.4 paired software measurement for Route-A empty-source elision.

The unelided and elided Route-A paths execute adjacent fresh-cache reset runs
against the identical replay source.  Semantic equivalence is certified by a
completed A4.1.7.3 artifact before timing begins.  This intentionally does
not re-label Python-reference timing as a packed-attention kernel result.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import pipeline

from kvpress.route_a_measurement import (
    A4155_RAW_SCHEMA,
    cuda_memory_snapshot,
    initialize_output_directory,
    raw_record,
    require_cuda_device,
    reset_cuda_peak_memory,
    summarize_paired_reset_records,
    summarize_reported_repetitions,
    time_cuda_region,
    write_raw_repetitions,
)
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a412_whole_decode_gate import answer_hash, read_source, token_ids_hash
from tools.run_kvzap_route_a4147_qwen_external_storage_whole_decode_measurement import EXTERNAL_STORAGE_PATH
from tools.run_kvzap_route_a4148_qwen_external_storage_profiler import make_backend_and_cache
from tools.run_kvzap_route_a4152_certified_execution_mode_whole_decode_measurement import verify_backend
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


A4155_SCHEMA = "kvzap-route-a4155-empty-source-elision-paired-measurement-1.0"
BASELINE_PATH = "same_mask_route_a_external_storage_unelided"
CANDIDATE_PATH = "same_mask_route_a_external_storage_empty_source_elision"
REQUIRED_A4154_GUARDS = frozenset({
    "execution_only_actual_numerical_guard_work_absent",
    "replay_consumption_complete",
    "all_layers_all_kv_heads_external_storage_substituted",
    "persistent_selected_native_cold_absent",
    "required_any_full_multi_tail_packed_coverage",
    "forced_full_model_logits_close",
    "independent_greedy_tokens_equal_baseline",
    "empty_pending_source_skip_observed",
    "source_partial_or_skip_accounting_matches_merge",
    "nonempty_hot_and_packed_attention_observed",
})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.7.4 repeated paired Route-A empty-source-elision Python-software measurement; not an HBM or hardware benchmark.")
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
    parser.add_argument("--empty-source-elision-certification", type=Path, required=True, help="Completed matching A4.1.7.3 manifest.")
    parser.add_argument("--require-cross-workload-source-coverage", action="store_true", help="Require the supplied A4154 certificate to bind current cross-workload source coverage.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def validate_cross_workload_a4154_coverage(certificate: dict[str, Any], *, expected_event_sha256: str) -> dict[str, Any]:
    """Verify the provenance relay from collector through A4151 into A4154."""
    if certificate.get("observational_guards", {}).get("required_cross_workload_source_coverage_verified") is not True:
        raise ValueError("A4154 certificate did not require cross-workload source coverage")
    source = certificate.get("replay_source", {})
    coverage, certificate_coverage = source.get("event_coverage"), source.get("certificate_event_coverage")
    if not isinstance(coverage, dict) or not isinstance(certificate_coverage, dict) or coverage.get("all_layers_exact_all_kv_heads") is not True or certificate_coverage.get("required_by_certificate") is not True or source.get("event_file_sha256") != expected_event_sha256 or coverage.get("event_count") != certificate_coverage.get("event_count"):
        raise ValueError("A4154 cross-workload source coverage does not match its certificate/source")
    return {"all_layers_exact_all_kv_heads": True, "event_count": coverage.get("event_count"), "layer_count": coverage.get("layer_count")}


def validate_a4154_certificate(*, path: Path, args: argparse.Namespace, event_sha256: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"empty-source-elision certificate is missing: {path}")
    certificate = json.loads(path.read_text(encoding="utf-8"))
    if certificate.get("schema_version") != "kvzap-route-a4154-empty-source-elision-semantic-gate-1.0" or certificate.get("status") != "complete":
        raise ValueError("empty-source-elision certificate is not a completed A4.1.7.3 manifest")
    missing = sorted(name for name in REQUIRED_A4154_GUARDS if certificate.get("observational_guards", {}).get(name) is not True)
    if missing:
        raise ValueError(f"empty-source-elision certificate lacks guards: {missing}")
    config = certificate.get("config", {})
    expected = {
        "model_name": args.model_name, "model_revision": args.model_revision,
        "predictor_name": args.predictor_name, "predictor_revision": args.predictor_revision,
        "threshold": args.threshold, "window_size": args.window_size, "page_tokens": args.page_tokens,
        "admission_budget": args.admission_budget, "max_new_tokens": args.max_new_tokens,
        "seed": args.seed, "replay_event_file_sha256": event_sha256,
        "baseline_elide_empty_sources": False, "candidate_elide_empty_sources": True,
    }
    mismatch = {key: {"certificate": config.get(key), "requested": value} for key, value in expected.items() if config.get(key) != value}
    if mismatch:
        raise ValueError(f"empty-source-elision certificate configuration mismatch: {mismatch}")
    diagnostic = certificate.get("diagnostic", {})
    baseline_digest = diagnostic.get("baseline", {}).get("generated_token_ids_sha256")
    candidate_digest = diagnostic.get("elided_independent", {}).get("generated_token_ids_sha256")
    if not isinstance(baseline_digest, str) or baseline_digest != candidate_digest:
        raise ValueError("A4.1.7.3 certificate does not establish a shared stable Route-A token digest")
    cross_workload_coverage = validate_cross_workload_a4154_coverage(certificate, expected_event_sha256=event_sha256) if args.require_cross_workload_source_coverage else None
    return {"manifest": str(path), "sha256": sha256_file(path), "route_a_execution_certificate": certificate.get("route_a_execution_certificate"), "token_ids_sha256": baseline_digest, "cross_workload_source_coverage": cross_workload_coverage}


def _counter_measure(counter: Counter[str]):
    def measure(name, operation):
        counter[name] += 1
        return operation()
    return measure


def _source_counts(counter: Counter[str]) -> dict[str, int]:
    return {name: int(counter[name]) for name in sorted(counter) if name.startswith("decode_route_a_attention_") or name.startswith("decode_route_a_empty_source_skip_") or name.startswith("multi_token_route_a_attention_") or name.startswith("multi_token_route_a_empty_source_skip_") or name.endswith("route_a_online_softmax_merge")}


def run_one(*, pipe, context_ids, question_ids, path: str, elide_empty_sources: bool, args: argparse.Namespace, layers, expected_heads, events, event_sha256: str, repetition: int, pair_id: int, execution_order: int, warmup: bool, expected_token_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
    counter: Counter[str] = Counter()
    backend, cache = make_backend_and_cache(path=EXTERNAL_STORAGE_PATH, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, component_measure=_counter_measure(counter), same_mask_numerical_guard_mode="execution_only", elide_empty_sources=elide_empty_sources)
    seed_everything(args.seed)
    with torch.no_grad(), backend:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        memory_before = reset_cuda_peak_memory(args.device)
        result, timing = time_cuda_region(lambda: pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True), device=args.device)
        memory_after = cuda_memory_snapshot(args.device)
    assert_no_runtime_mask_state(pipe.model)
    if not isinstance(result, tuple) or len(result) != 2 or not result[1]:
        raise AssertionError("A4.1.7.4 path did not return a nonempty answer/token-ID pair")
    answer, token_ids = result
    digest = token_ids_hash(token_ids)
    if digest != expected_token_digest:
        raise AssertionError(f"{path} reset-run token digest differs from A4.1.7.3 certificate")
    guard = verify_backend(path=EXTERNAL_STORAGE_PATH, backend=backend, cache=cache, expected_heads=expected_heads, args=args)
    elision = backend.empty_source_elision_summary()
    record = raw_record(path=path, component="whole_decode_after_untimed_context_prefill", repetition=repetition, execution_order=execution_order, warmup=warmup, timing=timing, memory_before=memory_before, memory_after=memory_after, schema_version=A4155_RAW_SCHEMA)
    record.update({
        "pair_id": pair_id,
        "generated_token_count": len(token_ids),
        "generated_token_ids_sha256": digest,
        "answer_sha256": answer_hash(answer),
        "timed_region": "question_forward_plus_greedy_decode",
        "replay_event_file_sha256": event_sha256,
        "same_mask_numerical_guard_mode": "execution_only",
        "elide_empty_sources": elide_empty_sources,
        "empty_source_skip_counts": {key: sum(int(row[key]) for row in elision["layers"]) for key in ("hot_skip_count", "pending_skip_count", "packed_skip_count")},
    })
    return record, {"path": path, "pair_id": pair_id, "repetition": repetition, "execution_order": execution_order, "warmup": warmup, "generated_token_ids_sha256": digest, "answer_sha256": record["answer_sha256"], "source_component_call_counts": _source_counts(counter), "empty_source_elision": elision, **guard}


def paired_schedule(*, warmups: int, measured: int, seed: int):
    rng = random.Random(seed)
    for warmup, count in ((True, warmups), (False, measured)):
        for repetition in range(count):
            ordered = [(BASELINE_PATH, False), (CANDIDATE_PATH, True)]
            rng.shuffle(ordered)
            yield repetition, warmup, ordered


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512:
        raise ValueError("A4.1.7.4 requires --target-layers all --target-kv-head all --admission-budget 512")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit, args.warmup_repetitions, args.measured_repetitions) <= 0 or args.window_size < 0:
        raise ValueError("invalid A4.1.7.4 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("A4.1.7.4 is bounded to frozen Qwen3-8B and official MLP revisions")
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
        raise ValueError("replay source admission budget differs from A4.1.7.4 configuration")
    certificate = validate_a4154_certificate(path=args.empty_source_elision_certification, args=args, event_sha256=event_sha256)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids, question_ids = tokenized["context_ids"].to(pipe.model.device), tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    config.update({"replay_event_file_sha256": event_sha256, "same_mask_numerical_guard_mode": "execution_only", "timed_region": "question_forward_plus_greedy_decode_after_untimed_context_prefill", "pairing": "adjacent_fresh_reset_runs_randomized_within_pair"})
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a4155_empty_source_elision_paired_measurement_started.json", schema_version=A4155_SCHEMA, boundaries=["A4.1.7.4 is a paired Python-reference software measurement after completed A4.1.7.3 semantic certification.", "It compares unelided Route-A external storage with a semantically certified empty-source-elided Route-A variant; Full-KV and same-mask-dense controls remain distinct prior artifacts, not this pair's paths.", "Timing and PyTorch allocator observations are not HBM traffic, throughput, energy, area, hardware acceleration, or RTL evidence."])
    records, outcomes = [], []
    execution_order = 0
    for pair_id, (repetition, warmup, ordered) in enumerate(paired_schedule(warmups=args.warmup_repetitions, measured=args.measured_repetitions, seed=args.seed)):
        for path, elide in ordered:
            print(f"{('Warmup' if warmup else 'Measured')} pair {pair_id}, repetition {repetition + 1}: {path} (execution_order={execution_order})")
            record, outcome = run_one(pipe=pipe, context_ids=context_ids, question_ids=question_ids, path=path, elide_empty_sources=elide, args=args, layers=layers, expected_heads=expected_heads, events=events, event_sha256=event_sha256, repetition=repetition, pair_id=pair_id, execution_order=execution_order, warmup=warmup, expected_token_digest=certificate["token_ids_sha256"])
            records.append(record); outcomes.append(outcome); execution_order += 1
    raw_path = write_raw_repetitions(args.output_dir, records)
    summary = summarize_reported_repetitions(records)
    summary.update({"raw_path": raw_path.name, "paired_reset_run_summary": summarize_paired_reset_records(records, baseline_path=BASELINE_PATH, candidate_path=CANDIDATE_PATH)})
    manifest = {"schema_version": A4155_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"]}, "empty_source_elision_certificate": certificate, "summary": summary, "outcomes": outcomes, "observational_guards": {"a4154_empty_source_elision_semantics_certified": True, "execution_only_actual_numerical_guard_work_absent": True, "replay_mask_consumption_complete_each_reset_run": True, "all_layers_all_kv_heads_external_storage_substituted_each_reset_run": True, "persistent_selected_native_cold_absent_each_reset_run": True, "required_any_full_multi_tail_packed_coverage_each_reset_run": True, "fresh_reset_run_token_digests_match_a4154_certificate": True, "adjacent_paired_fresh_reset_runs": True, "allocator_peaks_are_run_local_maxima": True, "required_cross_workload_source_coverage_verified": bool(args.require_cross_workload_source_coverage)}, "boundaries": ["This is a fixed-request repeated Python-reference software measurement; its paired timing deltas cannot establish hardware latency, throughput, or acceleration.", "Full-KV bypass and same-mask dense KVzap are distinct baselines retained in cited A4.1.7.1 artifacts, not paths in this Route-A-to-Route-A attribution pair.", "Allocator values are PyTorch allocated/reserved counters, not HBM capacity or traffic; component call counts are software counters, not hardware operations."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    path = args.output_dir / "a4155_empty_source_elision_paired_measurement_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.7.4 empty-source-elision paired measurement completed: {path}")


if __name__ == "__main__":
    main()
