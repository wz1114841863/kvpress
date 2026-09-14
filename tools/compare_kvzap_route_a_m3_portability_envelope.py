#!/usr/bin/env python3
"""M3 no-model portability/envelope comparison for Qwen and Nous Llama.

The report keeps each fixed-workload descriptor separate.  It checks whether
the portable Route-A semantic contract has two model anchors; it never turns
their source/page distributions into universal ranges or hardware parameters.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash
from tools.run_kvzap_llama31_m1_semantic_gate import M0_SCHEMA, M1_SCHEMA
from tools.run_kvzap_llama31_m2_lifecycle_gate import M2_SCHEMA


M3_SCHEMA = "kvzap-route-a-m3-portability-envelope-comparison-1.1"
M3_PRIOR_SCHEMA = "kvzap-route-a-m3-portability-envelope-comparison-1.0"
QWEN_SCHEMA = "kvzap-route-a4214-core-contract-closure-1.0"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def load(path: Path, schema: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required input is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != schema or value.get("status") != "complete":
        raise ValueError(f"invalid completed {schema} input: {path}")
    return value


def load_prior_m3(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"prior M3 report is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != M3_PRIOR_SCHEMA
        or value.get("status") != "complete"
    ):
        raise ValueError(f"invalid completed {M3_PRIOR_SCHEMA} prior report: {path}")
    return value


def require_true(data: dict[str, Any], names: tuple[str, ...], *, label: str) -> None:
    guards = data.get("observational_guards")
    if not isinstance(guards, dict) or any(guards.get(name) is not True for name in names):
        raise ValueError(f"{label} lacks required true guard(s): {names}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M3 no-model Qwen/Llama Route-A portability and descriptor comparison; no hardware selection.")
    parser.add_argument("--qwen-core-contract", type=Path, required=True)
    parser.add_argument("--llama-m0-manifest", type=Path, required=True)
    parser.add_argument("--llama-m1-manifest", type=Path, required=True)
    parser.add_argument("--llama-m2-manifest", type=Path, required=True)
    parser.add_argument(
        "--prior-m3-report",
        type=Path,
        required=True,
        help="Completed M3.1 report to reconcile; it is never modified.",
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def lifecycle_summary(point: dict[str, Any]) -> dict[str, Any]:
    route = point["replayed_same_mask_route_a"]
    states = [head for layer in route["final_lifecycle_state"] for head in layer["heads"]]
    return {
        "admission_budget_reference_input": point["admission_budget"],
        "source_observed": route["source_coverage"],
        "layer_count": len(route["final_lifecycle_state"]),
        "layer_kv_head_state_count": len(states),
        "final_state_nonzero_counts": {
            "pending": sum(int(head["pending_tokens"]) > 0 for head in states),
            "packed": sum(int(head["packed_tokens"]) > 0 for head in states),
            "sealed_full_page": sum(int(head["packed_full_page_count"]) > 0 for head in states),
            "nonempty_tail": sum(int(head["packed_tail_tokens"]) > 0 for head in states),
        },
        "final_state_maxima": {
            "hot_tokens": max(int(head["hot_tokens"]) for head in states),
            "pending_tokens": max(int(head["pending_tokens"]) for head in states),
            "packed_tokens": max(int(head["packed_tokens"]) for head in states),
            "packed_page_count": max(int(head["packed_page_count"]) for head in states),
            "packed_full_page_count": max(int(head["packed_full_page_count"]) for head in states),
            "packed_tail_tokens": max(int(head["packed_tail_tokens"]) for head in states),
        },
        "page_witness": route["page_witness"],
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    qwen = load(args.qwen_core_contract, QWEN_SCHEMA)
    m0 = load(args.llama_m0_manifest, M0_SCHEMA)
    m1 = load(args.llama_m1_manifest, M1_SCHEMA)
    m2 = load(args.llama_m2_manifest, M2_SCHEMA)
    prior_m3 = load_prior_m3(args.prior_m3_report)
    require_true(qwen, ("all_input_hashes_and_required_guards_verified", "three_workload_qwen_descriptor_coverage_verified", "core_contract_separates_portable_from_qwen_specific_fields", "no_hardware_parameter_selected"), label="Qwen closure")
    require_true(m0, ("fixed_base_snapshot_present", "llama_structure_matches_expected", "official_predictor_linear_dimensions_match_base_structure", "direct_derivation_or_explicit_override_bound"), label="Llama M0")
    require_true(m1, ("m0_complete_explicit_override_bound", "all_32_layers_and_all_8_kv_heads_selected", "same_mask_dense_events_replayed_exactly_once_by_route_a", "same_mask_fp32_and_executed_dtype_guards_executed"), label="Llama M1")
    require_true(m2, ("m0_complete_explicit_override_bound", "m1_completed_semantic_prerequisite", "all_32_layers_and_all_8_kv_heads_covered_at_both_points", "online_dense_events_replayed_exactly_once_at_both_points", "same_mask_fp32_and_executed_dtype_guards_executed_at_both_points", "budget_one_hot_pending_packed_observed", "budget_512_full_multi_tail_page_witness"), label="Llama M2")
    m0_sha, m1_sha = sha256(args.llama_m0_manifest), sha256(args.llama_m1_manifest)
    if m1.get("m0_provenance", {}).get("manifest_sha256") != m0_sha:
        raise ValueError("M1 does not bind supplied M0 hash")
    if m2.get("m0_provenance", {}).get("manifest_sha256") != m0_sha or m2.get("m1_provenance", {}).get("manifest_sha256") != m1_sha:
        raise ValueError("M2 does not bind supplied M0/M1 hashes")
    qscope = qwen["qwen3_8b_kvzap_resource_descriptor"]["scope"]
    qdescriptor = qwen["qwen3_8b_kvzap_resource_descriptor"]
    lstructure = m0["base_model_structure"]
    qwen_layers = int(qscope["observed_layer_count"])
    qwen_total_layer_kv_states = int(qscope["observed_kv_head_count"])
    if qwen_total_layer_kv_states % qwen_layers:
        raise ValueError("Qwen aggregate layer/KV-head state count is not divisible by layers")
    qwen_kv_heads_per_layer = qwen_total_layer_kv_states // qwen_layers
    llama_layers = int(lstructure["layer_count"])
    llama_kv_heads_per_layer = int(lstructure["kv_head_count"])
    llama_total_layer_kv_states = llama_layers * llama_kv_heads_per_layer
    if int(lstructure["query_heads_per_kv_head_group"]) != 4 or qdescriptor["qwen_specific_group_width_values"] != [4]:
        raise ValueError("observed Qwen/Llama GQA group-width compatibility precondition failed")
    if int(qscope["hot_window_tokens"]) != int(m2["config"]["window_size"]):
        raise ValueError("Qwen and Llama artifacts use different hot windows; do not create a common descriptor")
    if int(qscope["page_tokens"]) != int(m2["config"]["page_tokens"]):
        raise ValueError("Qwen and Llama artifacts use different page reference granularities; do not create a common descriptor")
    pending, packed = m2["outcomes"]["pending_budget_one"], m2["outcomes"]["packed_budget_512"]
    qwen_m3_consumed_projection = {
        "model": qscope["model"],
        "layer_count": qwen_layers,
        "kv_heads_per_layer": qwen_kv_heads_per_layer,
        "total_layer_kv_head_state_count": qwen_total_layer_kv_states,
        "hot_window_tokens": int(qscope["hot_window_tokens"]),
        "page_tokens_reference_input": int(qscope["page_tokens"]),
        "group_width_values": qdescriptor["qwen_specific_group_width_values"],
        "workloads": qdescriptor["workload_descriptor"],
        "a4201_unresolved_parameters": qwen["modeled_sensitivity_retained_unselected"]["a4201_unresolved_parameters"],
        "required_guards": {
            name: qwen["observational_guards"][name]
            for name in (
                "all_input_hashes_and_required_guards_verified",
                "three_workload_qwen_descriptor_coverage_verified",
                "core_contract_separates_portable_from_qwen_specific_fields",
                "no_hardware_parameter_selected",
            )
        },
    }
    prior_qwen_projection = {
        "model": prior_m3["separate_fixed_workload_descriptors"]["qwen3_8b_kvzap"]["model"],
        "layer_count": prior_m3["separate_fixed_workload_descriptors"]["qwen3_8b_kvzap"]["layer_count"],
        "kv_heads_per_layer": int(prior_m3["separate_fixed_workload_descriptors"]["qwen3_8b_kvzap"]["kv_head_count"]) // int(prior_m3["separate_fixed_workload_descriptors"]["qwen3_8b_kvzap"]["layer_count"]),
        "total_layer_kv_head_state_count": prior_m3["separate_fixed_workload_descriptors"]["qwen3_8b_kvzap"]["kv_head_count"],
        "hot_window_tokens": prior_m3["portable_contract_coverage"]["shared_hot_window_tokens"],
        "page_tokens_reference_input": prior_m3["portable_contract_coverage"]["shared_page_tokens_reference_input"],
        "group_width_values": [prior_m3["portable_contract_coverage"]["observed_gqa_query_heads_per_kv_head_group"]],
        "workloads": prior_m3["separate_fixed_workload_descriptors"]["qwen3_8b_kvzap"]["workloads"],
        "a4201_unresolved_parameters": prior_m3["comparison_boundaries"]["unresolved_hardware_fields_carried_forward"],
        "required_guards": {
            name: prior_m3["observational_guards"][name]
            for name in (
                "all_input_hashes_and_required_guards_verified",
                "no_hardware_parameter_selected",
            )
        },
    }
    # The prior report cannot represent two internal Qwen closure guards, so
    # equality is checked over every Qwen field M3.1 serialized or consumed.
    prior_projection_for_equality = dict(prior_qwen_projection)
    prior_projection_for_equality["required_guards"] = {
        "all_input_hashes_and_required_guards_verified": prior_qwen_projection["required_guards"]["all_input_hashes_and_required_guards_verified"],
        "no_hardware_parameter_selected": prior_qwen_projection["required_guards"]["no_hardware_parameter_selected"],
    }
    current_projection_for_equality = dict(qwen_m3_consumed_projection)
    current_projection_for_equality["required_guards"] = {
        "all_input_hashes_and_required_guards_verified": qwen_m3_consumed_projection["required_guards"]["all_input_hashes_and_required_guards_verified"],
        "no_hardware_parameter_selected": qwen_m3_consumed_projection["required_guards"]["no_hardware_parameter_selected"],
    }
    if canonical_sha256(prior_projection_for_equality) != canonical_sha256(current_projection_for_equality):
        raise ValueError("current Qwen M3-consumed semantic projection differs from prior M3 report")
    config = {
        "qwen_core_contract": {"path": str(args.qwen_core_contract), "sha256": sha256(args.qwen_core_contract)},
        "llama_m0": {"path": str(args.llama_m0_manifest), "sha256": m0_sha},
        "llama_m1": {"path": str(args.llama_m1_manifest), "sha256": m1_sha},
        "llama_m2": {"path": str(args.llama_m2_manifest), "sha256": sha256(args.llama_m2_manifest)},
        "prior_m3": {"path": str(args.prior_m3_report), "sha256": sha256(args.prior_m3_report)},
    }
    report = {
        "schema_version": M3_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model, hash-bound comparison of functional/trace-derived descriptors; not modeled or measured hardware evidence",
        "portable_contract_coverage": {
            "two_model_semantic_anchor": True,
            "same_mask_dense_comparator_and_full_kv_bypass": True,
            "maturity_to_pending_to_append_only_packed_lifecycle": True,
            "hot_pending_packed_attention_sources_observed": True,
            "online_softmax_same_mask_numerical_guard": True,
            "observed_gqa_query_heads_per_kv_head_group": 4,
            "shared_hot_window_tokens": int(qscope["hot_window_tokens"]),
            "shared_page_tokens_reference_input": int(qscope["page_tokens"]),
        },
        "separate_fixed_workload_descriptors": {
            "qwen3_8b_kvzap": {
                "model": qscope["model"], "layer_count": qwen_layers,
                "kv_heads_per_layer": qwen_kv_heads_per_layer,
                "total_layer_kv_head_state_count": qwen_total_layer_kv_states,
                "workloads": qdescriptor["workload_descriptor"],
                "interpretation": "Three fixed Qwen requests; source/fan-in/page-tail distributions remain Qwen-specific.",
            },
            "nous_llama31_8b_kvzap": {
                "model": m0["config"]["model_repo_id"], "layer_count": llama_layers,
                "kv_heads_per_layer": llama_kv_heads_per_layer,
                "total_layer_kv_head_state_count": llama_total_layer_kv_states,
                "pending_budget_one": lifecycle_summary(pending), "packed_budget_512": lifecycle_summary(packed),
                "interpretation": "One fixed Llama request and two lifecycle reference points; scalar state summaries are not workload distributions.",
            },
        },
        "comparison_boundaries": {
            "shared_observations": ["Both anchors use a same-mask dense comparator, a Full-KV bypass, protected hot state, and append-only packed-page reference state.", "Both anchors observe GQA group width four and use the same declared hot-window/page reference inputs.", "Llama M2 explicitly observes pending staging at budget one and full/multi/tail packed-page state at budget 512."],
            "not_directly_comparable": ["Qwen has three fixed workloads while Llama has one fixed request.", "Qwen descriptor source/fan-in fractions and page/tail distributions are not a distribution for Llama.", "Llama final-state maxima are not Qwen-equivalent event distributions or a universal resource bound.", "Each model has eight KV heads per layer, but its aggregate layer/KV-head state count differs (Qwen 36 x 8 = 288; Llama 32 x 8 = 256); neither quantity is an accelerator dimension."],
            "unresolved_hardware_fields_carried_forward": qwen["modeled_sensitivity_retained_unselected"]["a4201_unresolved_parameters"],
        },
        "m3_decision": {
            "semantic_portability_for_two_anchored_models": "supported only for the two fixed model/predictor/request contracts",
            "resource_envelope_status": "partial: two separate descriptors identify required abstract state classes, but no universal distribution or hardware dimension is established",
            "architecture_spec_or_rtl_authorized": False,
            "next_scope": "Use the separate descriptors to plan a bounded cross-model workload expansion or admit another pruning method only after it satisfies the Route-A semantic preconditions; do not rerun all Qwen A0-A4 by default.",
        },
        "provenance_reconciliation": {
            "prior_m3_sha256": sha256(args.prior_m3_report),
            "prior_m3_qwen_raw_input_sha256": prior_m3["config"]["qwen_core_contract"]["sha256"],
            "current_qwen_raw_input_sha256": sha256(args.qwen_core_contract),
            "raw_qwen_input_hashes_match": prior_m3["config"]["qwen_core_contract"]["sha256"] == sha256(args.qwen_core_contract),
            "prior_serialized_qwen_projection_sha256": canonical_sha256(prior_projection_for_equality),
            "current_qwen_projection_sha256": canonical_sha256(current_projection_for_equality),
            "m3_consumed_qwen_projection_matches_prior": True,
            "scope": "The equality projection covers the Qwen fields M3.1 serialized or consumed; it does not assert byte identity for the two A4.2.14 source files.",
        },
        "observational_guards": {"all_input_hashes_and_required_guards_verified": True, "qwen_and_llama_descriptors_kept_separate": True, "two_model_shared_semantic_contract_covered": True, "descriptor_head_units_explicit": True, "prior_m3_consumed_qwen_projection_matches": True, "no_hardware_parameter_selected": True, "no_model_runtime_loaded": True},
        "boundaries": ["M3 is a hash-bound comparison of already-completed artifacts. It does not execute a model, estimate capacity/traffic/latency, or select any hardware parameter.", "Shared page/window/GQA values are observed reference compatibility fields, not a universal design point.", "M3.2 clarifies descriptor units and provenance consumption only; it adds no workload, semantic, hardware, or performance evidence.", "This report is not an architecture specification, hardware measurement, or RTL gate."],
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "m3_portability_envelope_comparison_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"M3 portability/envelope comparison completed: {path}")


if __name__ == "__main__":
    main()
