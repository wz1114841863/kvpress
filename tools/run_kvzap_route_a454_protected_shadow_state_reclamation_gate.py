#!/usr/bin/env python3
"""A4.5.4 protected Route-A shadow-state tombstone semantic gate.

This gate extends the completed A4.5.3 next-epoch global fallback with a
fail-closed logical shadow-state tombstone. It is functional evidence only:
the tombstone is not an allocator operation or a physical-memory measurement.
"""
from __future__ import annotations

import argparse
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

from kvpress.route_a_policy_backend import ReclaimingGlobalNextEpochCapacityProtectedRouteAPolicyAttentionBackendSet
from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_llama31_m1_semantic_gate import EXPECTED_STRUCTURE, validate_runtime_structure
from tools.run_kvzap_route_a40_policy_gate import cuda_environment
from tools.run_kvzap_route_a451_capacity_protection_semantic_gate import qwen_kv_head_counts, token_ids_digest
from tools.run_kvzap_route_a453_global_next_epoch_protection_gate import HIGH_WATERMARK, WORKLOADS, build_predictor, continuation_for, read_a452
from tools.run_kvzap_trace import DEFAULT_MODEL as QWEN_MODEL, build_builtin_request
from tools.validate_kvzap_llama31_m0_provenance import DEFAULT_MODEL_REPO as LLAMA_MODEL, DEFAULT_MODEL_REVISION as LLAMA_REVISION, OFFICIAL_PREDICTOR_REPO


