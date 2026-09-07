"""A4.1.7.1 repeated execution-only software measurement after certification.

This runner deliberately keeps numerical certification outside the timed
repetitions.  It first certifies same-mask dense guard-elision on this exact
request/replay and verifies the completed A4.1.7.0 Route-A certificate.  The
timed runs retain replay, ownership, poison and page-state guards, but omit
only per-query same-mask numerical-reference work.
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

from kvpress.route_a_measurement import A4152_RAW_SCHEMA, cuda_memory_snapshot, initialize_output_directory, raw_record, require_cuda_device, reset_cuda_peak_memory, time_cuda_region, write_raw_repetitions
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a4123_first_decode_logits_diagnostic import paired_logit_relation
from tools.run_kvzap_route_a4128_allhead_continuation_diagnostic import token_ids_digest
from tools.run_kvzap_route_a412_whole_decode_gate import WHOLE_DECODE_COMPONENT, answer_hash, read_source, schedule_runs, token_ids_hash, whole_decode_summary
from tools.run_kvzap_route_a4142_qwen_multilayer_allhead_native_storage_gate import require_multilayer_replacement
from tools.run_kvzap_route_a4147_qwen_external_storage_whole_decode_measurement import EXTERNAL_STORAGE_PATH, compact_route_state
from tools.run_kvzap_route_a4148_qwen_external_storage_profiler import make_backend_and_cache
from tools.run_kvzap_route_a4151_guard_elided_execution_semantic_gate import A4151_SCHEMA, continuation
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


A4152_SCHEMA = "kvzap-route-a4152-certified-execution-mode-whole-decode-measurement-1.0"
MEASUREMENT_PATHS = ("full_kv_bypass", "same_mask_dense_replay", EXTERNAL_STORAGE_PATH)
ROUTE_CERTIFICATE_GUARDS = frozenset({
    "guarded_reference_fp32_same_mask_enforced",
    "execution_only_per_query_same_mask_numerical_guards_absent",
    "replay_consumption_complete",
    "all_layers_all_kv_heads_external_storage_substituted",
    "persistent_selected_native_cold_absent",
    "required_any_full_multi_tail_packed_coverage",
    "forced_full_model_logits_close",
    "independent_greedy_tokens_equal_guarded",
})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.7.1 certified execution-only repeated Qwen decode measurement; PyTorch software timing only, not an HBM or hardware benchmark.")
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
    parser.add_argument("--route-a-execution-certification", type=Path, required=True, help="Completed A4.1.7.0 manifest for this exact Route-A replay/configuration.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def _require_execution_only(backend) -> None:
    if any(item.same_mask_numerical_guard_enforced for item in backend.backends.values()):
        raise AssertionError("execution-only backend retained a per-query same-mask numerical guard")


def verify_backend(*, path: str, backend, cache, expected_heads: dict[int, tuple[int, ...]], args: argparse.Namespace) -> dict[str, Any]:
    backend.assert_replay_complete()
    if any(count <= 0 for count in backend.policy_decode_calls.values()):
        raise AssertionError(f"{path} did not execute policy attention in every selected layer")
    _require_execution_only(backend)
    result: dict[str, Any] = {
        "same_mask_numerical_guard_mode": "execution_only",
        "policy_decode_call_count_by_layer": backend.policy_decode_calls,
    }
    if path == EXTERNAL_STORAGE_PATH:
        coverage, storage, page_coverage = require_multilayer_replacement(backend=backend, cache=cache, expected_heads=expected_heads, args=args)
        if any(row["persistent_unselected_kv_heads"] or row["persistent_selected_native_cold_tensor_tokens"] for row in storage["layers"]):
            raise AssertionError("external-storage execution-only path retained prohibited persistent target-layer K/V")
        result["external_storage_guard"] = compact_route_state(coverage=coverage, page_coverage=page_coverage, ulp=backend.execution_dtype_ulp_breach_summary())
    return result


def validate_route_certificate(*, path: Path, args: argparse.Namespace, event_sha256: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"A4.1.7.0 Route-A execution certificate is missing: {path}")
    certificate = json.loads(path.read_text(encoding="utf-8"))
    if certificate.get("schema_version") != A4151_SCHEMA or certificate.get("status") != "complete":
        raise ValueError("Route-A execution certificate is not a completed A4.1.7.0 manifest")
    guards = certificate.get("observational_guards", {})
    missing = sorted(name for name in ROUTE_CERTIFICATE_GUARDS if guards.get(name) is not True)
    if missing:
        raise ValueError(f"Route-A execution certificate lacks required guards: {missing}")
    config = certificate.get("config", {})
    expected = {
        "model_name": args.model_name, "model_revision": args.model_revision,
        "predictor_name": args.predictor_name, "predictor_revision": args.predictor_revision,
        "threshold": args.threshold, "window_size": args.window_size, "page_tokens": args.page_tokens,
        "admission_budget": args.admission_budget, "max_new_tokens": args.max_new_tokens,
        "seed": args.seed, "replay_event_file_sha256": event_sha256,
    }
    mismatch = {key: {"certificate": config.get(key), "requested": value} for key, value in expected.items() if config.get(key) != value}
    if mismatch:
        raise ValueError(f"Route-A execution certificate configuration mismatch: {mismatch}")
    digest = certificate.get("diagnostic", {}).get("execution_only_independent", {}).get("generated_token_ids_sha256")
    if not isinstance(digest, str) or not digest:
        raise ValueError("Route-A execution certificate lacks independent execution-only token digest")
    return {"manifest": str(path), "sha256": sha256_file(path), "execution_only_token_ids_sha256": digest}


def certify_dense_execution_only(*, pipe, context_ids, question_ids, layers, expected_heads, events, args: argparse.Namespace) -> dict[str, Any]:
    """Fresh, untimed same-mask dense guard-on/guard-elided certification."""
    runs: dict[str, dict[str, Any]] = {}
    for label, mode, forced in (("guarded_reference", "enforce", None), ("execution_only_forced", "execution_only", None), ("execution_only_independent", "execution_only", None)):
        print(f"Untimed dense certification: {label}...")
        backend, cache = make_backend_and_cache(path="same_mask_dense_replay", pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, same_mask_numerical_guard_mode=mode)
        forced_ids = runs["guarded_reference"]["generated_token_ids"] if label == "execution_only_forced" else forced
        run = continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, cache=cache, args=args, forced_token_ids=forced_ids)
        assert_no_runtime_mask_state(pipe.model)
        backend.assert_replay_complete()
        if any(count <= 0 for count in backend.policy_decode_calls.values()):
            raise AssertionError("dense certification did not execute policy attention in every selected layer")
        if mode == "execution_only":
            _require_execution_only(backend)
        runs[label] = run
    relations = [paired_logit_relation(a, b) for a, b in zip(runs["guarded_reference"]["logits"], runs["execution_only_forced"]["logits"], strict=True)]
    for guarded, execution in zip(runs["guarded_reference"]["logits"], runs["execution_only_forced"]["logits"], strict=True):
        torch.testing.assert_close(execution, guarded, rtol=args.rtol, atol=args.atol)
    if runs["execution_only_independent"]["generated_token_ids"] != runs["guarded_reference"]["generated_token_ids"]:
        raise AssertionError("dense execution-only independent greedy tokens differ from guarded same-mask dense reference")
    return {
        "guarded_reference_token_ids_sha256": token_ids_digest(runs["guarded_reference"]["generated_token_ids"]),
        "execution_only_token_ids_sha256": token_ids_digest(runs["execution_only_independent"]["generated_token_ids"]),
        "guarded_vs_execution_only_forced_logit_steps": relations,
        "guards": {"guarded_reference_fp32_same_mask_enforced": True, "execution_only_per_query_same_mask_numerical_guards_absent": True, "forced_full_model_logits_close": True, "independent_greedy_tokens_equal_guarded": True},
    }


def run_one_path(*, pipe, context_ids, question_ids, path: str, args: argparse.Namespace, layers, expected_heads, events, event_sha256: str, repetition: int, execution_order: int, warmup: bool, expected_token_digest: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    backend, cache = make_backend_and_cache(path=path, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, same_mask_numerical_guard_mode="execution_only")
    seed_everything(args.seed)
    context = backend if backend is not None else contextlib.nullcontext()
    with torch.no_grad(), context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        memory_before = reset_cuda_peak_memory(args.device)
        result, timing = time_cuda_region(lambda: pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True), device=args.device)
        memory_after = cuda_memory_snapshot(args.device)
    assert_no_runtime_mask_state(pipe.model)
    if not isinstance(result, tuple) or len(result) != 2 or not isinstance(result[0], str) or not isinstance(result[1], list) or not result[1]:
        raise AssertionError("A4.1.7.1 whole-decode path did not return a nonempty answer/token-ID pair")
    answer, token_ids = result
    digest = token_ids_hash(token_ids)
    if expected_token_digest is not None and digest != expected_token_digest:
        raise AssertionError(f"{path} execution-only timed run token digest differs from its certified reference")
    record = raw_record(path=path, component=WHOLE_DECODE_COMPONENT, repetition=repetition, execution_order=execution_order, warmup=warmup, timing=timing, memory_before=memory_before, memory_after=memory_after, schema_version=A4152_RAW_SCHEMA)
    record.update({"generated_token_count": len(token_ids), "generated_token_ids_sha256": digest, "answer_sha256": answer_hash(answer), "timed_region": "question_forward_plus_greedy_decode", "replay_event_file_sha256": event_sha256, "same_mask_numerical_guard_mode": "execution_only"})
    outcome: dict[str, Any] = {"path": path, "repetition": repetition, "execution_order": execution_order, "warmup": warmup, "answer_sha256": record["answer_sha256"], "generated_token_count": len(token_ids), "generated_token_ids_sha256": digest}
    if backend is None:
        outcome["full_kv_bypass_zero_route_a_admission"] = True
    else:
        outcome.update(verify_backend(path=path, backend=backend, cache=cache, expected_heads=expected_heads, args=args))
    return record, outcome


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512:
        raise ValueError("A4.1.7.1 requires --target-layers all --target-kv-head all --admission-budget 512")
    if min(args.context_repetitions, args.page_tokens, args.max_new_tokens, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit, args.warmup_repetitions, args.measured_repetitions) <= 0 or args.window_size < 0:
        raise ValueError("invalid A4.1.7.1 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("A4.1.7.1 is bounded to frozen Qwen3-8B and official MLP revisions")
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
    args.require_any_pending = False
    args.require_any_full_multi_tail_packed = True
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=layers)
    if source["config"].get("admission_budget") != args.admission_budget:
        raise ValueError("replay source admission budget differs from A4.1.7.1 configuration")
    route_certificate = validate_route_certificate(path=args.route_a_execution_certification, args=args, event_sha256=event_sha256)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokenized["context_ids"].to(pipe.model.device)
    question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    config.update({"replay_event_file_sha256": event_sha256, "same_mask_numerical_guard_mode": "execution_only", "timed_region": "question_forward_plus_greedy_decode_after_untimed_context_prefill"})
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a4152_certified_execution_mode_started.json", schema_version=A4152_SCHEMA, boundaries=["A4.1.7.1 records repeated execution-only Python software timings after separate same-mask dense and A4.1.7.0 Route-A semantic certification.", "Each reset run preserves replay, policy/state, external ownership/native-cold poison and page coverage guards; only per-query numerical-reference work is elided.", "Allocator fields are PyTorch allocator observations, not HBM traffic. This is not a packed-attention kernel, throughput, energy, hardware, or RTL result."])
    dense_certificate = certify_dense_execution_only(pipe=pipe, context_ids=context_ids, question_ids=question_ids, layers=layers, expected_heads=expected_heads, events=events, args=args)
    expected_digests = {"same_mask_dense_replay": dense_certificate["execution_only_token_ids_sha256"], EXTERNAL_STORAGE_PATH: route_certificate["execution_only_token_ids_sha256"], "full_kv_bypass": None}
    records: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    observed_path_digests: dict[str, str] = {}
    schedule = schedule_runs(warmups=args.warmup_repetitions, measured=args.measured_repetitions, seed=args.seed, paths=MEASUREMENT_PATHS)
    for execution_order, (path, repetition, warmup) in enumerate(schedule):
        print(f"{('Warmup' if warmup else 'Measured')} {repetition + 1}: {path} (execution_order={execution_order})")
        record, outcome = run_one_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, path=path, args=args, layers=layers, expected_heads=expected_heads, events=events, event_sha256=event_sha256, repetition=repetition, execution_order=execution_order, warmup=warmup, expected_token_digest=expected_digests[path])
        previous = observed_path_digests.setdefault(path, record["generated_token_ids_sha256"])
        if previous != record["generated_token_ids_sha256"]:
            raise AssertionError(f"{path} token digest drifted across fresh reset runs")
        records.append(record)
        outcomes.append(outcome)
    raw_path = write_raw_repetitions(args.output_dir, records)
    summary = whole_decode_summary(records, outcomes)
    summary["raw_path"] = raw_path.name
    manifest = {"schema_version": A4152_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"], "source_answer_sha256": source["answer_sha256"]}, "route_a_execution_certificate": route_certificate, "same_mask_dense_execution_certificate": dense_certificate, "summary": summary, "source_artifact_sha256": source["source_artifact_sha256"], "observational_guards": {"full_kv_bypass_zero_route_a_admission": True, "route_a_execution_only_certification_verified": True, "same_mask_dense_guarded_vs_execution_only_certified": True, "execution_only_per_query_same_mask_numerical_guards_absent": True, "replay_mask_consumption_complete": True, "all_layers_all_kv_heads_external_storage_substituted": True, "persistent_selected_native_cold_absent": True, "required_any_full_multi_tail_packed_coverage": True, "one_timed_region_per_reset_run": True, "component_timer_installed": False, "execution_only_timed_token_digests_match_certificates": True, "fresh_reset_run_token_digests_stable": True}, "boundaries": ["This is an A4.1.7.1 execution-only Python-reference software measurement after untimed context prefill, not a packed-attention kernel benchmark.", "Full-KV bypass, same-mask dense KVzap execution-only, and same-mask Route-A external-storage execution-only are distinct paths. Neither is required to equal Full-KV.", "The guard-elided timing distribution is separate from guarded A4.1.4 and profiler artifacts. Allocator counters are PyTorch observations, not HBM traffic; no throughput, energy, area, frequency, hardware acceleration, or RTL conclusion follows."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    path = args.output_dir / "a4152_certified_execution_mode_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.7.1 certified execution-mode whole-decode measurement completed: {path}")


if __name__ == "__main__":
    main()
