#!/usr/bin/env python3
"""A4.4.0 Full-KV-to-Route-A activation / benefit-bypass functional gate.

This script deliberately reuses the established Llama M5.1 fixed eight-token
continuation.  ``deferred_decode_steps=8`` is an end-before-activation bypass
case; ``deferred_decode_steps=1`` commits after one native Full-KV q_len=1
step.  The commit is a logical reference-state hydration from the authoritative
native cache plus predictor journal.  It is not an allocator, transfer,
service-rate, timing, traffic, or hardware model.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from huggingface_hub import snapshot_download
from transformers import pipeline

from kvpress.route_a_attention import RouteALifecycleTransitionRecorder
from kvpress.route_a_policy_backend import DeferredActivationRouteAPolicyAttentionBackendSet
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
    WORKLOADS,
    expected_policy_decode_calls,
    fixed_continuation,
    sha256_file,
    token_ids_digest,
)
from tools.run_kvzap_route_a40_policy_gate import write_lifecycle_transitions
from tools.run_kvzap_trace import build_builtin_request
from tools.validate_kvzap_llama31_m0_provenance import (
    DEFAULT_MODEL_REPO,
    DEFAULT_MODEL_REVISION,
    OFFICIAL_PREDICTOR_REPO,
)


SCHEMA = "kvzap-route-a440-deferred-activation-contract-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.4.0 Llama Full-KV-to-Route-A activation and benefit-bypass functional gate; no hardware measurement."
    )
    parser.add_argument("--m0-manifest", type=Path, required=True)
    parser.add_argument("--m1-manifest", type=Path, required=True)
    parser.add_argument("--m51-report", type=Path, required=True)
    parser.add_argument("--presets", nargs="+", choices=WORKLOADS, default=list(WORKLOADS))
    parser.add_argument("--model-name", default=DEFAULT_MODEL_REPO)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--predictor-repo-id-override", required=True)
    parser.add_argument("--threshold", type=float, default=-7.0)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--page-tokens", type=int, default=64, help="Functional reference input; not a hardware selection.")
    parser.add_argument("--admission-budget", type=int, default=512, help="One logical activation-service action; not a service-rate claim.")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--fixed-new-tokens", type=int, default=8)
    parser.add_argument("--active-deferred-decode-steps", type=int, default=1)
    parser.add_argument("--bypass-deferred-decode-steps", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--execution-dtype-ulp-mode", choices=("enforce", "record_only"), default="record_only")
    parser.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def read_completed_m51(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"M5.1 report is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != M51_SCHEMA or value.get("status") != "complete":
        raise ValueError("A4.4.0 requires a completed M5.1 fixed-horizon report")
    return value


def activation_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = summary["layers"]
    if not isinstance(rows, list) or not rows:
        raise AssertionError("deferred activation summary has no layers")
    return rows


def assert_journal_coverage(mask_events: dict[int, dict[tuple[int, int], Any]], *, layers: int, heads: int, label: str) -> None:
    """Check journal decisions without requiring Route-A state construction.

    This is intentionally distinct from ``coverage()``, whose empty result is
    exactly the expected result for an end-before-activation bypass.
    """
    if set(mask_events) != set(range(layers)):
        raise AssertionError(f"{label}: journal does not cover every selected layer")
    for layer, events in mask_events.items():
        by_head = {head: sorted(position for (event_head, position) in events if event_head == head) for head in range(heads)}
        if any(not positions for positions in by_head.values()):
            raise AssertionError(f"{label}: layer {layer} lacks one or more KV-head decision streams")
        reference = by_head[0]
        if reference[0] != 0 or reference != list(range(reference[-1] + 1)):
            raise AssertionError(f"{label}: layer {layer} has non-contiguous decision positions")
        if any(positions != reference for positions in by_head.values()):
            raise AssertionError(f"{label}: layer {layer} has unequal KV-head journal positions")


def validate_bypass(summary: dict[str, Any], *, layers: int, expected_prefix_calls: int) -> None:
    rows = activation_rows(summary)
    if len(rows) != layers:
        raise AssertionError("bypass layer coverage is incomplete")
    for row in rows:
        if row["activation_committed"] or row["route_a_logical_state_exists_at_end"]:
            raise AssertionError(f"layer {row['layer']}: end-before-activation case created Route-A logical state")
        if row["mode_at_trace_end"] != "full_kv_bypass" or row["full_kv_prefix_decode_calls"] != expected_prefix_calls:
            raise AssertionError(f"layer {row['layer']}: bypass contract is not pure Full-KV through end")
        if row["native_cache_mutated_or_freed"]:
            raise AssertionError(f"layer {row['layer']}: bypass mutated or freed native cache")


def validate_activation(summary: dict[str, Any], *, layers: int, active_steps: int) -> dict[str, int]:
    rows = activation_rows(summary)
    if len(rows) != layers:
        raise AssertionError("activation layer coverage is incomplete")
    totals = {key: 0 for key in ("matured_kept_tokens", "matured_dropped_tokens", "pending_tokens_after_commit", "admitted_tokens", "hot_tokens_after_commit", "packed_tokens_after_commit", "logical_page_count_after_commit")}
    for row in rows:
        event = row["activation_event"]
        if not row["activation_committed"] or not row["route_a_logical_state_exists_at_end"] or event is None:
            raise AssertionError(f"layer {row['layer']}: expected Route-A activation did not commit")
        if row["mode_at_trace_end"] != "route_a_active" or event["mode_before_commit"] != "full_kv_bypass" or event["mode_after_commit"] != "route_a_active":
            raise AssertionError(f"layer {row['layer']}: invalid activation mode transition")
        if event["activation_decode_call_after_full_prefix"] != active_steps or event["route_a_logical_state_existed_before_commit"]:
            raise AssertionError(f"layer {row['layer']}: activation boundary does not match the deferred policy")
        if event["native_cache_mutated_or_freed_by_commit"] or row["native_cache_mutated_or_freed"]:
            raise AssertionError(f"layer {row['layer']}: functional activation mutated or freed native cache")
        if event["history_token_count"] <= 128 or event["matured_position_count"] <= 0:
            raise AssertionError(f"layer {row['layer']}: activation history did not cross the hot-window boundary")
        if event["journal_mask_decision_count_before_commit"] != event["history_token_count"] * len(event["heads"]):
            raise AssertionError(f"layer {row['layer']}: activation decision journal is incomplete")
        for head in event["heads"]:
            for key in totals:
                totals[key] += int(head[key])
    if totals["matured_kept_tokens"] <= 0 or totals["packed_tokens_after_commit"] <= 0:
        raise AssertionError("activation did not retain and logically pack mature KV")
    return totals


def run_deferred(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, args: argparse.Namespace, revision: str, layers: int, deferred_steps: int, recorder: RouteALifecycleTransitionRecorder | None = None, forced_token_ids: list[int] | None = None) -> tuple[dict[str, Any], DeferredActivationRouteAPolicyAttentionBackendSet]:
    backend = DeferredActivationRouteAPolicyAttentionBackendSet(
        pipe.model,
        make_predictor(predictor_revision=revision, override=args.predictor_repo_id_override),
        layers=tuple(range(layers)), kv_head=None, threshold=args.threshold, window=args.window_size,
        page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol,
        max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode=args.execution_dtype_ulp_mode,
        ulp_breach_sample_limit=args.ulp_breach_sample_limit, deferred_decode_steps=deferred_steps,
        lifecycle_transition_recorder=recorder,
    )
    result = fixed_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, backend=backend, forced_token_ids=forced_token_ids)
    assert_no_runtime_mask_state(pipe.model)
    return result, backend


def run_workload(*, workload: str, pipe, args: argparse.Namespace, revision: str, layers: int, heads: int, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    request = build_builtin_request(workload, args.context_repetitions)
    tokens = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokens["context_ids"].to(pipe.model.device)
    question_ids = tokens["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size:
        raise ValueError(f"A4.4.0 {workload}: context does not cross protected hot window")
    print(f"A4.4.0 {workload}: native Full-KV fixed-horizon reference...", flush=True)
    full = fixed_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args)
    assert_no_runtime_mask_state(pipe.model)
    print(f"A4.4.0 {workload}: end-before-activation Full-KV bypass...", flush=True)
    bypass, bypass_backend = run_deferred(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, revision=revision, layers=layers, deferred_steps=args.bypass_deferred_decode_steps)
    bypass_summary = bypass_backend.deferred_activation_summary()
    validate_bypass(bypass_summary, layers=layers, expected_prefix_calls=expected_policy_decode_calls(args.fixed_new_tokens))
    assert_journal_coverage(bypass_backend.mask_events(), layers=layers, heads=heads, label=f"A4.4.0 {workload} bypass journal")
    if bypass["generated_token_ids"] != full["generated_token_ids"]:
        raise AssertionError(f"A4.4.0 {workload}: unactivated Full-KV bypass changed the greedy token trajectory")
    recorder = RouteALifecycleTransitionRecorder()
    print(f"A4.4.0 {workload}: Full-KV-to-Route-A activation after {args.active_deferred_decode_steps} q_len=1 call(s)...", flush=True)
    active, active_backend = run_deferred(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, revision=revision, layers=layers, deferred_steps=args.active_deferred_decode_steps, recorder=recorder, forced_token_ids=full["generated_token_ids"])
    active_summary = active_backend.deferred_activation_summary()
    activation_totals = validate_activation(active_summary, layers=layers, active_steps=args.active_deferred_decode_steps)
    assert_all_layer_head_coverage(active_backend.coverage(), expected_layers=layers, expected_kv_heads=heads, label=f"A4.4.0 {workload} active")
    assert_journal_coverage(active_backend.mask_events(), layers=layers, heads=heads, label=f"A4.4.0 {workload} active journal")
    assert_numerical_guard_work(active_backend.same_mask_numerical_guard_work_summary(), layers, label=f"A4.4.0 {workload} active")
    if active["generated_token_ids"] != full["generated_token_ids"]:
        raise AssertionError(f"A4.4.0 {workload}: forced active continuation does not preserve reference token inputs")
    expected_active_calls = expected_policy_decode_calls(args.fixed_new_tokens) - args.active_deferred_decode_steps
    if set(active_backend.policy_decode_calls.values()) != {expected_active_calls}:
        raise AssertionError(f"A4.4.0 {workload}: active Route-A q_len=1 call count is not {expected_active_calls}")
    if not recorder.events or recorder.summary()["observed_layers"] != list(range(layers)):
        raise AssertionError(f"A4.4.0 {workload}: post-commit Route-A lifecycle trace is incomplete")
    trace_path = output_dir / "a440_post_commit_logical_lifecycle_events.jsonl.gz"
    trace_sha256 = write_lifecycle_transitions(trace_path, recorder)
    return {
        "request": {"request_id": request["request_id"], "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}), "context_tokens": int(context_ids.shape[1])},
        "full_kv_reference": {"generated_token_ids_sha256": token_ids_digest(full["generated_token_ids"]), "generated_token_count": len(full["generated_token_ids"])},
        "benefit_bypass_contract": {"deferred_decode_steps": args.bypass_deferred_decode_steps, "end_before_activation": True, "generated_token_ids_sha256": token_ids_digest(bypass["generated_token_ids"]), "generated_token_ids_equal_full_kv": True, "deferred_activation_summary": bypass_summary, "zero_route_a_logical_physicalization": True, "recording_semantics": "zero Route-A logical state/admission/page/PTE-metadata construction; native Full-KV remains authoritative. This does not observe allocator activity or physical memory."},
        "activation_contract": {"deferred_decode_steps": args.active_deferred_decode_steps, "forced_reference_token_ids_sha256": token_ids_digest(full["generated_token_ids"]), "forced_token_inputs_equal_full_kv": True, "deferred_activation_summary": active_summary, "activation_totals_over_layers_and_kv_heads": activation_totals, "activation_commit_boundary": "pre-commit native Full-KV authoritative with predictor journal only; commit hydrates logical hot/pending/packed state and applies one configured logical admission action; post-commit Route-A logical state authoritative", "logical_metadata_event_semantics": "logical page counts are page-table-entry events without PTE width, allocator allocation, DMA, bank, burst, or timing interpretation", "post_commit_policy_decode_call_count_by_layer": active_backend.policy_decode_calls, "same_mask_numerical_guard_work": active_backend.same_mask_numerical_guard_work_summary(), "execution_dtype_ulp_breach_summary": active_backend.execution_dtype_ulp_breach_summary()},
        "post_commit_logical_trace": {"schema_version": RouteALifecycleTransitionRecorder.SCHEMA, "path": str(trace_path.relative_to(output_dir.parents[1])), "sha256": trace_sha256, "event_count": len(recorder.events), "summary": recorder.summary(), "recording_semantics": "post-commit scalar Route-A reference state transitions only; no activation-transfer completion, queue arrival/completion, physical traffic, or timestamp"},
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if sorted(args.presets) != sorted(WORKLOADS) or len(set(args.presets)) != len(WORKLOADS):
        raise ValueError("A4.4.0 requires retrieval, summarization, and reasoning exactly once")
    fixed = (DEFAULT_MODEL_REPO, DEFAULT_MODEL_REVISION, OFFICIAL_PREDICTOR_REPO, -7.0, 128, 64, 512, 12, 8, 1, 8, 16.0, "record_only", 32, "cuda")
    observed = (args.model_name, args.model_revision, args.predictor_repo_id_override, args.threshold, args.window_size, args.page_tokens, args.admission_budget, args.context_repetitions, args.fixed_new_tokens, args.active_deferred_decode_steps, args.bypass_deferred_decode_steps, args.max_executed_dtype_ulps, args.execution_dtype_ulp_mode, args.ulp_breach_sample_limit, args.device)
    if observed != fixed or min(args.rtol, args.atol) <= 0:
        raise ValueError("A4.4.0 is fixed to M5.1 inputs, D=1 activation and D=8 end-before-activation bypass")
    m0_sha256 = sha256_file(args.m0_manifest)
    read_completed_m0(args.m0_manifest)
    m1 = read_completed_m1(args.m1_manifest, m0_sha256=m0_sha256)
    m1_sha256 = sha256_file(args.m1_manifest)
    m51 = read_completed_m51(args.m51_report)
    m51_sha256 = sha256_file(args.m51_report)
    revision = str(m1["config"]["predictor_revision"])
    if m51["provenance"]["m0_manifest_sha256"] != m0_sha256 or m51["provenance"]["m1_manifest_sha256"] != m1_sha256 or m51["provenance"]["predictor_revision"] != revision:
        raise ValueError("A4.4.0 input provenance does not match completed M5.1")
    args.output_dir.mkdir(parents=True)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    started = {"schema_version": SCHEMA, "status": "started", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "boundaries": ["A4.4.0 is a functional activation/bypass contract under the M5.1 fixed continuation, not an A3 benefit-curve rerun.", "Its activation admission budget is one software-reference action, not a FIFO depth, service rate, controller schedule, or final hardware parameter."]}
    (args.output_dir / "a440_deferred_activation_started.json").write_text(json.dumps(started, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"
    print(f"Loading A4.4.0 base model: {args.model_name}", flush=True)
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise AssertionError("loaded model revision differs from M0/M1")
    layers, heads = validate_runtime_structure(pipe.model)
    if (layers, heads) != (EXPECTED_STRUCTURE["layer_count"], EXPECTED_STRUCTURE["kv_head_count"]):
        raise AssertionError("loaded model dimensions differ from fixed M5.1 structure")
    snapshot = Path(snapshot_download(repo_id=OFFICIAL_PREDICTOR_REPO, revision=revision))
    if snapshot.name != revision:
        raise AssertionError("resolved predictor snapshot differs from M1")
    per_workload = {workload: run_workload(workload=workload, pipe=pipe, args=args, revision=revision, layers=layers, heads=heads, output_dir=args.output_dir / workload) for workload in args.presets}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "functional fixed-request activation/bypass evidence plus timestamp-free logical lifecycle events; no measured or modeled hardware result", "provenance": {"m0_manifest_sha256": m0_sha256, "m1_manifest_sha256": m1_sha256, "m51_report_sha256": m51_sha256, "predictor_revision": revision, "predictor_snapshot_path": str(snapshot)}, "per_workload": per_workload, "observational_guards": {"all_32_layers_all_8_kv_heads_journaled_for_bypass_and_active_each_workload": True, "pure_full_kv_end_before_activation_each_workload": True, "activation_commit_from_full_kv_history_each_workload": True, "pre_commit_has_no_route_a_logical_state_each_workload": True, "native_cache_not_mutated_or_freed_by_backend_each_workload": True, "full_kv_token_trajectory_retained_for_bypass_and_forced_active_inputs_each_workload": True, "post_commit_same_mask_numerical_guard_work_each_workload": True, "no_hardware_parameter_selected": True}, "boundaries": ["A4.4.0 validates only the Full-KV-to-Route-A functional transition and end-before-activation Full-KV bypass under three fixed Llama requests. It does not measure natural output-length prevalence, accuracy, serving quality, allocator behavior, physical capacity, HBM traffic, DMA, burst transfer, timing, latency, throughput, energy, area, or acceleration.", "Logical pages and metadata events intentionally have no PTE width, page/bank/burst mapping, FIFO depth, service rate, merge precision/PE, scheduler, controller timing, or architecture-spec interpretation.", "The native cache remains present in this functional reference; Route-A logical authority after commit must not be read as observed memory reclamation.", "This Llama gate does not make Qwen and Llama a pooled hardware envelope and does not establish portability to arbitrary models or pruning algorithms. A later capacity-protection contract is separately required for Route-A-active pressure/degraded transitions."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    output = args.output_dir / "a440_deferred_activation_contract_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.4.0 deferred-activation contract completed: {output}")


if __name__ == "__main__":
    main()
