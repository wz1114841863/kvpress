#!/usr/bin/env python3
"""M6 no-model, fixed-horizon Qwen/Llama descriptor-envelope comparison.

This tool is intentionally a *coverage* summary, not a hardware sizing tool.
It keeps Qwen and Llama workload rows separate, then reports the observed
minimum/maximum of already-normalized logical descriptor fields.  Absolute
event counts, layer counts, and model-specific predictor thresholds are never
pooled into a resource requirement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


M6_SCHEMA = "kvzap-route-a-m6-cross-model-fixed-horizon-envelope-1.0"
QWEN_CORE_SCHEMA = "kvzap-route-a4214-core-contract-closure-1.0"
QWEN_A428_SCHEMA = "kvzap-route-a428-matched-horizon-workload-stability-1.0"
LLAMA_M51_SCHEMA = "kvzap-llama31-m51-fixed-horizon-workload-descriptor-1.1"
SOURCES = ("hot", "pending", "packed")
FAN_IN_KEYS = ("1_active_sources", "2_active_sources", "3_active_sources")
TAIL_KEYS = ("p50", "p95", "max", "tail_p50", "tail_p95", "tail_max")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_completed(path: Path, schema: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required input is absent: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != schema or data.get("status") != "complete":
        raise ValueError(f"invalid completed {schema} input: {path}")
    return data


def require_true(data: dict[str, Any], names: tuple[str, ...], *, label: str) -> None:
    guards = data.get("observational_guards")
    if not isinstance(guards, dict) or any(guards.get(name) is not True for name in names):
        raise ValueError(f"{label} lacks required true guard(s): {names}")


def require_fraction_distribution(
    values: dict[str, Any], required_keys: tuple[str, ...], *, label: str
) -> dict[str, float]:
    if set(values) != set(required_keys):
        raise ValueError(f"{label} keys differ from required descriptor schema: {sorted(values)}")
    result = {key: float(values[key]) for key in required_keys}
    if any(value < 0.0 or value > 1.0 for value in result.values()):
        raise ValueError(f"{label} contains a fraction outside [0, 1]")
    if abs(sum(result.values()) - 1.0) > 1e-9:
        raise ValueError(f"{label} does not sum to one")
    return result


def active_sources(combination: str) -> tuple[str, ...]:
    values = tuple(combination.split("+"))
    if not values or any(source not in SOURCES for source in values) or len(set(values)) != len(values):
        raise ValueError(f"invalid source combination: {combination}")
    return values


def source_active_fractions(combinations: dict[str, float]) -> dict[str, float]:
    return {
        source: sum(fraction for combination, fraction in combinations.items() if source in active_sources(combination))
        for source in SOURCES
    }


def require_record_distribution(value: Any, *, source: str, label: str) -> dict[str, int | None]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} {source} record distribution is absent")
    required = {"sample_count", "p50", "p95", "max"}
    if not required.issubset(value):
        raise ValueError(f"{label} {source} record distribution is incomplete")
    sample_count = int(value["sample_count"])
    if sample_count <= 0:
        raise ValueError(f"{label} {source} has no nonempty source samples")
    result: dict[str, int | None] = {"sample_count": sample_count}
    for key in ("p50", "p95", "max"):
        if value[key] is None:
            raise ValueError(f"{label} {source} {key} is absent despite nonempty samples")
        result[key] = int(value[key])
    return result


def require_tail_distribution(value: Any, *, label: str) -> dict[str, int]:
    if not isinstance(value, dict) or set(TAIL_KEYS) - set(value):
        raise ValueError(f"{label} packed-tail descriptor is incomplete")
    return {key: int(value[key]) for key in TAIL_KEYS}


def normalize_workload(
    *,
    model_anchor: str,
    workload: str,
    policy_decode_calls: Any,
    combinations: Any,
    fan_in: Any,
    record_counts: Any,
    packed_tail: Any,
) -> dict[str, Any]:
    if int(policy_decode_calls) != 7:
        raise ValueError(f"{model_anchor}/{workload} does not have the required seven q_len=1 calls")
    if not isinstance(combinations, dict) or not combinations:
        raise ValueError(f"{model_anchor}/{workload} source-combination descriptor is absent")
    parsed_combinations = {str(key): float(value) for key, value in combinations.items()}
    for combination in parsed_combinations:
        active_sources(combination)
    if abs(sum(parsed_combinations.values()) - 1.0) > 1e-9:
        raise ValueError(f"{model_anchor}/{workload} source-combination fractions do not sum to one")
    if any(value < 0.0 or value > 1.0 for value in parsed_combinations.values()):
        raise ValueError(f"{model_anchor}/{workload} source-combination fraction is outside [0, 1]")
    if not isinstance(fan_in, dict):
        raise ValueError(f"{model_anchor}/{workload} fan-in descriptor is absent")
    parsed_fan_in = require_fraction_distribution(fan_in, FAN_IN_KEYS, label=f"{model_anchor}/{workload} fan-in")
    implied_fan_in = {
        key: sum(value for combination, value in parsed_combinations.items() if len(active_sources(combination)) == count)
        for count, key in enumerate(FAN_IN_KEYS, start=1)
    }
    if any(abs(parsed_fan_in[key] - implied_fan_in[key]) > 1e-9 for key in FAN_IN_KEYS):
        raise ValueError(f"{model_anchor}/{workload} fan-in does not match source combinations")
    if not isinstance(record_counts, dict):
        raise ValueError(f"{model_anchor}/{workload} source-record descriptor is absent")
    active = source_active_fractions(parsed_combinations)
    normalized_records = {
        source: require_record_distribution(record_counts.get(source), source=source, label=f"{model_anchor}/{workload}")
        for source in SOURCES
        if active[source] > 0.0
    }
    return {
        "model_anchor": model_anchor,
        "workload": workload,
        "actual_policy_decode_calls": 7,
        "source_combination_fractions": dict(sorted(parsed_combinations.items())),
        "fan_in_fractions": parsed_fan_in,
        "source_active_fractions": active,
        "source_record_count_conditioned_on_nonempty": normalized_records,
        "packed_page_tail_distribution": require_tail_distribution(packed_tail, label=f"{model_anchor}/{workload}"),
        "interpretation": "Normalized logical descriptor for one fixed request; not an absolute event count, workload distribution, or hardware demand.",
    }


def observed_range(values: list[float | int]) -> dict[str, float | int]:
    if not values:
        raise ValueError("cannot summarize an empty observed descriptor field")
    return {"min": min(values), "max": max(values), "range": max(values) - min(values), "sample_count": len(values)}


def coverage_envelope(rows: list[dict[str, Any]]) -> dict[str, Any]:
    combinations = sorted({key for row in rows for key in row["source_combination_fractions"]})
    return {
        "scope": "Observed min/max over six fixed request descriptors only; not a hardware resource range or sizing recommendation.",
        "source_combination_fractions": {
            key: observed_range([float(row["source_combination_fractions"].get(key, 0.0)) for row in rows])
            for key in combinations
        },
        "fan_in_fractions": {
            key: observed_range([float(row["fan_in_fractions"][key]) for row in rows])
            for key in FAN_IN_KEYS
        },
        "source_active_fractions": {
            source: observed_range([float(row["source_active_fractions"][source]) for row in rows])
            for source in SOURCES
        },
        "source_record_count_conditioned_on_nonempty": {
            source: {
                stat: observed_range(
                    [int(row["source_record_count_conditioned_on_nonempty"][source][stat]) for row in rows if source in row["source_record_count_conditioned_on_nonempty"]]
                )
                for stat in ("p50", "p95", "max")
            }
            for source in SOURCES
        },
        "packed_page_tail_distribution": {
            key: observed_range([int(row["packed_page_tail_distribution"][key]) for row in rows])
            for key in TAIL_KEYS
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M6 no-model Qwen/Llama fixed-horizon logical-descriptor coverage envelope; no hardware sizing."
    )
    parser.add_argument("--qwen-core-contract", type=Path, required=True)
    parser.add_argument("--qwen-a428-report", type=Path, required=True)
    parser.add_argument("--llama-m51-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    qwen_core = load_completed(args.qwen_core_contract, QWEN_CORE_SCHEMA)
    qwen = load_completed(args.qwen_a428_report, QWEN_A428_SCHEMA)
    llama = load_completed(args.llama_m51_report, LLAMA_M51_SCHEMA)
    require_true(
        qwen_core,
        (
            "all_input_hashes_and_required_guards_verified",
            "three_workload_qwen_descriptor_coverage_verified",
            "core_contract_separates_portable_from_qwen_specific_fields",
            "no_hardware_parameter_selected",
        ),
        label="Qwen A4.2.14 core closure",
    )
    require_true(
        qwen,
        (
            "all_workloads_a424_event_guards_verified",
            "all_workloads_semantics_certified",
            "shared_actual_policy_decode_calls",
            "three_fresh_sources_collected",
            "no_stability_threshold_selected",
        ),
        label="Qwen A4.2.8 descriptor",
    )
    require_true(
        llama,
        (
            "all_32_layers_all_8_kv_heads_covered_each_workload",
            "all_workloads_hot_packed_observed",
            "attention_same_mask_numerical_guard_work_executed_each_workload",
            "dense_token_trajectory_forced_in_route_a_each_workload",
            "event_source_decisions_partition_merges_each_workload",
            "failed_m5_natural_horizon_record_bound",
            "m41_non_strict_summarization_context_retained",
            "shared_actual_policy_decode_calls",
            "whole_model_logits_not_used_as_gate",
            "no_hardware_parameter_selected",
        ),
        label="Llama M5.1 descriptor",
    )
    qscope = qwen_core["qwen3_8b_kvzap_resource_descriptor"]["scope"]
    if int(qscope["hot_window_tokens"]) != int(llama["config"]["window_size"]):
        raise ValueError("Qwen/Llama hot-window inputs differ; a conditioned descriptor comparison is invalid")
    if int(qscope["page_tokens"]) != int(llama["config"]["page_tokens"]):
        raise ValueError("Qwen/Llama page reference inputs differ; a conditioned descriptor comparison is invalid")
    if int(qwen["config"]["max_new_tokens"]) != int(llama["continuation_contract"]["fixed_new_tokens"]):
        raise ValueError("Qwen/Llama declared fixed continuation lengths differ")
    if qwen["cross_workload"].get("shared_actual_policy_decode_calls") != 7 or llama["cross_workload"].get("shared_actual_policy_decode_calls") != 7:
        raise ValueError("Qwen/Llama reports do not share seven policy-decode calls")
    rows: list[dict[str, Any]] = []
    for workload, point in sorted(qwen["per_workload"].items()):
        summary = point.get("summary")
        if not isinstance(summary, dict):
            raise ValueError(f"Qwen/{workload} summary is absent")
        rows.append(
            normalize_workload(
                model_anchor="qwen3_8b_kvzap",
                workload=workload,
                policy_decode_calls=point.get("actual_policy_decode_calls"),
                combinations=summary.get("source_combination_fractions"),
                fan_in=summary.get("fan_in_fractions"),
                record_counts=summary.get("source_record_count_distribution"),
                packed_tail=summary.get("packed_page_witness_distribution"),
            )
        )
    for workload, point in sorted(llama["per_workload"].items()):
        descriptor = point.get("descriptor")
        if not isinstance(descriptor, dict):
            raise ValueError(f"Llama/{workload} descriptor is absent")
        rows.append(
            normalize_workload(
                model_anchor="nous_llama31_8b_kvzap",
                workload=workload,
                policy_decode_calls=point.get("actual_policy_decode_calls"),
                combinations=descriptor.get("source_combination_fractions"),
                fan_in=descriptor.get("fan_in_fractions"),
                record_counts=descriptor.get("source_record_count_distribution"),
                packed_tail=descriptor.get("packed_page_tail_distribution"),
            )
        )
    qwen_rows = [row for row in rows if row["model_anchor"] == "qwen3_8b_kvzap"]
    llama_rows = [row for row in rows if row["model_anchor"] == "nous_llama31_8b_kvzap"]
    if {row["workload"] for row in qwen_rows} != {"retrieval", "summarization", "reasoning"}:
        raise ValueError("Qwen report lacks the required three workload descriptors")
    if {row["workload"] for row in llama_rows} != {"retrieval", "summarization", "reasoning"}:
        raise ValueError("Llama report lacks the required three workload descriptors")
    config = {
        "qwen_core_contract": {"path": str(args.qwen_core_contract), "sha256": sha256(args.qwen_core_contract)},
        "qwen_a428_report": {"path": str(args.qwen_a428_report), "sha256": sha256(args.qwen_a428_report)},
        "llama_m51_report": {"path": str(args.llama_m51_report), "sha256": sha256(args.llama_m51_report)},
        "required_declared_fixed_new_tokens": 8,
        "required_actual_policy_decode_calls": 7,
        "shared_hot_window_tokens": int(qscope["hot_window_tokens"]),
        "shared_page_tokens_reference_input": int(qscope["page_tokens"]),
    }
    report = {
        "schema_version": M6_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model, hash-bound functional/trace-derived logical-descriptor coverage comparison; not modeled or measured hardware evidence",
        "per_model_fixed_workload_descriptors": {
            "qwen3_8b_kvzap": qwen_rows,
            "nous_llama31_8b_kvzap": llama_rows,
        },
        "cross_model_conditioned_coverage_envelope": coverage_envelope(rows),
        "interpretation": {
            "shared_semantic_portability": "Both completed anchors use the same-mask dense comparator, explicit Full-KV bypass, hot/pending/packed Route-A state, and online merge under the declared fixed-horizon contract.",
            "observed_extension": "The envelope retains Llama's higher observed three-active-source fractions rather than averaging them away; this is a fixed-workload interface-coverage finding only.",
            "resource_envelope_status": "bounded descriptor coverage over six fixed requests, not a distribution, capacity requirement, scheduler choice, or hardware resource envelope.",
        },
        "observational_guards": {
            "all_input_hashes_and_required_guards_verified": True,
            "same_declared_fixed_horizon_verified": True,
            "same_actual_policy_decode_call_count_verified": True,
            "same_hot_window_and_page_reference_inputs_verified": True,
            "qwen_and_llama_rows_kept_separate": True,
            "absolute_event_counts_not_pooled": True,
            "source_record_ranges_conditioned_on_nonempty_source": True,
            "m41_record_only_context_retained": True,
            "no_hardware_parameter_selected": True,
            "no_model_runtime_loaded": True,
        },
        "boundaries": [
            "M6 compares only already-completed fixed-request, timestamp-free logical descriptors. It is not a natural-generation distribution, quality benchmark, or serving measurement.",
            "The min/max values are observed coverage bounds over six rows, not FIFO depth, PTE width, bank, burst, merge precision, PE count, scheduler, controller timing, capacity, traffic, latency, throughput, energy, area, hardware, architecture-specification, or RTL inputs.",
            "Qwen and Llama differ in layer count, predictor, threshold, and request content. M6 deliberately does not pool absolute event counts or convert normalized descriptor variation into equal hardware requirements.",
            "The retained Llama M4.1 record-only strict-ULP context is not a numerical pass and does not select a merge precision.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "m6_cross_model_fixed_horizon_envelope_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"M6 cross-model fixed-horizon descriptor envelope completed: {path}")


if __name__ == "__main__":
    main()
