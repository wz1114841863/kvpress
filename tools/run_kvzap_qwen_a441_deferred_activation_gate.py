#!/usr/bin/env python3
"""A4.4.1 Qwen Full-KV-to-Route-A activation / benefit-bypass gate.

The fixed eight-token continuation provides a declared functional horizon for
two distinct branches: D=8 ends before activation under native Full KV; D=1
commits exactly once from the retained native prefix to Route-A logical state.
It is not a natural-length, allocator, timing, traffic, or hardware study.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from huggingface_hub import snapshot_download
from transformers import DynamicCache, pipeline

from kvpress import KVzapPress
from kvpress.route_a_attention import RouteALifecycleTransitionRecorder
from kvpress.route_a_policy_backend import DeferredActivationRouteAPolicyAttentionBackendSet
from tools.export_kvzap_predictor_trace import (
    GATE_A_PREDICTOR_REVISION,
    GATE_B_MODEL_REVISION,
    assert_no_runtime_mask_state,
    file_sha256,
    get_git_commit,
    stable_hash,
    validate_gate_a_evidence,
)
from tools.run_kvzap_route_a40_policy_gate import cuda_environment, write_lifecycle_transitions
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, build_builtin_request, seed_everything


SCHEMA = "kvzap-route-a441-qwen-deferred-activation-contract-1.0"
A435_SCHEMA = "kvzap-route-a435-microevent-quantum-sweep-1.0"
WORKLOADS = ("retrieval", "summarization", "reasoning")


def token_ids_digest(token_ids: list[int]) -> str:
    return hashlib.sha256(",".join(str(token) for token in token_ids).encode("ascii")).hexdigest()


def expected_policy_decode_calls(fixed_new_tokens: int) -> int:
    if fixed_new_tokens < 2:
        raise ValueError("fixed continuation requires at least two tokens")
    return fixed_new_tokens - 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.4.1 Qwen Full-KV-to-Route-A activation and benefit-bypass functional gate; no hardware measurement."
    )
    parser.add_argument("--gate-a-evidence", type=Path, default=Path("traces/hardware_predictor_gate_a_01"))
    parser.add_argument("--a435-report", type=Path, required=True)
    parser.add_argument("--presets", nargs="+", choices=WORKLOADS, default=list(WORKLOADS))
    parser.add_argument("--model-name", default=DEFAULT_MODEL)
    parser.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR)
    parser.add_argument("--predictor-revision", default=GATE_A_PREDICTOR_REVISION)
    parser.add_argument("--threshold", type=float, default=-4.0)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--page-tokens", type=int, default=64, help="Functional reference input; not a hardware choice.")
    parser.add_argument("--admission-budget", type=int, default=512, help="One logical commit action; not a hardware service rate.")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--fixed-new-tokens", type=int, default=8)
    parser.add_argument("--active-deferred-decode-steps", type=int, default=1)
    parser.add_argument("--bypass-deferred-decode-steps", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--execution-dtype-ulp-mode", choices=("enforce", "record_only"), default="record_only")
    parser.add_argument("--execution-dtype-close-mode", choices=("quantization_aware_enforce",), default="quantization_aware_enforce")
    parser.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def read_completed_a435(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"A4.3.5 Qwen report is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != A435_SCHEMA or value.get("status") != "complete":
        raise ValueError("A4.4.1 requires a completed Qwen A4.3.5 report")
    if value.get("config", {}).get("admission_budgets") != [1, 8, 32]:
        raise ValueError("A4.4.1 requires the completed Qwen A4.3.5 Q={1,8,32} source")
    rows = value.get("per_workload_rows")
    if not isinstance(rows, list) or {row.get("preset") for row in rows} != set(WORKLOADS):
        raise ValueError("A4.4.1 requires all three Qwen A4.3.5 workload rows")
    return value


def fixed_continuation(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, args: argparse.Namespace, backend=None, forced_token_ids: list[int] | None = None) -> dict[str, Any]:
    """Execute an exact non-EOS horizon, optionally under fixed token inputs."""
    if forced_token_ids is not None and len(forced_token_ids) != args.fixed_new_tokens:
        raise ValueError("forced token count differs from declared fixed horizon")
    seed_everything(args.seed)
    cache = DynamicCache()
    logits: list[torch.Tensor] = []
    generated: list[int] = []
    context = backend if backend is not None else torch.no_grad()
    with torch.no_grad(), context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        question_position = torch.arange(
            int(context_ids.shape[1]), int(context_ids.shape[1]) + int(question_ids.shape[1]), device=pipe.model.device
        ).unsqueeze(0)
        output = pipe.model(input_ids=question_ids, past_key_values=cache, position_ids=question_position, num_logits_to_keep=1)
        logits.append(output.logits[0, -1].detach())
        for step in range(args.fixed_new_tokens):
            token = int(forced_token_ids[step]) if forced_token_ids is not None else int(logits[-1].argmax().item())
            generated.append(token)
            if step + 1 == args.fixed_new_tokens:
                break
            output = pipe.model(
                input_ids=torch.tensor([[token]], dtype=question_ids.dtype, device=pipe.model.device),
                past_key_values=cache,
                position_ids=torch.tensor([[int(context_ids.shape[1]) + int(question_ids.shape[1]) + step]], device=pipe.model.device),
                num_logits_to_keep=1,
            )
            logits.append(output.logits[0, -1].detach())
    if len(generated) != args.fixed_new_tokens or len(logits) != args.fixed_new_tokens:
        raise AssertionError("fixed continuation did not execute the declared horizon")
    return {"generated_token_ids": generated, "logits": logits}


def assert_journal_coverage(mask_events: dict[int, dict[tuple[int, int], Any]], *, layers: tuple[int, ...], heads_by_layer: dict[int, tuple[int, ...]], label: str) -> None:
    """Check predictor journal completeness even when bypass has no Route-A state."""
    if set(mask_events) != set(layers):
        raise AssertionError(f"{label}: decision journal lacks selected layers")
    for layer in layers:
        events = mask_events[layer]
        by_head = {head: sorted(position for event_head, position in events if event_head == head) for head in heads_by_layer[layer]}
        if any(not positions for positions in by_head.values()):
            raise AssertionError(f"{label}: layer {layer} lacks a KV-head decision stream")
        reference = next(iter(by_head.values()))
        if reference[0] != 0 or reference != list(range(reference[-1] + 1)):
            raise AssertionError(f"{label}: layer {layer} has non-contiguous journal positions")
        if any(positions != reference for positions in by_head.values()):
            raise AssertionError(f"{label}: layer {layer} has inconsistent KV-head journal positions")


def validate_bypass(summary: dict[str, Any], *, layers: tuple[int, ...], expected_prefix_calls: int) -> None:
    rows = summary.get("layers", [])
    if {row.get("layer") for row in rows} != set(layers):
        raise AssertionError("bypass summary lacks selected layers")
    for row in rows:
        if row["activation_committed"] or row["route_a_logical_state_exists_at_end"] or row["mode_at_trace_end"] != "full_kv_bypass":
            raise AssertionError(f"layer {row['layer']}: end-before-activation branch created Route-A state")
        if row["full_kv_prefix_decode_calls"] != expected_prefix_calls or row["native_cache_mutated_or_freed"]:
            raise AssertionError(f"layer {row['layer']}: bypass did not remain native Full-KV through end")


def validate_activation(summary: dict[str, Any], *, layers: tuple[int, ...], active_steps: int, window: int) -> dict[str, int]:
    rows = summary.get("layers", [])
    if {row.get("layer") for row in rows} != set(layers):
        raise AssertionError("activation summary lacks selected layers")
    totals = {key: 0 for key in ("matured_kept_tokens", "matured_dropped_tokens", "pending_tokens_after_commit", "admitted_tokens", "hot_tokens_after_commit", "packed_tokens_after_commit", "logical_page_count_after_commit")}
    for row in rows:
        event = row["activation_event"]
        if not row["activation_committed"] or not row["route_a_logical_state_exists_at_end"] or event is None:
            raise AssertionError(f"layer {row['layer']}: activation did not commit")
        if (event["mode_before_commit"], event["mode_after_commit"]) != ("full_kv_bypass", "route_a_active"):
            raise AssertionError(f"layer {row['layer']}: invalid activation transition")
        if event["activation_decode_call_after_full_prefix"] != active_steps or event["route_a_logical_state_existed_before_commit"]:
            raise AssertionError(f"layer {row['layer']}: invalid activation boundary")
        if event["native_cache_mutated_or_freed_by_commit"] or row["native_cache_mutated_or_freed"]:
            raise AssertionError(f"layer {row['layer']}: activation mutated native cache")
        if event["history_token_count"] <= window or event["matured_position_count"] <= 0:
            raise AssertionError(f"layer {row['layer']}: activation did not cross the hot-window boundary")
        if event["journal_mask_decision_count_before_commit"] != event["history_token_count"] * len(event["heads"]):
            raise AssertionError(f"layer {row['layer']}: incomplete activation decision journal")
        for head in event["heads"]:
            for key in totals:
                totals[key] += int(head[key])
    if totals["matured_kept_tokens"] <= 0 or totals["packed_tokens_after_commit"] <= 0:
        raise AssertionError("activation did not retain and logically pack mature K/V")
    return totals


def run_deferred(*, pipe, context_ids, question_ids, args: argparse.Namespace, layers: tuple[int, ...], deferred_steps: int, recorder: RouteALifecycleTransitionRecorder | None = None, forced_token_ids: list[int] | None = None):
    backend = DeferredActivationRouteAPolicyAttentionBackendSet(
        pipe.model,
        KVzapPress(model_type="mlp", predictor_revision=args.predictor_revision),
        layers=layers, kv_head=None, threshold=args.threshold, window=args.window_size,
        page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol,
        max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode=args.execution_dtype_ulp_mode,
        execution_dtype_close_mode=args.execution_dtype_close_mode, ulp_breach_sample_limit=args.ulp_breach_sample_limit,
        deferred_decode_steps=deferred_steps, lifecycle_transition_recorder=recorder,
    )
    result = fixed_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, backend=backend, forced_token_ids=forced_token_ids)
    assert_no_runtime_mask_state(pipe.model)
    return result, backend


def run_workload(*, workload: str, pipe, args: argparse.Namespace, layers: tuple[int, ...], heads_by_layer: dict[int, tuple[int, ...]], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    request = build_builtin_request(workload, args.context_repetitions)
    tokens = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokens["context_ids"].to(pipe.model.device)
    question_ids = tokens["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size:
        raise ValueError(f"A4.4.1 {workload}: context does not cross protected hot window")
    print(f"A4.4.1 {workload}: native Full-KV fixed-horizon reference...", flush=True)
    full = fixed_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args)
    assert_no_runtime_mask_state(pipe.model)
    print(f"A4.4.1 {workload}: end-before-activation Full-KV bypass...", flush=True)
    bypass, bypass_backend = run_deferred(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, layers=layers, deferred_steps=args.bypass_deferred_decode_steps)
    bypass_summary = bypass_backend.deferred_activation_summary()
    validate_bypass(bypass_summary, layers=layers, expected_prefix_calls=expected_policy_decode_calls(args.fixed_new_tokens))
    assert_journal_coverage(bypass_backend.mask_events(), layers=layers, heads_by_layer=heads_by_layer, label=f"A4.4.1 {workload} bypass")
    if bypass["generated_token_ids"] != full["generated_token_ids"]:
        raise AssertionError(f"A4.4.1 {workload}: unactivated Full-KV bypass changed greedy tokens")
    recorder = RouteALifecycleTransitionRecorder()
    print(f"A4.4.1 {workload}: Full-KV-to-Route-A activation after {args.active_deferred_decode_steps} q_len=1 call(s)...", flush=True)
    active, active_backend = run_deferred(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, layers=layers, deferred_steps=args.active_deferred_decode_steps, recorder=recorder, forced_token_ids=full["generated_token_ids"])
    active_summary = active_backend.deferred_activation_summary()
    totals = validate_activation(active_summary, layers=layers, active_steps=args.active_deferred_decode_steps, window=args.window_size)
    assert_journal_coverage(active_backend.mask_events(), layers=layers, heads_by_layer=heads_by_layer, label=f"A4.4.1 {workload} activation")
    if active["generated_token_ids"] != full["generated_token_ids"]:
        raise AssertionError(f"A4.4.1 {workload}: forced activation inputs do not match Full-KV reference")
    expected_active_calls = expected_policy_decode_calls(args.fixed_new_tokens) - args.active_deferred_decode_steps
    if set(active_backend.policy_decode_calls.values()) != {expected_active_calls}:
        raise AssertionError(f"A4.4.1 {workload}: post-commit Route-A q_len=1 call count differs from {expected_active_calls}")
    guard = active_backend.same_mask_numerical_guard_work_summary()
    if any(int(row["work_count"]) <= 0 for row in guard["layers"]):
        raise AssertionError(f"A4.4.1 {workload}: a layer skipped post-commit same-mask numerical work")
    if not recorder.events or recorder.summary()["observed_layers"] != list(layers):
        raise AssertionError(f"A4.4.1 {workload}: incomplete post-commit lifecycle trace")
    trace_path = output_dir / "a441_post_commit_logical_lifecycle_events.jsonl.gz"
    trace_sha256 = write_lifecycle_transitions(trace_path, recorder)
    return {
        "request": {"request_id": request["request_id"], "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}), "context_tokens": int(context_ids.shape[1])},
        "full_kv_reference": {"generated_token_ids_sha256": token_ids_digest(full["generated_token_ids"]), "generated_token_count": len(full["generated_token_ids"])},
        "benefit_bypass_contract": {"deferred_decode_steps": args.bypass_deferred_decode_steps, "end_before_activation": True, "generated_token_ids_sha256": token_ids_digest(bypass["generated_token_ids"]), "generated_token_ids_equal_full_kv": True, "deferred_activation_summary": bypass_summary, "zero_route_a_logical_physicalization": True, "recording_semantics": "zero Route-A logical state/admission/page/PTE-metadata construction; native Full-KV remains authoritative. This does not observe allocator activity or physical memory."},
        "activation_contract": {"deferred_decode_steps": args.active_deferred_decode_steps, "forced_reference_token_ids_sha256": token_ids_digest(full["generated_token_ids"]), "forced_token_inputs_equal_full_kv": True, "deferred_activation_summary": active_summary, "activation_totals_over_layers_and_kv_heads": totals, "activation_commit_boundary": "pre-commit native Full-KV authoritative with predictor journal only; commit hydrates logical hot/pending/packed state and applies one configured logical admission action; post-commit Route-A logical state authoritative", "logical_metadata_event_semantics": "logical page counts are page-table-entry events without PTE width, allocator allocation, DMA, bank, burst, or timing interpretation", "post_commit_policy_decode_call_count_by_layer": active_backend.policy_decode_calls, "same_mask_numerical_guard_work": guard, "execution_dtype_ulp_breach_summary": active_backend.execution_dtype_ulp_breach_summary()},
        "post_commit_logical_trace": {"schema_version": RouteALifecycleTransitionRecorder.SCHEMA, "path": str(trace_path.relative_to(output_dir.parents[1])), "sha256": trace_sha256, "event_count": len(recorder.events), "summary": recorder.summary(), "recording_semantics": "post-commit scalar Route-A reference state transitions only; no activation-transfer completion, queue arrival/completion, physical traffic, or timestamp"},
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if sorted(args.presets) != sorted(WORKLOADS) or len(set(args.presets)) != len(WORKLOADS):
        raise ValueError("A4.4.1 requires retrieval, summarization, and reasoning exactly once")
    fixed = (DEFAULT_MODEL, GATE_B_MODEL_REVISION, DEFAULT_PREDICTOR, GATE_A_PREDICTOR_REVISION, -4.0, 128, 64, 512, 12, 8, 1, 8, 16.0, "record_only", "quantization_aware_enforce", 32, "cuda")
    observed = (args.model_name, args.model_revision, args.predictor_name, args.predictor_revision, args.threshold, args.window_size, args.page_tokens, args.admission_budget, args.context_repetitions, args.fixed_new_tokens, args.active_deferred_decode_steps, args.bypass_deferred_decode_steps, args.max_executed_dtype_ulps, args.execution_dtype_ulp_mode, args.execution_dtype_close_mode, args.ulp_breach_sample_limit, args.device)
    if observed != fixed or min(args.rtol, args.atol) <= 0:
        raise ValueError("A4.4.1 is fixed to the accepted Qwen inputs, D=1 activation, D=8 bypass, and quantization-aware numerical guard")
    cuda = cuda_environment(require_single_visible_device=True)
    gate_a = validate_gate_a_evidence(args.gate_a_evidence, model_name=args.model_name, predictor_name=args.predictor_name, threshold=args.threshold, window_size=args.window_size)
    if not gate_a["passed"]:
        raise ValueError("frozen Qwen Gate-A validation failed")
    a435 = read_completed_a435(args.a435_report)
    args.output_dir.mkdir(parents=True)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    started = {"schema_version": SCHEMA, "status": "started", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "boundaries": ["A4.4.1 is a fixed-horizon functional activation/bypass contract, not a natural-generation length or A3 benefit-curve study.", "The admission budget is one software-reference commit action, not a FIFO depth, service rate, controller schedule, or hardware parameter."]}
    (args.output_dir / "a441_deferred_activation_started.json").write_text(json.dumps(started, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"
    print(f"Loading A4.4.1 base model: {args.model_name}", flush=True)
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise AssertionError("loaded Qwen revision differs from frozen Gate-A/B")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    layers = tuple(range(len(language_model.layers)))
    heads_by_layer = {layer: tuple(range(int(language_model.layers[layer].self_attn.config.num_key_value_heads))) for layer in layers}
    if not layers or any(not heads for heads in heads_by_layer.values()):
        raise AssertionError("loaded Qwen structure has no Route-A layer/KV-head coverage")
    snapshot = Path(snapshot_download(repo_id=args.predictor_name, revision=args.predictor_revision))
    if snapshot.name != args.predictor_revision:
        raise AssertionError("resolved Qwen predictor snapshot differs from frozen Gate-A")
    per_workload = {workload: run_workload(workload=workload, pipe=pipe, args=args, layers=layers, heads_by_layer=heads_by_layer, output_dir=args.output_dir / workload) for workload in args.presets}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "functional fixed-request activation/bypass evidence plus timestamp-free logical lifecycle events; no measured or modeled hardware result", "provenance": {"gate_a_manifest_sha256": file_sha256(args.gate_a_evidence / "manifest.json"), "gate_a_score_mask_sha256": file_sha256(args.gate_a_evidence / "score_mask.npz"), "a435_report_sha256": file_sha256(args.a435_report), "a435_report_schema": a435["schema_version"], "predictor_snapshot_path": str(snapshot)}, "cuda_environment": cuda, "model_structure": {"layer_count": len(layers), "kv_head_count_by_layer": {str(layer): len(heads) for layer, heads in heads_by_layer.items()}}, "per_workload": per_workload, "observational_guards": {"single_visible_cuda_device": True, "all_selected_layers_all_kv_heads_journaled_for_bypass_and_active_each_workload": True, "pure_full_kv_end_before_activation_each_workload": True, "activation_commit_from_full_kv_history_each_workload": True, "pre_commit_has_no_route_a_logical_state_each_workload": True, "native_cache_not_mutated_or_freed_by_backend_each_workload": True, "full_kv_token_trajectory_retained_for_bypass_and_forced_active_inputs_each_workload": True, "post_commit_same_mask_numerical_guard_work_each_workload": True, "no_hardware_parameter_selected": True}, "boundaries": ["A4.4.1 validates only the Qwen Full-KV-to-Route-A functional transition and end-before-activation Full-KV bypass under three fixed requests. It does not measure natural output-length prevalence, quality, allocator behavior, physical capacity, HBM traffic, DMA, burst transfer, timing, latency, throughput, energy, area, or acceleration.", "Logical pages and metadata events intentionally have no PTE width, page/bank/burst mapping, FIFO depth, service rate, merge precision/PE, scheduler, controller timing, or architecture-spec interpretation.", "The native cache remains present in this functional reference; Route-A logical authority after commit must not be read as observed memory reclamation.", "Qwen rows must remain separate from A4.4.0 Llama rows. This gate creates no pooled hardware envelope and does not establish portability to arbitrary models or pruning algorithms. Capacity protection after Route-A activation remains a separate future contract."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    output = args.output_dir / "a441_qwen_deferred_activation_contract_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.4.1 Qwen deferred-activation contract completed: {output}")


if __name__ == "__main__":
    main()
