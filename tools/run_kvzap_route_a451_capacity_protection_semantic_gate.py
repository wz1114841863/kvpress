#!/usr/bin/env python3
"""A4.5.1 model-on, layer-local Route-A capacity-protection semantic gate.

The gate executes a one-way per-layer ``ROUTE_A_ACTIVE -> PROTECTED_FULL_KV``
primitive at a declared *logical* pending watermark.  It retains the model's
native cache and freezes the Route-A reference state before delegating current
and future calls for that layer to native attention.  It is not a request-global
controller, a FIFO sizing study, or a hardware measurement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Transformers and huggingface_hub cache the offline mode during import.  Set
# this before either package is imported so a missing cached auxiliary file
# fails explicitly instead of making an incidental Hub metadata request.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
import transformers
from huggingface_hub import snapshot_download
from transformers import pipeline

from kvpress import KVzapPress
from kvpress.route_a_policy_backend import CapacityProtectedDeferredActivationRouteAPolicyAttentionBackendSet
from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import LLAMA_SCHEMA, QWEN_SCHEMA, sha256_file, validate_anchor
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_llama31_m1_semantic_gate import EXPECTED_STRUCTURE, make_predictor, validate_runtime_structure
from tools.run_kvzap_llama31_m51_fixed_horizon_workload_descriptor import fixed_continuation as llama_fixed_continuation
from tools.run_kvzap_qwen_a441_deferred_activation_gate import fixed_continuation as qwen_fixed_continuation
from tools.run_kvzap_route_a40_policy_gate import cuda_environment
from tools.run_kvzap_trace import DEFAULT_MODEL as QWEN_MODEL, DEFAULT_PREDICTOR as QWEN_PREDICTOR, build_builtin_request
from tools.validate_kvzap_llama31_m0_provenance import DEFAULT_MODEL_REPO as LLAMA_MODEL, DEFAULT_MODEL_REVISION as LLAMA_REVISION, OFFICIAL_PREDICTOR_REPO


SCHEMA = "kvzap-route-a451-capacity-protection-semantic-gate-1.0"
WORKLOADS = ("retrieval", "summarization", "reasoning")
DEFAULT_WATERMARK = 1024


def token_ids_digest(token_ids: list[int]) -> str:
    return hashlib.sha256(",".join(str(token) for token in token_ids).encode("ascii")).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.5.1 model-on layer-local Route-A capacity-protection semantic gate; no FIFO sizing or hardware measurement.")
    parser.add_argument("--anchor", choices=("qwen3_8b", "llama31_8b_instruct"), required=True)
    parser.add_argument("--anchor-report", type=Path, required=True, help="Completed anchor-specific A4.4 report.")
    parser.add_argument("--a450-report", type=Path, required=True, help="Completed A4.5.0 logical boundary replay.")
    parser.add_argument("--predictor-repo-id-override", default=None, help="Required only for the reviewed Llama public predictor repository.")
    parser.add_argument("--pending-high-watermark", type=int, default=DEFAULT_WATERMARK, help="Fixed logical probe point, not a FIFO depth or hardware parameter.")
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
    parser.add_argument("--preflight-only", action="store_true", help="Validate hash-bound inputs and fixed contract without CUDA/model load or output creation.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def read_a450_row(path: Path, *, anchor: str, workload: str, anchor_sha256: str, watermark: int) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "kvzap-route-a450-capacity-protection-boundary-replay-1.0" or value.get("status") != "complete":
        raise ValueError("A4.5.1 requires a completed A4.5.0 boundary replay")
    source = value.get("input_artifacts", {}).get(anchor, {})
    if source.get("report_sha256") != anchor_sha256:
        raise ValueError("A4.5.0 anchor hash does not bind the supplied A4.4 anchor report")
    rows = [row for row in value.get("replay_rows", []) if row.get("anchor") == anchor and row.get("workload") == workload and row.get("policy", {}).get("pending_high_watermark") == watermark]
    if len(rows) != 1 or rows[0].get("transition") is None:
        raise ValueError(f"A4.5.0 has no protection witness for {anchor}/{workload}/C={watermark}")
    return rows[0]


def assert_journal_coverage(mask_events: dict[int, dict[tuple[int, int], Any]], *, layers: tuple[int, ...], heads_by_layer: dict[int, int], label: str) -> None:
    if set(mask_events) != set(layers):
        raise AssertionError(f"{label}: decision journal lacks a selected layer")
    for layer in layers:
        events = mask_events[layer]
        by_head = [sorted(position for head, position in events if head == expected_head) for expected_head in range(heads_by_layer[layer])]
        if any(not positions for positions in by_head):
            raise AssertionError(f"{label}: a KV-head journal is empty")
        reference = by_head[0]
        if reference[0] != 0 or reference != list(range(reference[-1] + 1)) or any(positions != reference for positions in by_head):
            raise AssertionError(f"{label}: journal positions are not layer-head contiguous")


def validate_protection(summary: dict[str, Any], *, layers: tuple[int, ...], watermark: int, workload: str) -> dict[str, Any]:
    rows = summary.get("layers", [])
    if {row.get("layer") for row in rows} != set(layers):
        raise AssertionError(f"{workload}: protection summary lacks layer coverage")
    protected, still_active = [], []
    for row in rows:
        if not row["activation_committed"] or row["activation_event"] is None:
            raise AssertionError(f"{workload}: layer {row['layer']} did not hydrate from the Full-KV prefix")
        if row["native_cache_mutated_or_freed"]:
            raise AssertionError(f"{workload}: backend mutated or freed a native cache")
        event = row["capacity_protection_event"]
        if event is None:
            if row["mode_at_trace_end"] != "route_a_active":
                raise AssertionError(f"{workload}: unprotected layer has an invalid final mode")
            still_active.append(int(row["layer"]))
            continue
        if row["mode_at_trace_end"] != "protected_full_kv" or not row["capacity_protection_committed"]:
            raise AssertionError(f"{workload}: protected layer lacks protected Full-KV mode")
        if event["aggregate_pending_tokens_at_transition"] < watermark or event["reentry_permitted"]:
            raise AssertionError(f"{workload}: protected layer violated its one-way logical boundary")
        if event["native_cache_mutated_or_freed_by_transition"] or event["post_transition_route_a_logical_admission_or_drop"] != "disabled":
            raise AssertionError(f"{workload}: transition claimed native mutation or Route-A continuation")
        if row["protected_native_attention_calls"] <= 0 or row["route_a_logical_state_next_position_at_end"] != event["route_a_state_next_position_frozen"]:
            raise AssertionError(f"{workload}: protected native call or frozen Route-A state guard failed")
        protected.append({"layer": int(row["layer"]), "event": event, "protected_native_attention_calls": int(row["protected_native_attention_calls"])})
    if not protected:
        raise AssertionError(f"{workload}: declared C={watermark} witness did not exercise an actual protected layer")
    return {"protected_layer_count": len(protected), "still_route_a_active_layer_count": len(still_active), "protected_layers": protected, "still_route_a_active_layers": still_active}


def fixed_continuation_for(anchor: str):
    return qwen_fixed_continuation if anchor == "qwen3_8b" else llama_fixed_continuation


def build_predictor(args: argparse.Namespace, *, predictor_revision: str):
    if args.anchor == "qwen3_8b":
        return KVzapPress(model_type="mlp", predictor_revision=predictor_revision)
    return make_predictor(predictor_revision=predictor_revision, override=args.predictor_repo_id_override)


def qwen_kv_head_counts(language_model) -> dict[int, int]:
    """Read Qwen KV-head topology from the version-stable attention config."""
    counts = {
        layer: int(block.self_attn.config.num_key_value_heads)
        for layer, block in enumerate(language_model.layers)
    }
    if not counts or any(count <= 0 for count in counts.values()):
        raise AssertionError("loaded Qwen structure has no Route-A layer/KV-head coverage")
    return counts


def run_workload(*, workload: str, pipe, args: argparse.Namespace, layers: tuple[int, ...], heads_by_layer: dict[int, int], predictor_revision: str, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    request = build_builtin_request(workload, args.context_repetitions)
    tokens = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokens["context_ids"].to(pipe.model.device)
    question_ids = tokens["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= 128:
        raise ValueError(f"{workload}: context must cross the frozen hot window")
    continuation = fixed_continuation_for(args.anchor)
    print(f"A4.5.1 {args.anchor}/{workload}: native Full-KV fixed-horizon reference...", flush=True)
    full = continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args)
    assert_no_runtime_mask_state(pipe.model)
    print(f"A4.5.1 {args.anchor}/{workload}: layer-local capacity-protected continuation...", flush=True)
    backend = CapacityProtectedDeferredActivationRouteAPolicyAttentionBackendSet(
        pipe.model, build_predictor(args, predictor_revision=predictor_revision), layers=layers, kv_head=None,
        threshold=-4.0 if args.anchor == "qwen3_8b" else -7.0, window=128, page_tokens=args.page_tokens,
        admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol,
        max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode=args.execution_dtype_ulp_mode,
        execution_dtype_close_mode="quantization_aware_enforce" if args.anchor == "qwen3_8b" else "off",
        deferred_decode_steps=args.deferred_decode_steps, pending_high_watermark=args.pending_high_watermark,
    )
    protected = continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, backend=backend, forced_token_ids=full["generated_token_ids"])
    assert_no_runtime_mask_state(pipe.model)
    if protected["generated_token_ids"] != full["generated_token_ids"]:
        raise AssertionError(f"{workload}: protected branch did not consume the Full-KV fixed token inputs")
    summary = backend.capacity_protection_summary()
    guard = validate_protection(summary, layers=layers, watermark=args.pending_high_watermark, workload=workload)
    assert_journal_coverage(backend.mask_events(), layers=layers, heads_by_layer=heads_by_layer, label=f"{args.anchor}/{workload}")
    return {
        "request": {"request_id": request["request_id"], "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}), "context_tokens": int(context_ids.shape[1])},
        "full_kv_reference": {"generated_token_ids_sha256": token_ids_digest(full["generated_token_ids"]), "generated_token_count": len(full["generated_token_ids"])},
        "protection_contract": {"forced_reference_token_ids_sha256": token_ids_digest(full["generated_token_ids"]), "forced_token_inputs_equal_full_kv": True, "deferred_activation_summary": summary, "actual_layer_local_protection": guard, "logical_watermark_semantics": "aggregate pending tokens within one layer across its KV heads; a functional probe, not FIFO depth/capacity", "execution_scope": "layer-local attention-hook primitive; not a request-global controller", "native_full_kv_authoritative_after_protection": True, "post_protection_route_a_state_frozen": True, "reentry_permitted": False},
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    fixed = (DEFAULT_WATERMARK, 12, 8, 1, 64, 512, 42, "record_only")
    if (args.pending_high_watermark, args.context_repetitions, args.fixed_new_tokens, args.deferred_decode_steps, args.page_tokens, args.admission_budget, args.seed, args.execution_dtype_ulp_mode) != fixed or min(args.rtol, args.atol) <= 0:
        raise ValueError("A4.5.1 is fixed to C=1024, existing 12x/fixed-8/D=1 functional inputs, and record-only ULP context")
    if args.anchor == "qwen3_8b":
        expected_schema, model_name, model_revision, predictor_revision = QWEN_SCHEMA, QWEN_MODEL, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION
        if args.predictor_repo_id_override is not None:
            raise ValueError("Qwen must retain the default predictor derivation without an override")
    else:
        expected_schema, model_name, model_revision = LLAMA_SCHEMA, LLAMA_MODEL, LLAMA_REVISION
        if args.predictor_repo_id_override != OFFICIAL_PREDICTOR_REPO:
            raise ValueError("Llama requires the reviewed explicit official predictor repository override")
        raw_anchor = json.loads(args.anchor_report.read_text(encoding="utf-8"))
        predictor_revision = str(raw_anchor.get("provenance", {}).get("predictor_revision", ""))
        if not predictor_revision:
            raise ValueError("Llama A4.4 report lacks predictor revision provenance")
    anchor = validate_anchor(path=args.anchor_report, expected_schema=expected_schema, anchor=args.anchor)
    anchor_sha256 = sha256_file(args.anchor_report)
    for workload in WORKLOADS:
        read_a450_row(args.a450_report, anchor=args.anchor, workload=workload, anchor_sha256=anchor_sha256, watermark=args.pending_high_watermark)
    if args.preflight_only:
        print(f"A4.5.1 preflight passed: {args.anchor}, three hash-bound C={args.pending_high_watermark} A4.5.0 witnesses; no model loaded.")
        return
    cuda = cuda_environment(require_single_visible_device=True)
    args.output_dir.mkdir(parents=True)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    started = {"schema_version": SCHEMA, "status": "started", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "boundaries": ["A4.5.1 is a layer-local functional primitive, not A4.5.0's request-global control-plane replay.", "C=1024 is a logical probe point bound to A4.5.0, not a FIFO depth, capacity selection, or hardware parameter."]}
    (args.output_dir / "a451_capacity_protection_started.json").write_text(json.dumps(started, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Loading A4.5.1 {args.anchor} base model: {model_name}", flush=True)
    pipe = pipeline("kv-press-text-generation", model=model_name, revision=model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != model_revision:
        raise AssertionError("loaded model revision differs from anchor provenance")
    if args.anchor == "qwen3_8b":
        language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
        layers = tuple(range(len(language_model.layers)))
        heads_by_layer = qwen_kv_head_counts(language_model)
    else:
        layer_count, head_count = validate_runtime_structure(pipe.model)
        if (layer_count, head_count) != (EXPECTED_STRUCTURE["layer_count"], EXPECTED_STRUCTURE["kv_head_count"]):
            raise AssertionError("loaded Llama dimensions differ from accepted provenance")
        snapshot = Path(snapshot_download(repo_id=OFFICIAL_PREDICTOR_REPO, revision=predictor_revision))
        if snapshot.name != predictor_revision:
            raise AssertionError("resolved Llama predictor snapshot differs from the A4.4 source")
        layers, heads_by_layer = tuple(range(layer_count)), {layer: head_count for layer in range(layer_count)}
    per_workload = {workload: run_workload(workload=workload, pipe=pipe, args=args, layers=layers, heads_by_layer=heads_by_layer, predictor_revision=predictor_revision, output_dir=args.output_dir / workload) for workload in WORKLOADS}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "model-on functional semantic evidence for a layer-local fallback primitive; no measured or modeled hardware result", "provenance": {"anchor_report_path": str(args.anchor_report), "anchor_report_sha256": anchor_sha256, "anchor_report_schema": anchor["report_schema"], "a450_report_path": str(args.a450_report), "a450_report_sha256": sha256_file(args.a450_report), "predictor_revision": predictor_revision}, "cuda_environment": cuda, "model_structure": {"layer_count": len(layers), "kv_head_count_by_layer": {str(layer): heads_by_layer[layer] for layer in layers}}, "per_workload": per_workload, "observational_guards": {"single_visible_cuda_device": True, "a450_c1024_witness_hash_bound_for_each_workload": True, "all_layers_all_kv_heads_predictor_journaled_each_workload": True, "at_least_one_actual_layer_local_protection_transition_each_workload": True, "native_full_kv_called_after_protection_each_workload": True, "route_a_state_frozen_after_protection_each_workload": True, "one_way_no_reentry_each_workload": True, "forced_fixed_token_inputs_equal_full_kv_each_workload": True, "native_cache_not_mutated_or_freed_by_backend_each_workload": True, "no_hardware_parameter_selected": True}, "boundaries": ["A4.5.1 validates a layer-local executable protection primitive only. It does not implement or validate a request-global controller, controller look-ahead, synchronization, within-append transient avoidance, or re-entry policy beyond its one-way local reference state.", "C=1024 is an A4.5.0-bound logical pending probe. It is not a measured FIFO depth/capacity, overflow threshold, service rate, page/bank/burst choice, controller timing, or hardware parameter.", "Forced Full-KV token inputs establish the declared functional continuation inputs, not a claim that protected execution preserves arbitrary natural generation outputs or quality.", "This gate does not measure allocator behavior, native memory reclamation, physical capacity, HBM/DMA traffic, bursts, timing, latency, throughput, energy, area, acceleration, architecture specification, or RTL. Qwen and Llama reports remain separate and cannot derive a pooled hardware envelope."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    output = args.output_dir / "a451_capacity_protection_semantic_gate_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.5.1 {args.anchor} capacity-protection semantic gate completed: {output}")


if __name__ == "__main__":
    main()
