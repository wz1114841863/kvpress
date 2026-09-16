#!/usr/bin/env python3
"""Conditioned Llama Route-A prefill-micro-event gate for A4.3.6.

This is deliberately a fixed-continuation functional reference.  It reuses
the completed M5.1 Llama contract rather than treating a Qwen natural decode
trajectory as portable.  ``admission_budget`` is a logical post-append action
count and never a controller rate or hardware choice.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import pipeline

from kvpress.route_a_attention import RouteALifecycleTransitionRecorder
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAPolicyAttentionBackendSet
from tools.export_kvzap_predictor_trace import assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_llama31_m1_semantic_gate import (
    EXPECTED_STRUCTURE,
    assert_all_layer_head_coverage,
    assert_numerical_guard_work,
    make_predictor,
    read_completed_m0,
    validate_runtime_structure,
)
from tools.run_kvzap_llama31_m2_lifecycle_gate import read_completed_m1
from tools.run_kvzap_llama31_m51_fixed_horizon_workload_descriptor import (
    M51_SCHEMA,
    expected_policy_decode_calls,
    fixed_continuation,
    token_ids_digest,
)
from tools.run_kvzap_trace import PRESETS, build_builtin_request
from tools.validate_kvzap_llama31_m0_provenance import (
    DEFAULT_MODEL_REPO,
    DEFAULT_MODEL_REVISION,
    OFFICIAL_PREDICTOR_REPO,
)


SCHEMA = "kvzap-route-a436-llama31-microevent-gate-1.0"
QUANTA = {1, 8, 32}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.3.6 conditioned Llama chunk-64 micro-event functional gate; no timing, FIFO, or hardware claim."
    )
    parser.add_argument("--preset", choices=PRESETS, required=True)
    parser.add_argument("--m0-manifest", type=Path, required=True)
    parser.add_argument("--m1-manifest", type=Path, required=True)
    parser.add_argument("--m51-report", type=Path, required=True)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_REPO)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--predictor-repo-id-override", required=True)
    parser.add_argument("--threshold", type=float, default=-7.0)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--page-tokens", type=int, default=64, help="Functional reference input, not a hardware choice.")
    parser.add_argument("--admission-budget", type=int, required=True, help="Must be one of 1, 8, or 32; a logical action count, not a hardware rate.")
    parser.add_argument("--prefill-maturity-chunk-tokens", type=int, default=64, help="Must be 64 for the bounded micro-event comparison.")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--fixed-new-tokens", type=int, default=8, help="Must preserve the M5.1 fixed non-EOS continuation.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--execution-dtype-ulp-mode", choices=("enforce", "record_only"), default="record_only")
    parser.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    parser.add_argument("--require-single-visible-cuda-device", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def cuda_environment(*, require_single_visible_device: bool) -> dict[str, Any]:
    available = bool(torch.cuda.is_available())
    count = int(torch.cuda.device_count()) if available else 0
    result = {
        "cuda_available": available,
        "visible_cuda_device_count": count,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "visible_device_names": [torch.cuda.get_device_name(index) for index in range(count)],
    }
    if require_single_visible_device and count != 1:
        raise RuntimeError(f"A4.3.6 requires exactly one visible CUDA device; observed={count}")
    return result


def read_m51(path: Path, *, m0_sha256: str, m1_sha256: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"M5.1 report is absent: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("schema_version") != M51_SCHEMA or report.get("status") != "complete":
        raise ValueError("A4.3.6 requires a completed M5.1 fixed-horizon report")
    config, provenance, guards, continuation = (
        report.get("config"), report.get("provenance"), report.get("observational_guards"), report.get("continuation_contract")
    )
    if not all(isinstance(value, dict) for value in (config, provenance, guards, continuation)):
        raise ValueError("M5.1 report lacks configuration/provenance/guard sections")
    expected = {
        "model_name": DEFAULT_MODEL_REPO,
        "model_revision": DEFAULT_MODEL_REVISION,
        "predictor_repo_id_override": OFFICIAL_PREDICTOR_REPO,
        "threshold": -7.0,
        "window_size": 128,
        "page_tokens": 64,
        "context_repetitions": 12,
        "fixed_new_tokens": 8,
        "execution_dtype_ulp_mode": "record_only",
    }
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError("M5.1 report differs from the bounded A4.3.6 Llama contract")
    if provenance.get("m0_manifest_sha256") != m0_sha256 or provenance.get("m1_manifest_sha256") != m1_sha256:
        raise ValueError("M5.1 report does not bind the supplied M0/M1 provenance")
    required = (
        "m0_m1_m4_m41_hash_bound",
        "m41_non_strict_summarization_context_retained",
        "all_32_layers_all_8_kv_heads_covered_each_workload",
        "online_dense_mask_replayed_exactly_once_each_workload",
        "attention_same_mask_numerical_guard_work_executed_each_workload",
        "dense_token_trajectory_forced_in_route_a_each_workload",
        "logical_events_have_no_timestamps",
    )
    if not all(guards.get(key) is True for key in required):
        raise ValueError("M5.1 required functional guard is absent or false")
    if continuation.get("mode") != "fixed_non_eos_continuation" or continuation.get("fixed_new_tokens") != 8:
        raise ValueError("M5.1 fixed-continuation contract is not preserved")
    return report


def write_transitions(path: Path, recorder: RouteALifecycleTransitionRecorder) -> str:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for event in recorder.events:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return sha256_file(path)


def validate_backend(backend: RouteAPolicyAttentionBackendSet | DenseSameMaskAttentionBackendSet, *, layers: int, heads: int, label: str) -> dict[str, Any]:
    coverage = backend.coverage()
    assert_all_layer_head_coverage(coverage, expected_layers=layers, expected_kv_heads=heads, label=label)
    assert_numerical_guard_work(backend.same_mask_numerical_guard_work_summary(), layers, label=label)
    if set(backend.policy_decode_calls.values()) != {expected_policy_decode_calls(8)}:
        raise AssertionError(f"{label}: policy decode horizon differs from the fixed M5.1 contract")
    return coverage


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    fixed = (
        args.model_name, args.model_revision, args.predictor_repo_id_override, args.threshold,
        args.window_size, args.page_tokens, args.context_repetitions, args.fixed_new_tokens,
        args.max_executed_dtype_ulps, args.execution_dtype_ulp_mode, args.ulp_breach_sample_limit,
        args.prefill_maturity_chunk_tokens,
    )
    expected = (
        DEFAULT_MODEL_REPO, DEFAULT_MODEL_REVISION, OFFICIAL_PREDICTOR_REPO, -7.0,
        128, 64, 12, 8, 16.0, "record_only", 32, 64,
    )
    if fixed != expected or args.admission_budget not in QUANTA:
        raise ValueError("A4.3.6 is fixed to the reviewed Llama/M5.1 contract and Q={1,8,32}")
    if min(args.rtol, args.atol, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit) <= 0:
        raise ValueError("invalid numerical guard dimensions")
    cuda_env = cuda_environment(require_single_visible_device=args.require_single_visible_cuda_device)
    m0_sha256 = sha256_file(args.m0_manifest)
    read_completed_m0(args.m0_manifest)
    read_completed_m1(args.m1_manifest, m0_sha256=m0_sha256)
    m1_sha256 = sha256_file(args.m1_manifest)
    m51 = read_m51(args.m51_report, m0_sha256=m0_sha256, m1_sha256=m1_sha256)
    m51_sha256 = sha256_file(args.m51_report)
    revision = str(m51["provenance"]["predictor_revision"])
    args.output_dir.mkdir(parents=True, exist_ok=False)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key not in {"output_dir", "m0_manifest", "m1_manifest", "m51_report"}} | {"predictor_revision": revision, "predictor_model_type": "linear", "target_layers": "all", "target_kv_heads": "all"}
    started = {
        "schema_version": SCHEMA, "status": "started", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "provenance": {"m0_manifest_sha256": m0_sha256, "m1_manifest_sha256": m1_sha256, "m51_report_sha256": m51_sha256},
        "boundaries": ["Started-record only: A4.3.6 is a fixed-continuation functional micro-event gate, not timing or hardware evidence."]
    }
    (args.output_dir / "a436_llama31_microevent_started.json").write_text(json.dumps(started, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    print(f"Loading A4.3.6 Llama base model: {args.model_name}", flush=True)
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise AssertionError("loaded base model revision differs from M0/M1")
    layers, heads = validate_runtime_structure(pipe.model)
    if (layers, heads) != (EXPECTED_STRUCTURE["layer_count"], EXPECTED_STRUCTURE["kv_head_count"]):
        raise AssertionError("loaded model dimensions differ from fixed Llama structure")
    request = build_builtin_request(args.preset, args.context_repetitions)
    tokens = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids, question_ids = tokens["context_ids"].to(pipe.model.device), tokens["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size:
        raise ValueError("request does not exceed protected hot window")
    print("Pass 1/4: fixed-horizon Full-KV bypass...", flush=True)
    full = fixed_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args)
    assert_no_runtime_mask_state(pipe.model)
    selected_layers = tuple(range(layers))
    predictor = make_predictor(predictor_revision=revision, override=args.predictor_repo_id_override)
    dense_backend = DenseSameMaskAttentionBackendSet(pipe.model, predictor, layers=selected_layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode=args.execution_dtype_ulp_mode, ulp_breach_sample_limit=args.ulp_breach_sample_limit)
    print("Pass 2/4: fixed-horizon online same-mask dense source...", flush=True)
    dense = fixed_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, backend=dense_backend)
    assert_no_runtime_mask_state(pipe.model)
    dense_coverage = validate_backend(dense_backend, layers=layers, heads=heads, label="A4.3.6 dense")
    replay_events = dense_backend.mask_events()
    route_backend = RouteAPolicyAttentionBackendSet(pipe.model, None, layers=selected_layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode=args.execution_dtype_ulp_mode, ulp_breach_sample_limit=args.ulp_breach_sample_limit, replay_mask_events=replay_events)
    print("Pass 3/4: trace-off Route-A exact-mask replay...", flush=True)
    route = fixed_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, backend=route_backend, forced_token_ids=dense["generated_token_ids"])
    assert_no_runtime_mask_state(pipe.model)
    route_backend.assert_replay_complete()
    route_coverage = validate_backend(route_backend, layers=layers, heads=heads, label="A4.3.6 trace-off Route-A")
    recorder = RouteALifecycleTransitionRecorder()
    micro_backend = RouteAPolicyAttentionBackendSet(pipe.model, None, layers=selected_layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode=args.execution_dtype_ulp_mode, ulp_breach_sample_limit=args.ulp_breach_sample_limit, replay_mask_events=replay_events, lifecycle_transition_recorder=recorder, prefill_maturity_chunk_tokens=args.prefill_maturity_chunk_tokens)
    print("Pass 4/4: trace-on chunk-64 Route-A exact-mask micro-event replay...", flush=True)
    micro = fixed_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, backend=micro_backend, forced_token_ids=dense["generated_token_ids"])
    assert_no_runtime_mask_state(pipe.model)
    micro_backend.assert_replay_complete()
    micro_coverage = validate_backend(micro_backend, layers=layers, heads=heads, label="A4.3.6 micro-event Route-A")
    if dense_backend.mask_events() != route_backend.mask_events() or route_backend.mask_events() != micro_backend.mask_events():
        raise AssertionError("A4.3.6 replay changed original-mask events")
    if route["generated_token_ids"] != dense["generated_token_ids"] or micro["generated_token_ids"] != dense["generated_token_ids"]:
        raise AssertionError("A4.3.6 Route-A path changed the forced dense token trajectory")
    transition_summary = recorder.summary()
    if not recorder.events or transition_summary.get("observed_layers") != list(selected_layers):
        raise AssertionError("A4.3.6 lifecycle trace lacks all-layer coverage")
    trace_path = args.output_dir / "a436_llama31_logical_lifecycle_microevents.jsonl.gz"
    trace_sha256 = write_transitions(trace_path, recorder)
    manifest = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(),
        "config": config, "config_hash": stable_hash(config), "cuda_environment": cuda_env,
        "execution_classification": "fixed-continuation functional/trace-derived Llama micro-event state evidence; not modeled or measured hardware evidence",
        "provenance": {"m0_manifest_sha256": m0_sha256, "m1_manifest_sha256": m1_sha256, "m51_report_sha256": m51_sha256, "m41_non_strict_summarization_context_retained": True},
        "request": {"request_id": request["request_id"], "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}), "context_tokens": int(context_ids.shape[1])},
        "continuation_contract": {"mode": "fixed_non_eos_continuation", "fixed_new_tokens": args.fixed_new_tokens, "actual_policy_decode_calls": expected_policy_decode_calls(args.fixed_new_tokens), "dense_token_trajectory_forced_in_route_a": True, "natural_generation_length_claimed": False},
        "full_kv_bypass_generated_token_ids_sha256": token_ids_digest(full["generated_token_ids"]),
        "dense_generated_token_ids_sha256": token_ids_digest(dense["generated_token_ids"]),
        "route_a_trace_off_generated_token_ids_sha256": token_ids_digest(route["generated_token_ids"]),
        "route_a_microevent_generated_token_ids_sha256": token_ids_digest(micro["generated_token_ids"]),
        "policy_coverage": {"dense": dense_coverage, "route_a_trace_off": route_coverage, "route_a_microevent": micro_coverage},
        "lifecycle_transition_trace": {"schema_version": "kvzap-route-a432-logical-lifecycle-transitions-1.0", "path": trace_path.name, "sha256": trace_sha256, "summary": transition_summary, "prefill_maturity_chunk_tokens": args.prefill_maturity_chunk_tokens, "recording_semantics": "scalar Route-A state around ordered logical micro-events; no queue arrival/completion or timestamp"},
        "observational_guards": {"m0_m1_m51_hash_bound": True, "m41_non_strict_summarization_context_retained": True, "all_32_layers_all_8_kv_heads_covered_dense_trace_off_and_microevent": True, "online_dense_mask_replayed_exactly_once_by_both_route_a_paths": True, "same_mask_numerical_guard_work_executed_by_all_paths": True, "record_only_ulp_context_not_a_strict_pass": True, "fixed_dense_token_trajectory_forced_in_route_a": True, "trace_off_route_a_tokens_equal_trace_on_microevent": True, "prefill_micro_event_trace_enabled": True, "logical_events_have_no_timestamps": True, "dms_press_used": False, "fake_key_attention_used": False, "masked_key_indices_created": False, "model_cache_mutated_by_backend": False},
        "boundaries": ["This preserves a M5.1 fixed non-EOS continuation and does not report natural generation length, quality, or serving behavior.", "The retained M4.1 summarization record-only ULP context is non-strict diagnostic evidence and does not choose a merge precision.", "Q is a logical reference action count. Pending and logical page state are not FIFO, HBM, physical-page, timing, capacity, latency, throughput, energy, area, hardware, architecture-specification, or RTL evidence."],
        "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__),
    }
    output = args.output_dir / "a436_llama31_microevent_manifest.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.3.6 Llama micro-event gate passed: {output}", flush=True)


if __name__ == "__main__":
    main()
