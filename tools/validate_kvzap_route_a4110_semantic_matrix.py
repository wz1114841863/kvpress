#!/usr/bin/env python3
"""Validate A4.11.0's trace-off, three-workload Route-A semantic matrix.

This tool deliberately consumes completed policy-on manifests.  It never loads
a model, times an operation, records lifecycle transitions, or changes the
A4.10 declared queue/control parameters.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash
from tools.simulate_kvzap_route_a410_queue_contract import SCHEMA as A410_SCHEMA


SCHEMA = "kvzap-route-a4110-trace-off-semantic-matrix-1.0"
POLICY_SCHEMA = "kvzap-route-a40-policy-on-qwen-gate-1.5"
WORKLOADS = ("retrieval", "summarization", "reasoning")
A410_GUARDS = (
    "a492_record_granular_execution_fixed_without_new_variant",
    "ha8_wide_primary_and_ha8_base_control_only",
    "transaction_fifo_ownership_and_single_commit_boundary_unchanged",
    "lossless_credit_only_delays_transactions_without_drop_or_reorder",
    "queue_overflow_reference_and_finite_credit_staging_both_reported",
    "no_model_default_pruning_path_or_hardware_measurement_loaded",
)
STABLE_POLICY_FIELDS = (
    "model_name", "model_revision", "predictor_name", "predictor_revision",
    "threshold", "window_size", "page_tokens", "admission_budget",
    "context_repetitions", "max_new_tokens", "seed", "rtol", "atol",
    "max_executed_dtype_ulps", "target_layers", "target_kv_head",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.11.0 trace-off semantic-matrix validator; no model, timing, allocator, or trace-on control-event run."
    )
    parser.add_argument("--a410-report", type=Path, required=True)
    for workload in WORKLOADS:
        parser.add_argument(f"--{workload}-manifest", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate all immutable inputs without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return payload


def validate_a410(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("schema_version") != A410_SCHEMA or report.get("status") != "complete":
        raise ValueError("A4.10 report is not a completed compatible contract")
    if not all(report.get("semantic_guards", {}).get(name) is True for name in A410_GUARDS):
        raise ValueError("A4.10 semantic guards are incomplete")
    config = report.get("config", {})
    expected = {
        "fixed_execution": "A4.9.2 record-granular only",
        "candidates": ["ha8_base", "ha8_wide"],
        "local_capacity_per_bank": 32,
        "shared_capacity_per_layer": 256,
        "staging_capacity_per_layer": 512,
        "queue_reference_word_bits": 64,
    }
    if any(config.get(name) != value for name, value in expected.items()):
        raise ValueError("A4.10 queue/control configuration differs from the fixed contract")
    return expected


def required_trace_off_config(config: dict[str, Any], workload: str) -> None:
    if config.get("preset") != workload or config.get("input_jsonl") is not None:
        raise ValueError(f"{workload}: A4.11.0 requires the named built-in preset")
    if config.get("target_layers") != ["all"] or config.get("target_kv_head") != "all":
        raise ValueError(f"{workload}: A4.11.0 requires all layers and all KV heads")
    if config.get("with_same_mask_dense_baseline") is not True or config.get("replay_dense_mask_for_route_a") is not True:
        raise ValueError(f"{workload}: A4.11.0 requires the replayed same-mask dense pairing")
    if config.get("record_lifecycle_transitions", False) or config.get("prefill_maturity_chunk_tokens", 0):
        raise ValueError(f"{workload}: A4.11.0 accepts trace-off manifests only")
    if config.get("require_pending_nonempty") is not True:
        raise ValueError(f"{workload}: A4.11.0 requires a pending-staging witness")


def validate_policy_manifest(manifest: dict[str, Any], workload: str) -> dict[str, Any]:
    if manifest.get("schema_version") != POLICY_SCHEMA:
        raise ValueError(f"{workload}: expected {POLICY_SCHEMA}")
    config = manifest.get("config")
    if not isinstance(config, dict):
        raise ValueError(f"{workload}: policy config is missing")
    required_trace_off_config(config, workload)
    guards = manifest.get("observational_guards", {})
    expected_guards = {
        "selected_head_original_attention_called_during_policy_decode": False,
        "route_a_mask_source": "replayed_dense_mask",
        "replay_mask_consumption_complete": True,
        "lifecycle_transition_trace_enabled": False,
        "prefill_micro_event_trace_enabled": False,
        "dms_press_used": False,
        "masked_key_indices_created": False,
        "fake_key_attention_used": False,
        "model_cache_mutated_by_backend": False,
    }
    if any(guards.get(name) != value for name, value in expected_guards.items()):
        raise ValueError(f"{workload}: trace-off Route-A guards are incomplete")
    dense = manifest.get("same_mask_dense_kvzap")
    if not isinstance(dense, dict) or dense.get("pairing_mode") != "replayed_dense_mask" or dense.get("original_mask_digest_matches_route_a") is not True:
        raise ValueError(f"{workload}: same-mask dense control is absent or not paired")
    coverage = manifest.get("policy_coverage", {})
    dense_coverage = dense.get("policy_coverage", {})
    route_layers = coverage.get("layers", [])
    dense_layers = dense_coverage.get("layers", [])
    resolved = config.get("resolved_target_layers")
    if not isinstance(resolved, list) or not resolved or [row.get("layer") for row in route_layers] != resolved or [row.get("layer") for row in dense_layers] != resolved:
        raise ValueError(f"{workload}: all-layer coverage is incomplete")
    route_calls = manifest.get("policy_decode_call_count_by_layer", {})
    dense_calls = dense.get("policy_decode_call_count_by_layer", {})
    pending_seen = False
    for route, dense_row in zip(route_layers, dense_layers):
        if route.get("selected_kv_heads") != dense_row.get("selected_kv_heads") or route.get("original_mask_sha256") != dense_row.get("original_mask_sha256") or route.get("original_mask_decision_count") != dense_row.get("original_mask_decision_count"):
            raise ValueError(f"{workload}: dense and Route-A layer mask summaries differ")
        heads = route.get("heads", [])
        if not heads or [head.get("kv_head") for head in heads] != route.get("selected_kv_heads"):
            raise ValueError(f"{workload}: selected KV-head coverage is incomplete")
        if any(int(head.get("comparison_count", 0)) <= 0 for head in heads):
            raise ValueError(f"{workload}: a selected KV head has no numerical comparison")
        pending_seen = pending_seen or any(int(head.get("max_pending_tokens", 0)) > 0 for head in heads)
        layer = route["layer"]
        if int(route_calls.get(str(layer), route_calls.get(layer, 0))) <= 0 or int(dense_calls.get(str(layer), dense_calls.get(layer, 0))) <= 0:
            raise ValueError(f"{workload}: a selected layer has no policy decode call")
    if not pending_seen or not manifest.get("comparisons") or not dense.get("comparisons"):
        raise ValueError(f"{workload}: pending or numerical-comparison coverage is absent")
    answer_fields = ("full_kv_bypass_answer_sha256", "route_a_fast_path_answer_sha256")
    answers = {name: manifest.get(name) for name in answer_fields}
    answers["same_mask_dense_kvzap_answer_sha256"] = dense.get("answer_sha256")
    if any(not isinstance(value, str) or len(value) != 64 for value in answers.values()):
        raise ValueError(f"{workload}: one of the three path answer digests is invalid")
    return {
        "request_id": manifest.get("request_id"),
        "request_content_hash": manifest.get("request_content_hash"),
        "stable_config": {name: config.get(name) for name in STABLE_POLICY_FIELDS},
        "resolved_target_layers": resolved,
        "selected_kv_head_count": sum(len(row["selected_kv_heads"]) for row in route_layers),
        "route_a_comparison_count": len(manifest["comparisons"]),
        "same_mask_dense_comparison_count": len(dense["comparisons"]),
        "three_path_answer_sha256": answers,
        "answers_equal_to_full_kv": {
            "same_mask_dense": dense.get("answers_identical_to_full_kv"),
            "route_a": manifest.get("answers_identical"),
        },
    }


def validate_inputs(args: argparse.Namespace) -> dict[str, Any]:
    a410 = read_json(args.a410_report, "A4.10 report")
    a410_config = validate_a410(a410)
    rows = []
    stable_config = None
    for workload in WORKLOADS:
        path = getattr(args, f"{workload}_manifest")
        manifest = read_json(path, f"{workload} policy manifest")
        summary = validate_policy_manifest(manifest, workload)
        if stable_config is None:
            stable_config = summary["stable_config"]
        elif summary["stable_config"] != stable_config:
            raise ValueError(f"{workload}: semantic configuration differs from the other workloads")
        rows.append({"workload": workload, "manifest": str(path), "manifest_sha256": sha256_file(path), **summary})
    return {"a410": {"report": str(args.a410_report), "report_sha256": sha256_file(args.a410_report), "fixed_config": a410_config}, "stable_policy_config": stable_config, "workloads": rows}


def main() -> None:
    args = parse_args()
    checked = validate_inputs(args)
    if args.preflight_only:
        print("A4.11.0 preflight passed: A4.10 contract and all trace-off three-path semantic manifests validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    config = {"stage": "A4.11.0", "workloads": list(WORKLOADS), "execution": "trace-off replayed-mask three-path semantics only", "a410_contract": checked["a410"]["fixed_config"]}
    report = {
        "schema_version": SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "input_artifacts": checked,
        "semantic_guards": {
            "a410_record_granular_ha8_contract_is_hash_bound_and_unchanged": True,
            "full_kv_bypass_same_mask_dense_and_route_a_packed_paths_present": True,
            "dense_to_route_a_mask_replay_is_exact_for_every_selected_layer_and_kv_head": True,
            "selected_route_a_attention_never_calls_original_dense_attention": True,
            "pending_staging_and_numerical_comparisons_are_observed_per_workload": True,
            "trace_off_only_no_timing_allocator_or_control_event_observation": True,
            "full_kv_answer_equality_is_recorded_not_required": True,
        },
        "boundaries": [
            "This is a functional trace-off semantic matrix, not a performance, allocator, HBM, queue-depth, credit-latency, throughput, area, energy, architecture, or RTL result.",
            "A4.10 parameters are hash-bound context only; this matrix neither calibrates nor changes its declared queue/control model.",
            "The next trace-off timing run and trace-on control-event run must use new outputs and remain separate from this semantic gate.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a4110_trace_off_semantic_matrix_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.11.0 complete: {path} sha256={sha256_file(path)} workloads={len(WORKLOADS)}")


if __name__ == "__main__":
    main()
