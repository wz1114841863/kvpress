#!/usr/bin/env python3
"""Validate and summarize A4.11.1 trace-off three-path software measurements."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash
from tools.validate_kvzap_route_a4110_semantic_matrix import SCHEMA as A4110_SCHEMA, WORKLOADS


SCHEMA = "kvzap-route-a4111-trace-off-measurement-matrix-1.0"
MEASUREMENT_SCHEMA = "kvzap-route-a4147-qwen-external-storage-whole-decode-measurement-1.0"
PATHS = ("full_kv_bypass", "same_mask_dense_replay", "same_mask_route_a_external_storage_replay")
STABLE_FIELDS = (
    "model_name", "model_revision", "predictor_name", "predictor_revision",
    "threshold", "window_size", "page_tokens", "admission_budget",
    "context_repetitions", "max_new_tokens", "seed", "rtol", "atol",
    "max_executed_dtype_ulps", "target_layers", "target_kv_head",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.11.1 trace-off measurement-matrix validator; summarizes Python software timing and allocator observations only."
    )
    parser.add_argument("--a4110-report", type=Path, required=True)
    for workload in WORKLOADS:
        parser.add_argument(f"--{workload}-measurement", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate semantic and measurement inputs without creating output.")
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


def validate_a4110(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("schema_version") != A4110_SCHEMA or report.get("status") != "complete":
        raise ValueError("A4.11.0 semantic matrix is incomplete or incompatible")
    guards = report.get("semantic_guards", {})
    required = (
        "a410_record_granular_ha8_contract_is_hash_bound_and_unchanged",
        "full_kv_bypass_same_mask_dense_and_route_a_packed_paths_present",
        "dense_to_route_a_mask_replay_is_exact_for_every_selected_layer_and_kv_head",
        "selected_route_a_attention_never_calls_original_dense_attention",
        "pending_staging_and_numerical_comparisons_are_observed_per_workload",
        "trace_off_only_no_timing_allocator_or_control_event_observation",
    )
    if not all(guards.get(name) is True for name in required):
        raise ValueError("A4.11.0 semantic guards are incomplete")
    policy = report.get("input_artifacts", {}).get("stable_policy_config")
    if not isinstance(policy, dict) or any(name not in policy for name in STABLE_FIELDS):
        raise ValueError("A4.11.0 stable semantic configuration is incomplete")
    if policy.get("admission_budget") != 512 or policy.get("target_layers") != ["all"] or policy.get("target_kv_head") != "all":
        raise ValueError("A4.11.1 is bounded to the A4.11.0 all-layer/all-head budget-512 semantic configuration")
    return policy


def aggregate_groups(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = summary.get("reset_run_aggregate_groups", [])
    by_path = {row.get("path"): row for row in rows}
    if set(by_path) != set(PATHS):
        raise ValueError("measurement lacks one of the three required reset-run paths")
    for path, row in by_path.items():
        if row.get("reported_reset_runs", 0) <= 0 or row.get("callback_count_per_reset_run", {}).get("median") != 1.0:
            raise ValueError(f"{path}: measurement does not have one timed region per reported reset run")
        for metric in ("wall_ms_sum_per_reset_run", "cuda_event_ms_sum_per_reset_run", "peak_allocated_bytes_max_per_reset_run", "peak_reserved_bytes_max_per_reset_run"):
            if not isinstance(row.get(metric, {}).get("median"), (int, float)):
                raise ValueError(f"{path}: missing {metric} median")
    return by_path


def generated_outputs(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = summary.get("whole_decode_generated_tokens", [])
    by_path = {row.get("path"): row for row in rows}
    if set(by_path) != set(PATHS):
        raise ValueError("measurement lacks generated-output rows for the three paths")
    for path, row in by_path.items():
        if row.get("reported_reset_runs", 0) <= 0 or len(row.get("generated_token_ids_sha256_values", [])) != 1 or len(row.get("answer_sha256_values", [])) != 1:
            raise ValueError(f"{path}: generated outputs are not stable across reported reset runs")
    if by_path["same_mask_dense_replay"]["generated_token_ids_sha256_values"] != by_path["same_mask_route_a_external_storage_replay"]["generated_token_ids_sha256_values"]:
        raise ValueError("same-mask dense and Route-A external-storage token digests differ")
    return by_path


def ratio(numerator: float, denominator: float) -> float | None:
    return None if denominator == 0 else numerator / denominator


def validate_measurement(manifest: dict[str, Any], workload: str, semantic_config: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != MEASUREMENT_SCHEMA or manifest.get("status") != "complete":
        raise ValueError(f"{workload}: measurement is incomplete or incompatible")
    config = manifest.get("config", {})
    if config.get("preset") != workload or config.get("input_jsonl") is not None:
        raise ValueError(f"{workload}: measurement must use the named built-in preset")
    if any(config.get(name) != semantic_config[name] for name in STABLE_FIELDS):
        raise ValueError(f"{workload}: measurement configuration differs from A4.11.0 semantics")
    guards = manifest.get("observational_guards", {})
    required = (
        "paired_mask_mode", "full_kv_bypass_zero_route_a_admission",
        "replay_mask_consumption_complete",
        "all_layers_all_kv_heads_external_storage_substituted",
        "persistent_selected_native_cold_absent",
        "required_any_full_multi_tail_packed_coverage",
        "one_timed_region_per_reset_run",
    )
    if guards.get("paired_mask_mode") != "replayed_dense_mask" or any(guards.get(name) is not True for name in required[1:]):
        raise ValueError(f"{workload}: external-storage measurement guards are incomplete")
    summary = manifest.get("summary", {})
    groups = aggregate_groups(summary)
    outputs = generated_outputs(summary)
    raw_path = summary.get("raw_path")
    if not isinstance(raw_path, str) or not (Path(raw_path).is_absolute() or raw_path):
        raise ValueError(f"{workload}: raw repetition path is invalid")
    dense = groups["same_mask_dense_replay"]
    route = groups["same_mask_route_a_external_storage_replay"]
    def metrics(row: dict[str, Any]) -> dict[str, float]:
        return {
            "wall_ms_median": float(row["wall_ms_sum_per_reset_run"]["median"]),
            "cuda_event_ms_median": float(row["cuda_event_ms_sum_per_reset_run"]["median"]),
            "peak_allocated_bytes_median": float(row["peak_allocated_bytes_max_per_reset_run"]["median"]),
            "peak_reserved_bytes_median": float(row["peak_reserved_bytes_max_per_reset_run"]["median"]),
        }
    by_path = {path: metrics(groups[path]) for path in PATHS}
    return {
        "measurement_request_id": manifest.get("request_id"),
        "measurement_request_content_hash": manifest.get("request_content_hash"),
        "replay_event_file_sha256": manifest.get("replay_source", {}).get("event_file_sha256"),
        "raw_repetitions_path": raw_path,
        "reported_reset_runs_per_path": {path: int(groups[path]["reported_reset_runs"]) for path in PATHS},
        "path_medians": by_path,
        "same_mask_dense_route_a_token_digest_equal": True,
        "full_kv_route_a_token_digest_equal": outputs["full_kv_bypass"]["generated_token_ids_sha256_values"] == outputs["same_mask_route_a_external_storage_replay"]["generated_token_ids_sha256_values"],
        "route_a_vs_dense_median_ratio": {
            "wall_ms": ratio(by_path["same_mask_route_a_external_storage_replay"]["wall_ms_median"], by_path["same_mask_dense_replay"]["wall_ms_median"]),
            "cuda_event_ms": ratio(by_path["same_mask_route_a_external_storage_replay"]["cuda_event_ms_median"], by_path["same_mask_dense_replay"]["cuda_event_ms_median"]),
            "peak_allocated_bytes": ratio(by_path["same_mask_route_a_external_storage_replay"]["peak_allocated_bytes_median"], by_path["same_mask_dense_replay"]["peak_allocated_bytes_median"]),
            "peak_reserved_bytes": ratio(by_path["same_mask_route_a_external_storage_replay"]["peak_reserved_bytes_median"], by_path["same_mask_dense_replay"]["peak_reserved_bytes_median"]),
        },
    }


def validate_inputs(args: argparse.Namespace) -> dict[str, Any]:
    semantic = read_json(args.a4110_report, "A4.11.0 report")
    policy = validate_a4110(semantic)
    rows = []
    for workload in WORKLOADS:
        path = getattr(args, f"{workload}_measurement")
        measurement = read_json(path, f"{workload} measurement")
        rows.append({"workload": workload, "measurement": str(path), "measurement_sha256": sha256_file(path), **validate_measurement(measurement, workload, policy)})
    return {"semantic_report": str(args.a4110_report), "semantic_report_sha256": sha256_file(args.a4110_report), "stable_policy_config": policy, "workloads": rows}


def main() -> None:
    args = parse_args()
    checked = validate_inputs(args)
    if args.preflight_only:
        print("A4.11.1 preflight passed: completed A4.11.0 semantics and all trace-off three-path measurements validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    config = {"stage": "A4.11.1", "workloads": list(WORKLOADS), "measurement": "trace-off repeated external-storage three-path Python-reference software observation"}
    report = {
        "schema_version": SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "input_artifacts": checked,
        "observational_guards": {
            "a4110_trace_off_semantics_verified_before_measurement": True,
            "full_kv_bypass_same_mask_dense_and_external_route_a_paths_measured": True,
            "same_mask_dense_and_external_route_a_generated_tokens_equal": True,
            "all_layers_all_kv_heads_external_storage_and_replay_consumption_verified": True,
            "one_timed_region_and_run_local_allocator_peak_per_reset_run": True,
            "a410_parameters_not_changed_or_calibrated_by_measurement": True,
        },
        "boundaries": [
            "Wall time, CUDA-event time, and PyTorch allocator bytes are Python-reference software observations, not HBM traffic, throughput, energy, area, frequency, hardware acceleration, or RTL evidence.",
            "Full-KV bypass is an explicit independent control; its output relation is recorded, not required. Dense and Route-A equality is required only for their paired replayed mask.",
            "This trace-off measurement does not validate queue arrival/ready/done/commit timing, credit latency, or an A4.10 hardware calibration; those belong to the later trace-on control-event stage.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a4111_trace_off_measurement_matrix_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.11.1 complete: {path} sha256={sha256_file(path)} workloads={len(WORKLOADS)}")


if __name__ == "__main__":
    main()
