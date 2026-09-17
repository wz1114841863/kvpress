#!/usr/bin/env python3
"""A4.5.3 model-on next-epoch request-global protection semantic gate.

It executes the A4.5.2 contract exactly: activation retains the existing
layer-local primitive, while a shared controller latches on the first crossing
and switches every selected layer to native Full-KV only on the next decode
epoch. This is functional evidence, not a controller timing or hardware study.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
import transformers
from transformers import pipeline

from kvpress import KVzapPress
from kvpress.route_a_policy_backend import GlobalNextEpochCapacityProtectedRouteAPolicyAttentionBackendSet
from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_llama31_m1_semantic_gate import EXPECTED_STRUCTURE, make_predictor, validate_runtime_structure
from tools.run_kvzap_llama31_m51_fixed_horizon_workload_descriptor import fixed_continuation as llama_fixed_continuation
from tools.run_kvzap_qwen_a441_deferred_activation_gate import fixed_continuation as qwen_fixed_continuation
from tools.run_kvzap_route_a40_policy_gate import cuda_environment
from tools.run_kvzap_route_a451_capacity_protection_semantic_gate import DEFAULT_WATERMARK as HIGH_WATERMARK, SCHEMA as A451_SCHEMA, qwen_kv_head_counts, token_ids_digest
from tools.run_kvzap_trace import DEFAULT_MODEL as QWEN_MODEL, build_builtin_request
from tools.validate_kvzap_llama31_m0_provenance import DEFAULT_MODEL_REPO as LLAMA_MODEL, DEFAULT_MODEL_REVISION as LLAMA_REVISION, OFFICIAL_PREDICTOR_REPO


SCHEMA = "kvzap-route-a453-global-next-epoch-protection-gate-1.0"
A452_SCHEMA = "kvzap-route-a452-global-protection-controller-reconciliation-1.0"
WORKLOADS = ("retrieval", "summarization", "reasoning")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.5.3 model-on next-decode-epoch request-global native fallback gate; no controller timing or hardware measurement.")
    parser.add_argument("--anchor", choices=("qwen3_8b", "llama31_8b_instruct"), required=True)
    parser.add_argument("--a452-report", type=Path, required=True)
    parser.add_argument("--predictor-repo-id-override", default=None, help="Required only for the reviewed Llama public predictor repository.")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--fixed-new-tokens", type=int, default=8)
    parser.add_argument("--deferred-decode-steps", type=int, default=1)
    parser.add_argument("--page-tokens", type=int, default=64, help="Functional reference input only; not a hardware choice.")
    parser.add_argument("--admission-budget", type=int, default=512, help="One logical reference action only; not a service-rate claim.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--execution-dtype-ulp-mode", choices=("record_only",), default="record_only")
    parser.add_argument("--preflight-only", action="store_true", help="Validate A4.5.2 binding without CUDA/model load or output creation.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def read_a452(path: Path, *, anchor: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"A4.5.2 report is absent: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != A452_SCHEMA or report.get("status") != "complete":
        raise ValueError("A4.5.3 requires a completed A4.5.2 report")
    key = f"{anchor}_a451"
    source = report.get("input_artifacts", {}).get(key, {})
    a451_path = Path(str(source.get("report_path", "")))
    if not a451_path.is_file() or sha256_file(a451_path) != source.get("report_sha256"):
        raise ValueError(f"A4.5.2 {anchor} A4.5.1 source is unavailable or hash-mismatched")
    a451 = json.loads(a451_path.read_text(encoding="utf-8"))
    if a451.get("schema_version") != A451_SCHEMA or a451.get("status") != "complete":
        raise ValueError(f"A4.5.2 {anchor} source is not completed A4.5.1")
    rows = {row.get("workload"): row for row in report.get("anchor_workload_rows", []) if row.get("anchor") == anchor}
    if set(rows) != set(WORKLOADS):
        raise ValueError(f"A4.5.2 lacks three reconciliation rows for {anchor}")
    for workload, row in rows.items():
        controller = row.get("reconciled_request_global_controller_contract", {})
        local = row.get("a451_actual_layer_local_primitive", {})
        if row.get("pending_high_watermark") != HIGH_WATERMARK or local.get("source_threshold_set_matches_actual") is not True:
            raise ValueError(f"A4.5.2 {anchor}/{workload} does not retain C={HIGH_WATERMARK} local-set reconciliation")
        if controller.get("all_layer_global_protection_effective_boundary") != "next_decode_epoch_after_completion_of_current_activation_epoch" or controller.get("current_epoch_retroactive_reroute_permitted") is not False:
            raise ValueError(f"A4.5.2 {anchor}/{workload} does not retain the next-epoch non-retroactive contract")
    return report, a451, rows


def continuation_for(anchor: str):
    return qwen_fixed_continuation if anchor == "qwen3_8b" else llama_fixed_continuation


def build_predictor(args: argparse.Namespace, *, predictor_revision: str):
    if args.anchor == "qwen3_8b":
        return KVzapPress(model_type="mlp", predictor_revision=predictor_revision)
    return make_predictor(predictor_revision=predictor_revision, override=args.predictor_repo_id_override)


def validate_runtime_summary(*, summary: dict[str, Any], expected: dict[str, Any], layers: tuple[int, ...], workload: str) -> dict[str, Any]:
    controller = summary.get("controller", {})
    latch = controller.get("global_latch_event")
    expected_controller = expected["reconciled_request_global_controller_contract"]
    expected_local = expected["a451_actual_layer_local_primitive"]
    if not controller.get("activation_observations_complete") or controller.get("controller_timestamps_or_cycles_recorded"):
        raise AssertionError(f"{workload}: controller observations are incomplete or timed")
    if not isinstance(latch, dict) or latch.get("first_trigger_observation_layer") != expected_controller["first_trigger_observation_layer"]:
        raise AssertionError(f"{workload}: runtime first global latch differs from A4.5.2")
    if controller.get("all_layer_global_effective_boundary") != expected_controller["all_layer_global_protection_effective_boundary"]:
        raise AssertionError(f"{workload}: runtime global effective boundary differs from A4.5.2")
    observations = controller.get("activation_observations_by_layer", [])
    if [entry.get("layer") for entry in observations] != list(layers):
        raise AssertionError(f"{workload}: activation observations are not layer ordered/complete")
    expected_local_set = set(expected_local["protected_layer_indices"])
    runtime_local_set = set()
    global_layers = []
    current_epoch_route_a_layers = []
    for row in summary.get("layers", []):
        layer = int(row["layer"])
        if row.get("capacity_protection_committed"):
            runtime_local_set.add(layer)
        else:
            current_epoch_route_a_layers.append(layer)
        event = row.get("request_global_protection_event")
        if not row.get("request_global_protection_committed") or not isinstance(event, dict):
            raise AssertionError(f"{workload}: layer {layer} did not enter next-epoch request-global protection")
        if event.get("boundary") != "next_decode_epoch_after_completion_of_current_activation_epoch" or event.get("reentry_permitted"):
            raise AssertionError(f"{workload}: layer {layer} global transition violates contract")
        if int(row.get("request_global_native_attention_calls", 0)) <= 0 or row.get("route_a_logical_state_next_position_at_end") != event.get("route_a_state_next_position_frozen"):
            raise AssertionError(f"{workload}: layer {layer} did not retain native fallback/frozen Route-A state")
        global_layers.append(layer)
    if runtime_local_set != expected_local_set or set(global_layers) != set(layers):
        raise AssertionError(f"{workload}: local threshold set or all-layer next-epoch global coverage differs from contract")
    return {
        "runtime_local_protected_layer_indices": sorted(runtime_local_set),
        "runtime_current_activation_epoch_route_a_layer_indices": current_epoch_route_a_layers,
        "runtime_all_layer_next_epoch_global_protection": True,
        "first_global_latch_layer": latch["first_trigger_observation_layer"],
        "global_effective_cache_position": controller["global_effective_cache_position"],
    }


def run_workload(*, workload: str, pipe, args: argparse.Namespace, layers: tuple[int, ...], heads_by_layer: dict[int, int], predictor_revision: str, expected: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    request = build_builtin_request(workload, args.context_repetitions)
    tokens = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids, question_ids = tokens["context_ids"].to(pipe.model.device), tokens["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= 128:
        raise ValueError(f"{workload}: context does not cross the frozen hot window")
    continuation = continuation_for(args.anchor)
    print(f"A4.5.3 {args.anchor}/{workload}: native Full-KV fixed-horizon reference...", flush=True)
    full = continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args)
    assert_no_runtime_mask_state(pipe.model)
    print(f"A4.5.3 {args.anchor}/{workload}: local-current / next-epoch-global protection...", flush=True)
    backend = GlobalNextEpochCapacityProtectedRouteAPolicyAttentionBackendSet(
        pipe.model, build_predictor(args, predictor_revision=predictor_revision), layers=layers, kv_head=None,
        threshold=-4.0 if args.anchor == "qwen3_8b" else -7.0, window=128, page_tokens=args.page_tokens,
        admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol,
        max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode=args.execution_dtype_ulp_mode,
        execution_dtype_close_mode="quantization_aware_enforce" if args.anchor == "qwen3_8b" else "off",
        deferred_decode_steps=args.deferred_decode_steps, pending_high_watermark=HIGH_WATERMARK,
    )
    protected = continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, backend=backend, forced_token_ids=full["generated_token_ids"])
    assert_no_runtime_mask_state(pipe.model)
    if protected["generated_token_ids"] != full["generated_token_ids"]:
        raise AssertionError(f"{workload}: protected branch did not consume Full-KV fixed token inputs")
    summary = backend.global_next_epoch_summary()
    runtime = validate_runtime_summary(summary=summary, expected=expected, layers=layers, workload=workload)
    masks = backend.mask_events()
    if set(masks) != set(layers) or any(not masks[layer] for layer in layers):
        raise AssertionError(f"{workload}: predictor journals lack selected layer coverage")
    return {
        "request": {"request_id": request["request_id"], "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}), "context_tokens": int(context_ids.shape[1])},
        "full_kv_reference": {"generated_token_ids_sha256": token_ids_digest(full["generated_token_ids"]), "generated_token_count": len(full["generated_token_ids"])},
        "next_epoch_global_protection_contract": {"forced_reference_token_ids_sha256": token_ids_digest(full["generated_token_ids"]), "forced_token_inputs_equal_full_kv": True, "a452_expected_contract": expected["reconciled_request_global_controller_contract"], "runtime_validation": runtime, "runtime_summary": summary, "execution_scope": "model-on next-decode-epoch all-layer native fallback after current-epoch layer-local activation behavior", "no_reentry": True},
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    fixed = (12, 8, 1, 64, 512, 42, "record_only")
    if (args.context_repetitions, args.fixed_new_tokens, args.deferred_decode_steps, args.page_tokens, args.admission_budget, args.seed, args.execution_dtype_ulp_mode) != fixed or min(args.rtol, args.atol) <= 0:
        raise ValueError("A4.5.3 is fixed to existing 12x/fixed-8/D=1 functional inputs and record-only ULP context")
    a452, a451, expected = read_a452(args.a452_report, anchor=args.anchor)
    if args.anchor == "qwen3_8b":
        model_name, model_revision, predictor_revision = QWEN_MODEL, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION
        if args.predictor_repo_id_override is not None:
            raise ValueError("Qwen must retain default predictor derivation without an override")
    else:
        model_name, model_revision = LLAMA_MODEL, LLAMA_REVISION
        predictor_revision = str(a451.get("provenance", {}).get("predictor_revision", ""))
        if args.predictor_repo_id_override != OFFICIAL_PREDICTOR_REPO or not predictor_revision:
            raise ValueError("Llama requires reviewed predictor override and A4.5.1 predictor revision")
    if args.preflight_only:
        print(f"A4.5.3 preflight passed: {args.anchor}, three hash-bound A4.5.2 next-epoch controller rows; no model loaded.")
        return
    cuda = cuda_environment(require_single_visible_device=True)
    args.output_dir.mkdir(parents=True)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    (args.output_dir / "a453_global_next_epoch_protection_started.json").write_text(json.dumps({"schema_version": SCHEMA, "status": "started", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Loading A4.5.3 {args.anchor} base model: {model_name}", flush=True)
    pipe = pipeline("kv-press-text-generation", model=model_name, revision=model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != model_revision:
        raise AssertionError("loaded model revision differs from anchor provenance")
    if args.anchor == "qwen3_8b":
        language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
        layers, heads_by_layer = tuple(range(len(language_model.layers))), qwen_kv_head_counts(language_model)
    else:
        layer_count, head_count = validate_runtime_structure(pipe.model)
        if (layer_count, head_count) != (EXPECTED_STRUCTURE["layer_count"], EXPECTED_STRUCTURE["kv_head_count"]):
            raise AssertionError("loaded Llama dimensions differ from accepted provenance")
        layers, heads_by_layer = tuple(range(layer_count)), {layer: head_count for layer in range(layer_count)}
    per_workload = {workload: run_workload(workload=workload, pipe=pipe, args=args, layers=layers, heads_by_layer=heads_by_layer, predictor_revision=predictor_revision, expected=expected[workload], output_dir=args.output_dir / workload) for workload in WORKLOADS}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "model-on functional next-epoch request-global fallback evidence over a hash-bound A4.5.2 contract; no measured or modeled hardware result", "provenance": {"a452_report_path": str(args.a452_report), "a452_report_sha256": sha256_file(args.a452_report), "a451_source_report_sha256": sha256_file(Path(a452["input_artifacts"][f"{args.anchor}_a451"]["report_path"])), "predictor_revision": predictor_revision}, "cuda_environment": cuda, "model_structure": {"layer_count": len(layers), "kv_head_count_by_layer": {str(layer): heads_by_layer[layer] for layer in layers}}, "per_workload": per_workload, "observational_guards": {"single_visible_cuda_device": True, "a452_hash_bound_three_workload_next_epoch_contract": True, "ordered_layer_complete_activation_observations_each_workload": True, "runtime_local_protection_set_matches_a452_each_workload": True, "all_layers_global_native_fallback_next_epoch_each_workload": True, "frozen_route_a_state_and_no_reentry_each_workload": True, "forced_fixed_token_inputs_equal_full_kv_each_workload": True, "native_cache_not_mutated_or_freed_by_backend_each_workload": True, "no_hardware_parameter_selected": True}, "boundaries": ["A4.5.3 validates only the A4.5.2 next-decode-epoch request-global fallback semantics under bounded fixed continuations. It does not measure or implement controller timing, barrier/broadcast latency, scheduler behavior, queueing, or a physical global-control fabric.", "C=1024 remains a logical probe and the current activation epoch retains layer-local behavior; this gate cannot choose FIFO capacity/service, page/bank/burst, merge/PE, scheduler, controller timing, or hardware parameters.", "Forced Full-KV token inputs establish bounded functional continuation inputs only. The gate does not prove arbitrary natural-generation output/quality equivalence, allocator behavior, physical capacity, HBM/DMA traffic, bursts, timing, latency, throughput, energy, area, acceleration, architecture specification, or RTL.", "Qwen and Llama reports remain separate. No cross-anchor average, numerical envelope, or common hardware contract is derived."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    output = args.output_dir / "a453_global_next_epoch_protection_gate_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.5.3 {args.anchor} global next-epoch protection gate completed: {output}")


if __name__ == "__main__":
    main()
