#!/usr/bin/env python3
"""No-model diagnosis of recorded M4 summarization execution-dtype ULP breaches.

ULP values are interpreted only alongside their scalar absolute values and the
declared software numerical tolerances.  This tool neither changes a numerical
guard nor derives a hardware merge-precision choice.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


M2_SCHEMA = "kvzap-llama31-m2-lifecycle-gate-1.0"
M4_SCHEMA = "kvzap-llama31-m4-bounded-workload-envelope-1.0"
M41_SCHEMA = "kvzap-llama31-m41-summarization-ulp-diagnostic-1.0"
POINTS = ("pending_budget_one", "packed_budget_512")
WORKLOADS = ("retrieval", "summarization", "reasoning")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_completed(path: Path, schema: str, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != schema or value.get("status") != "complete":
        raise ValueError(f"{label} is not a completed {schema} artifact")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M4.1 no-model summarization ULP diagnostic; not a precision-selection or hardware study."
    )
    parser.add_argument("--m4-report", type=Path, required=True)
    parser.add_argument("--retrieval-m2-manifest", type=Path, required=True)
    parser.add_argument("--summarization-m2-manifest", type=Path, required=True)
    parser.add_argument("--reasoning-m2-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def validate_record_only_m2(value: dict[str, Any], *, workload: str) -> None:
    config, request, guards = value.get("config"), value.get("request"), value.get("observational_guards")
    if not isinstance(config, dict) or not isinstance(request, dict) or not isinstance(guards, dict):
        raise ValueError(f"{workload} M2 lacks config/request/guard sections")
    if request.get("request_id") != f"builtin_{workload}_trace":
        raise ValueError(f"{workload} M2 request does not match the bounded M4 matrix")
    if config.get("execution_dtype_ulp_mode") != "record_only" or config.get("same_mask_numerical_guard_mode", "enforce") != "enforce":
        raise ValueError(f"{workload} M2 is not an explicit record-only ULP diagnostic with same-mask guard enforcement")
    required_true = (
        "all_32_layers_and_all_8_kv_heads_covered_at_both_points",
        "online_dense_events_replayed_exactly_once_at_both_points",
        "same_mask_fp32_and_executed_dtype_guards_executed_at_both_points",
        "same_mask_numerical_guard_remained_enforced",
        "budget_one_hot_pending_packed_observed",
        "budget_512_full_multi_tail_page_witness",
        "model_cache_mutated_by_backend",
        "route_a_predictor_scored_online",
    )
    if any(guards.get(name) is not True for name in required_true[:-2]):
        raise ValueError(f"{workload} M2 lacks required true functional guard")
    if guards["model_cache_mutated_by_backend"] is not False or guards["route_a_predictor_scored_online"] is not False:
        raise ValueError(f"{workload} M2 violates native-cache or replay-only boundary")


def summarize_route_breaches(manifest: dict[str, Any], *, atol: float) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for point_name in POINTS:
        summary = manifest["outcomes"][point_name]["replayed_same_mask_route_a"]["execution_dtype_ulp_breach_summary"]
        for layer_summary in summary["layers"]:
            for sample in layer_summary["samples"]:
                if sample["max_executed_dtype_ulps"] <= sample["executed_dtype_ulp_limit"]:
                    raise ValueError("recorded ULP sample does not exceed its declared limit")
                rows.append({"reference_point": point_name, "route_layer": layer_summary["layer"], **sample})
    location_counts = Counter(
        (row["route_layer"], row["kv_head"], row["query_head"], row["cache_position"])
        for row in rows
    )
    annotated = []
    for row in rows:
        item = dict(row)
        item["max_fp32_abs_difference_within_declared_atol"] = float(row["max_fp32_abs_difference"]) <= atol
        item["dense_value_magnitude_below_declared_atol"] = abs(float(row["dense_fp32_value_at_max_ulp"])) < atol
        item["route_value_magnitude_below_declared_atol"] = abs(float(row["route_fp32_value_at_max_ulp"])) < atol
        item["same_location_occurrences_across_reference_points"] = location_counts[(row["route_layer"], row["kv_head"], row["query_head"], row["cache_position"])]
        annotated.append(item)
    return {
        "recorded_breach_occurrence_count": len(annotated),
        "unique_location_count": len(location_counts),
        "all_finite": all(not bool(row["max_executed_dtype_ulps_is_infinite"]) for row in annotated),
        "max_recorded_ulps": max((float(row["max_executed_dtype_ulps"]) for row in annotated), default=0.0),
        "max_recorded_fp32_abs_difference": max((float(row["max_fp32_abs_difference"]) for row in annotated), default=0.0),
        "all_recorded_fp32_maxima_within_declared_atol": all(row["max_fp32_abs_difference_within_declared_atol"] for row in annotated),
        "all_sample_values_below_declared_atol_magnitude": all(row["dense_value_magnitude_below_declared_atol"] and row["route_value_magnitude_below_declared_atol"] for row in annotated),
        "samples": annotated,
    }


def total_route_breach_count(manifest: dict[str, Any]) -> int:
    return sum(
        int(layer["breach_count"])
        for point_name in POINTS
        for layer in manifest["outcomes"][point_name]["replayed_same_mask_route_a"]["execution_dtype_ulp_breach_summary"]["layers"]
    )


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    m4 = load_completed(args.m4_report, M4_SCHEMA, label="M4 report")
    m2_paths = {
        "retrieval": args.retrieval_m2_manifest,
        "summarization": args.summarization_m2_manifest,
        "reasoning": args.reasoning_m2_manifest,
    }
    m2 = {
        workload: load_completed(path, M2_SCHEMA, label=f"{workload} M2 manifest")
        for workload, path in m2_paths.items()
    }
    for workload in WORKLOADS:
        validate_record_only_m2(m2[workload], workload=workload)
        m4_entry = m4["config"][workload]
        if m4_entry.get("sha256") != sha256_file(m2_paths[workload]):
            raise ValueError(f"M4 does not bind supplied {workload} M2 manifest")
    if not all(m4.get("observational_guards", {}).values()):
        raise ValueError("M4 report has an incomplete observational guard")
    atol = float(m2["summarization"]["config"]["atol"])
    breach_summary = summarize_route_breaches(m2["summarization"], atol=atol)
    comparator_counts = {
        workload: total_route_breach_count(m2[workload])
        for workload in ("retrieval", "reasoning")
    }
    config = {
        "m4_report": {"path": str(args.m4_report), "sha256": sha256_file(args.m4_report)},
        **{workload: {"path": str(path), "sha256": sha256_file(path)} for workload, path in m2_paths.items()},
    }
    report = {
        "schema_version": M41_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model hash-bound diagnostic of recorded software execution-dtype scalar breaches; not modeled or measured hardware evidence",
        "strict_failure_context": {
            "strict_executed_dtype_ulp_limit": m2["summarization"]["config"]["max_executed_dtype_ulps"],
            "record_only_mode": True,
            "same_mask_numerical_guard_mode": m2["summarization"]["config"].get("same_mask_numerical_guard_mode", "enforce"),
            "declared_fp32_atol": atol,
            "declared_fp32_rtol": m2["summarization"]["config"]["rtol"],
        },
        "summarization_route_a_ulp_diagnostic": breach_summary,
        "other_fixed_workload_route_a_breach_occurrence_counts": comparator_counts,
        "m41_decision": {
            "strict_16_ulp_contract_for_summarization": "not passed; recorded breaches remain explicit",
            "fp32_guard_observation": "all recorded breach samples have maximum FP32 absolute difference within the declared atol",
            "near_zero_interpretation": "all recorded sample values are below the declared atol magnitude, so ULP count must be read with local scalar spacing and not alone",
            "hardware_precision_or_merge_choice_selected": False,
            "next_scope": "If stricter numerical portability is required, separately test a predeclared software numerical contract; do not infer a hardware precision from M4.1.",
        },
        "observational_guards": {
            "m4_hashes_and_guards_verified": True,
            "all_three_m2_inputs_record_only_with_same_mask_guard_enforced": True,
            "summarization_breach_samples_bound_and_validated": True,
            "retrieval_and_reasoning_zero_recorded_route_a_breaches": comparator_counts == {"retrieval": 0, "reasoning": 0},
            "no_model_runtime_loaded": True,
            "no_hardware_parameter_selected": True,
        },
        "boundaries": [
            "M4.1 does not turn a record-only run into a strict 16-ULP numerical pass.",
            "Small absolute differences or near-zero values are software diagnostic context, not a proof of generation accuracy, merge precision sufficiency, or hardware robustness.",
            "No field is capacity, HBM traffic, latency, throughput, energy, area, hardware acceleration, architecture specification, or RTL evidence.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "llama31_m41_summarization_ulp_diagnostic_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"M4.1 summarization ULP diagnostic completed: {output}")


if __name__ == "__main__":
    main()
