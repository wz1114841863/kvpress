#!/usr/bin/env python3
"""Aggregate three fixed Llama M2 lifecycle gates into a bounded descriptor.

This is deliberately an aggregation of already functional/trace-derived M2
outputs.  It neither loads a model nor creates a capacity, traffic, timing, or
hardware resource estimate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


M2_SCHEMA = "kvzap-llama31-m2-lifecycle-gate-1.0"
M4_SCHEMA = "kvzap-llama31-m4-bounded-workload-envelope-1.0"
WORKLOADS = ("retrieval", "summarization", "reasoning")
REQUIRED_M2_GUARDS = (
    "m0_complete_explicit_override_bound",
    "m1_completed_semantic_prerequisite",
    "all_32_layers_and_all_8_kv_heads_covered_at_both_points",
    "online_dense_events_replayed_exactly_once_at_both_points",
    "same_mask_fp32_and_executed_dtype_guards_executed_at_both_points",
    "same_mask_numerical_guard_remained_enforced",
    "execution_dtype_ulp_mode_declared",
    "budget_one_hot_pending_packed_observed",
    "budget_512_hot_packed_observed",
    "budget_512_full_multi_tail_page_witness",
    "model_cache_mutated_by_backend",
    "route_a_predictor_scored_online",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M4 no-model bounded Llama workload descriptor aggregation; not a hardware envelope."
    )
    parser.add_argument("--retrieval-m2-manifest", type=Path, required=True)
    parser.add_argument("--summarization-m2-manifest", type=Path, required=True)
    parser.add_argument("--reasoning-m2-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def load_m2(path: Path, *, workload: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{workload} M2 manifest is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != M2_SCHEMA or value.get("status") != "complete":
        raise ValueError(f"{workload} input is not a completed {M2_SCHEMA} manifest")
    config, request, guards = value.get("config"), value.get("request"), value.get("observational_guards")
    if not isinstance(config, dict) or not isinstance(request, dict) or not isinstance(guards, dict):
        raise ValueError(f"{workload} M2 lacks config/request/guard sections")
    if config.get("preset") != workload or request.get("request_id") != f"builtin_{workload}_trace":
        raise ValueError(f"{workload} M2 does not use its required fixed built-in request")
    if any(guards.get(name) is not True for name in REQUIRED_M2_GUARDS[:-2]):
        raise ValueError(f"{workload} M2 lacks a required true functional guard")
    if guards["model_cache_mutated_by_backend"] is not False or guards["route_a_predictor_scored_online"] is not False:
        raise ValueError(f"{workload} M2 violates native-cache or replay-only boundary")
    return value


def summarize_point(point: dict[str, Any]) -> dict[str, Any]:
    route = point["replayed_same_mask_route_a"]
    coverage = route["policy_coverage"]
    layers = coverage["layers"]
    heads = [head for layer in layers for head in layer["heads"]]
    final_states = [head for layer in route["final_lifecycle_state"] for head in layer["heads"]]
    ulp_rows = route["execution_dtype_ulp_breach_summary"]["layers"]
    return {
        "admission_budget_reference_input": point["admission_budget"],
        "all_layer_mask_decision_count": sum(int(layer["original_mask_decision_count"]) for layer in layers),
        "all_layer_kv_head_state_count": len(heads),
        "source_coverage": route["source_coverage"],
        "page_witness_count": len(route["page_witness"]["witnesses"]),
        "execution_dtype_ulp_diagnostic": {
            "mode": ulp_rows[0]["mode"],
            "executed_dtype_ulp_limit": ulp_rows[0]["executed_dtype_ulp_limit"],
            "breach_count": sum(int(row["breach_count"]) for row in ulp_rows),
            "max_observed_ulps": max((row["max_observed_ulps"] for row in ulp_rows if row["max_observed_ulps"] is not None), default=None),
            "any_infinite_observation": any(bool(row["max_observed_ulps_is_infinite"]) for row in ulp_rows),
        },
        "final_state_nonzero_counts": {
            "pending": sum(int(head["pending_tokens"]) > 0 for head in final_states),
            "packed": sum(int(head["packed_tokens"]) > 0 for head in final_states),
            "sealed_full_page": sum(int(head["packed_full_page_count"]) > 0 for head in final_states),
            "nonempty_tail": sum(int(head["packed_tail_tokens"]) > 0 for head in final_states),
        },
        "final_state_maxima": {
            name: max(int(head[name]) for head in final_states)
            for name in (
                "hot_tokens", "pending_tokens", "packed_tokens", "packed_page_count",
                "packed_full_page_count", "packed_tail_tokens",
            )
        },
    }


def summarize_workload(value: dict[str, Any]) -> dict[str, Any]:
    config, request, outcomes = value["config"], value["request"], value["outcomes"]
    return {
        "request_id": request["request_id"],
        "content_sha256": request["content_sha256"],
        "context_tokens": request["context_tokens"],
        "functional_reference_inputs": {
            name: config[name]
            for name in ("threshold", "window_size", "page_tokens", "pending_admission_budget", "packing_admission_budget", "max_new_tokens", "context_repetitions", "max_executed_dtype_ulps", "execution_dtype_ulp_mode", "ulp_breach_sample_limit")
        },
        "pending_budget_one": summarize_point(outcomes["pending_budget_one"]),
        "packed_budget_512": summarize_point(outcomes["packed_budget_512"]),
        "full_kv_bypass_zero_route_a_admission": outcomes["full_kv_bypass"]["zero_route_a_admission"],
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    paths = {
        "retrieval": args.retrieval_m2_manifest,
        "summarization": args.summarization_m2_manifest,
        "reasoning": args.reasoning_m2_manifest,
    }
    manifests = {workload: load_m2(path, workload=workload) for workload, path in paths.items()}
    hashes = {workload: sha256_file(path) for workload, path in paths.items()}
    m0_hashes = {workload: manifests[workload]["m0_provenance"]["manifest_sha256"] for workload in WORKLOADS}
    m1_hashes = {workload: manifests[workload]["m1_provenance"]["manifest_sha256"] for workload in WORKLOADS}
    if len(set(m0_hashes.values())) != 1 or len(set(m1_hashes.values())) != 1:
        raise ValueError("M4 requires every workload to bind the same completed M0 and M1 manifests")
    summaries = {workload: summarize_workload(manifests[workload]) for workload in WORKLOADS}
    request_hashes = [summaries[workload]["content_sha256"] for workload in WORKLOADS]
    if len(set(request_hashes)) != len(WORKLOADS):
        raise ValueError("M4 fixed workload matrix requires three distinct request contents")
    configs = [summaries[workload]["functional_reference_inputs"] for workload in WORKLOADS]
    if any(config != configs[0] for config in configs[1:]):
        raise ValueError("M4 requires matched functional-reference inputs across workloads")
    config = {
        workload: {"path": str(paths[workload]), "sha256": hashes[workload]}
        for workload in WORKLOADS
    }
    report = {
        "schema_version": M4_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model hash-bound aggregation of fixed-request functional/trace-derived M2 summaries; not modeled or measured hardware evidence",
        "shared_provenance": {
            "m0_manifest_sha256": next(iter(m0_hashes.values())),
            "m1_manifest_sha256": next(iter(m1_hashes.values())),
            "matched_functional_reference_inputs": configs[0],
        },
        "bounded_fixed_workload_descriptors": summaries,
        "cross_workload_summary": {
            "workloads": list(WORKLOADS),
            "distinct_request_content_count": len(set(request_hashes)),
            "all_workloads_cover_hot_pending_packed_at_budget_one": all(
                all(summaries[workload]["pending_budget_one"]["source_coverage"].values())
                for workload in WORKLOADS
            ),
            "all_workloads_cover_hot_packed_and_page_witness_at_budget_512": all(
                summaries[workload]["packed_budget_512"]["source_coverage"]["hot_observed"]
                and summaries[workload]["packed_budget_512"]["source_coverage"]["packed_observed"]
                and summaries[workload]["packed_budget_512"]["page_witness_count"] > 0
                for workload in WORKLOADS
            ),
            "interpretation": "Three fixed built-in requests broaden Llama lifecycle/source coverage only. Their minima/maxima are not a model distribution, universal resource envelope, or hardware sizing range.",
        },
        "observational_guards": {
            "three_expected_fixed_workloads_present": True,
            "three_distinct_request_contents": True,
            "all_workloads_bind_same_m0_m1": True,
            "functional_reference_inputs_matched": True,
            "all_workloads_replay_online_dense_masks_once": True,
            "all_workloads_keep_native_cache_unmodified": True,
            "no_model_runtime_loaded": True,
            "no_hardware_parameter_selected": True,
        },
        "boundaries": [
            "M4 is a hash-bound aggregation; the model executions occurred only in its three M2 inputs.",
            "Three built-in requests are a bounded coverage matrix, not a production workload sample, accuracy benchmark, or probability distribution.",
            "No field is physical capacity, HBM traffic, actual latency, throughput, energy, area, hardware acceleration, architecture specification, or RTL evidence.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "llama31_m4_bounded_workload_envelope_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"M4 bounded Llama workload descriptor aggregation completed: {output}")


if __name__ == "__main__":
    main()