SCHEMA = "kvzap-route-a454-protected-shadow-state-reclamation-gate-1.0"
A453_SCHEMA = "kvzap-route-a453-global-next-epoch-protection-gate-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.5.4 model-on logical Route-A shadow-state tombstone gate; no allocator, physical-memory, timing, or hardware measurement.")
    parser.add_argument("--anchor", choices=("qwen3_8b", "llama31_8b_instruct"), required=True)
    parser.add_argument("--a453-report", type=Path, required=True)
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
    parser.add_argument("--preflight-only", action="store_true", help="Validate A4.5.3/A4.5.2 provenance and semantics without CUDA/model load or output creation.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def read_a453(path: Path, *, anchor: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"A4.5.3 report is absent: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != A453_SCHEMA or report.get("status") != "complete":
        raise ValueError("A4.5.4 requires a completed A4.5.3 report")
    guards = report.get("observational_guards", {})
    required_guards = (
        "a452_hash_bound_three_workload_next_epoch_contract",
        "ordered_layer_complete_activation_observations_each_workload",
        "runtime_local_protection_set_matches_a452_each_workload",
        "all_layers_global_native_fallback_next_epoch_each_workload",
        "frozen_route_a_state_and_no_reentry_each_workload",
        "forced_fixed_token_inputs_equal_full_kv_each_workload",
        "native_cache_not_mutated_or_freed_by_backend_each_workload",
        "no_hardware_parameter_selected",
    )
    if any(guards.get(key) is not True for key in required_guards):
        raise ValueError("A4.5.3 source does not retain every required next-epoch semantic guard")
    a452_path = Path(str(report.get("provenance", {}).get("a452_report_path", "")))
    if not a452_path.is_file() or sha256_file(a452_path) != report.get("provenance", {}).get("a452_report_sha256"):
        raise ValueError("A4.5.3 A4.5.2 source is unavailable or hash-mismatched")
    a452, a451, expected = read_a452(a452_path, anchor=anchor)
    workloads = report.get("per_workload", {})
    if set(workloads) != set(WORKLOADS):
        raise ValueError(f"A4.5.3 lacks three workload rows for {anchor}")
    for workload, row in workloads.items():
        source = row.get("next_epoch_global_protection_contract", {})
        source_summary = source.get("runtime_summary", {})
        controller = source_summary.get("controller", {})
        expected_local = expected[workload]["a451_actual_layer_local_primitive"]["protected_layer_indices"]
        source_local = source.get("runtime_validation", {}).get("runtime_local_protected_layer_indices")
        if source.get("forced_token_inputs_equal_full_kv") is not True or source_local != expected_local:
            raise ValueError(f"A4.5.3 {anchor}/{workload} lacks its source local-protection contract")
        if controller.get("activation_observations_complete") is not True or controller.get("global_effective_cache_position") != controller.get("global_latch_event", {}).get("cache_position", -2) + 1:
            raise ValueError(f"A4.5.3 {anchor}/{workload} lacks the complete next-epoch controller boundary")
    return report, a452, a451, expected


def validate_runtime_summary(*, summary: dict[str, Any], source_row: dict[str, Any], expected: dict[str, Any], layers: tuple[int, ...], workload: str) -> dict[str, Any]:
    controller = summary.get("controller", {})
    latch = controller.get("global_latch_event")
    source = source_row["next_epoch_global_protection_contract"]
    expected_controller = expected["reconciled_request_global_controller_contract"]
    expected_local = set(expected["a451_actual_layer_local_primitive"]["protected_layer_indices"])
    if not isinstance(latch, dict) or not controller.get("activation_observations_complete") or controller.get("controller_timestamps_or_cycles_recorded"):
        raise AssertionError(f"{workload}: incomplete or timed controller summary")
    if latch.get("first_trigger_observation_layer") != expected_controller["first_trigger_observation_layer"]:
        raise AssertionError(f"{workload}: A4.5.4 latch differs from A4.5.2")
    if latch.get("first_trigger_observation_layer") != source["runtime_validation"]["first_global_latch_layer"]:
        raise AssertionError(f"{workload}: A4.5.4 latch differs from its A4.5.3 source")
    if [item.get("layer") for item in controller.get("activation_observations_by_layer", [])] != list(layers):
        raise AssertionError(f"{workload}: A4.5.4 activation observations are not ordered/complete")
    effective = controller.get("global_effective_cache_position")
    if effective != latch.get("cache_position", -2) + 1:
        raise AssertionError(f"{workload}: A4.5.4 global boundary is not the next decode epoch")
    runtime_local, global_layers, inventories = set(), [], []
    for row in summary.get("layers", []):
        layer = int(row["layer"])
        if row.get("capacity_protection_committed"):
            runtime_local.add(layer)
        event = row.get("request_global_protection_event")
        disposition = row.get("route_a_shadow_state_disposition_event")
        if not row.get("request_global_protection_committed") or not row.get("route_a_shadow_state_tombstoned"):
            raise AssertionError(f"{workload}: layer {layer} lacks global protection or a Route-A shadow tombstone")
        if not isinstance(event, dict) or not isinstance(disposition, dict):
            raise AssertionError(f"{workload}: layer {layer} lacks global/disposition event detail")
        if event.get("boundary") != "next_decode_epoch_after_completion_of_current_activation_epoch" or disposition.get("boundary") != event["boundary"]:
            raise AssertionError(f"{workload}: layer {layer} uses a non-contract disposition boundary")
        if event.get("global_effective_cache_position") != effective or disposition.get("cache_position_of_disposition") != effective:
            raise AssertionError(f"{workload}: layer {layer} tombstone position differs from global boundary")
        if disposition.get("native_full_kv_authoritative_after_disposition") is not True or disposition.get("route_a_shadow_authoritative_after_disposition") is not False:
            raise AssertionError(f"{workload}: layer {layer} authority transition is invalid")
        if disposition.get("route_a_shadow_logically_marked_reclaimable") is not True or disposition.get("route_a_shadow_python_allocator_reclaimed_or_measured") is not False:
            raise AssertionError(f"{workload}: layer {layer} reclamation boundary is mislabeled")
        if disposition.get("post_disposition_route_a_access") != "forbidden_by_tombstone" or disposition.get("reentry_permitted"):
            raise AssertionError(f"{workload}: layer {layer} permits a tombstoned Route-A access or re-entry")
        inventory = disposition.get("logical_inventory_before_tombstone", {})
        heads, totals = inventory.get("per_kv_head", []), inventory.get("totals", {})
        required = ("hot_tokens", "pending_tokens", "packed_tokens", "packed_page_count", "packed_full_page_count", "packed_tail_tokens")
        if inventory.get("route_a_state_next_position") != event.get("route_a_state_next_position_frozen") or row.get("route_a_logical_state_next_position_at_end") != inventory.get("route_a_state_next_position"):
            raise AssertionError(f"{workload}: layer {layer} tombstone position is not frozen exactly once")
        if len(heads) == 0 or any(int(item.get(key, -1)) < 0 for item in heads for key in required):
            raise AssertionError(f"{workload}: layer {layer} inventory is malformed")
        if any(int(totals.get(key, -1)) != sum(int(item[key]) for item in heads) for key in required):
            raise AssertionError(f"{workload}: layer {layer} inventory totals do not equal KV-head rows")
        if int(row.get("request_global_native_attention_calls", 0)) <= 0 or row.get("native_cache_mutated_or_freed"):
            raise AssertionError(f"{workload}: layer {layer} lacks retained native fallback")
        global_layers.append(layer)
        inventories.append(inventory)
    if runtime_local != expected_local or set(global_layers) != set(layers):
        raise AssertionError(f"{workload}: local set or all-layer global coverage differs from A4.5.2/A4.5.3")
    return {
        "runtime_local_protected_layer_indices": sorted(runtime_local),
        "runtime_all_layer_next_epoch_global_protection": True,
        "runtime_all_layer_route_a_shadow_tombstoned": True,
        "first_global_latch_layer": latch["first_trigger_observation_layer"],
        "global_effective_cache_position": effective,
        "tombstone_inventory_layer_count": len(inventories),
        "tombstone_is_not_allocator_measurement": True,
    }


def run_workload(*, workload: str, pipe, args: argparse.Namespace, layers: tuple[int, ...], heads_by_layer: dict[int, int], predictor_revision: str, source_row: dict[str, Any], expected: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    request = build_builtin_request(workload, args.context_repetitions)
    tokens = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids, question_ids = tokens["context_ids"].to(pipe.model.device), tokens["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= 128:
        raise ValueError(f"{workload}: context does not cross the frozen hot window")
    continuation = continuation_for(args.anchor)
    print(f"A4.5.4 {args.anchor}/{workload}: native Full-KV fixed-horizon reference...", flush=True)
    full = continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args)
    assert_no_runtime_mask_state(pipe.model)
    print(f"A4.5.4 {args.anchor}/{workload}: next-epoch fallback with Route-A shadow tombstone...", flush=True)
    backend = ReclaimingGlobalNextEpochCapacityProtectedRouteAPolicyAttentionBackendSet(
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
        raise AssertionError(f"{workload}: tombstone branch did not consume Full-KV fixed token inputs")
    full_digest = token_ids_digest(full["generated_token_ids"])
    if source_row["full_kv_reference"]["generated_token_ids_sha256"] != full_digest:
        raise AssertionError(f"{workload}: A4.5.4 Full-KV reference inputs differ from A4.5.3")
    summary = backend.protected_shadow_state_summary()
    runtime = validate_runtime_summary(summary=summary, source_row=source_row, expected=expected, layers=layers, workload=workload)
    masks = backend.mask_events()
    if set(masks) != set(layers) or any(not masks[layer] for layer in layers):
        raise AssertionError(f"{workload}: predictor journals lack selected layer coverage")
    return {
        "request": {"request_id": request["request_id"], "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}), "context_tokens": int(context_ids.shape[1])},
        "full_kv_reference": {"generated_token_ids_sha256": full_digest, "generated_token_count": len(full["generated_token_ids"])},
        "protected_shadow_state_contract": {
            "forced_reference_token_ids_sha256": full_digest,
            "forced_token_inputs_equal_full_kv": True,
            "a453_source_full_kv_token_ids_sha256": source_row["full_kv_reference"]["generated_token_ids_sha256"],
            "runtime_validation": runtime,
            "runtime_summary": summary,
            "execution_scope": "model-on next-decode-epoch global native fallback with a fail-closed logical Route-A shadow tombstone",
            "no_reentry": True,
            "logical_reclaimability_only": True,
        },
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    fixed = (12, 8, 1, 64, 512, 42, "record_only")
    if (args.context_repetitions, args.fixed_new_tokens, args.deferred_decode_steps, args.page_tokens, args.admission_budget, args.seed, args.execution_dtype_ulp_mode) != fixed or min(args.rtol, args.atol) <= 0:
        raise ValueError("A4.5.4 is fixed to existing 12x/fixed-8/D=1 functional inputs and record-only ULP context")
    a453, a452, a451, expected = read_a453(args.a453_report, anchor=args.anchor)
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
        print(f"A4.5.4 preflight passed: {args.anchor}, three hash-bound A4.5.3 tombstone-source rows; no model loaded.")
        return
    cuda = cuda_environment(require_single_visible_device=True)
    args.output_dir.mkdir(parents=True)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    (args.output_dir / "a454_protected_shadow_state_reclamation_started.json").write_text(json.dumps({"schema_version": SCHEMA, "status": "started", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Loading A4.5.4 {args.anchor} base model: {model_name}", flush=True)
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
    source_rows = a453["per_workload"]
    per_workload = {
        workload: run_workload(workload=workload, pipe=pipe, args=args, layers=layers, heads_by_layer=heads_by_layer, predictor_revision=predictor_revision, source_row=source_rows[workload], expected=expected[workload], output_dir=args.output_dir / workload)
        for workload in WORKLOADS
    }
    report = {
        "schema_version": SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "model-on functional logical Route-A shadow-state tombstone evidence over hash-bound A4.5.3/A4.5.2 contracts; no allocator, measured, or modeled hardware result",
        "provenance": {
            "a453_report_path": str(args.a453_report),
            "a453_report_sha256": sha256_file(args.a453_report),
            "a452_report_sha256": sha256_file(Path(a453["provenance"]["a452_report_path"])),
            "a451_source_report_sha256": sha256_file(Path(a452["input_artifacts"][f"{args.anchor}_a451"]["report_path"])),
            "predictor_revision": predictor_revision,
        },
        "cuda_environment": cuda,
        "model_structure": {"layer_count": len(layers), "kv_head_count_by_layer": {str(layer): heads_by_layer[layer] for layer in layers}},
        "per_workload": per_workload,
        "observational_guards": {
            "single_visible_cuda_device": True,
            "a453_hash_bound_three_workload_source_contract": True,
            "ordered_layer_complete_activation_observations_each_workload": True,
            "runtime_local_protection_set_matches_a452_a453_each_workload": True,
            "all_layers_global_native_fallback_next_epoch_each_workload": True,
            "all_layers_route_a_shadow_tombstoned_each_workload": True,
            "tombstone_inventory_conserves_kv_head_totals_each_workload": True,
            "forced_fixed_token_inputs_equal_full_kv_each_workload": True,
            "native_cache_not_mutated_or_freed_by_backend_each_workload": True,
            "logical_reclaimability_not_allocator_measurement": True,
            "no_hardware_parameter_selected": True,
        },
        "boundaries": [
            "A4.5.4 validates only that the functional Route-A reference state is inaccessible after next-epoch global Full-KV fallback under bounded fixed continuations. Tombstoning is a fail-closed logical ownership guard, not Python allocator behavior or a physical release observation.",
            "The recorded hot/pending/packed/page counts are logical reference-state inventory at the transition. They are not bytes, allocated capacity, HBM/DMA traffic, bursts, FIFO occupancy/capacity, service rate, or overflow evidence.",
            "Forced Full-KV token inputs establish bounded functional continuation inputs only. This gate does not prove arbitrary natural-generation output/quality equivalence, controller timing/broadcast, latency, throughput, energy, area, acceleration, architecture specification, or RTL.",
            "Qwen and Llama reports remain separate. No cross-anchor average, numerical envelope, common hardware contract, or parameter selection is derived.",
        ],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    output = args.output_dir / "a454_protected_shadow_state_reclamation_gate_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.5.4 {args.anchor} protected shadow-state reclamation gate completed: {output}")


if __name__ == "__main__":
    main()
