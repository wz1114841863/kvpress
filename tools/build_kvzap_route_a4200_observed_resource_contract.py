"""A4.2.0 observed software-resource/interface contract; no hardware sizing."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


A4200_SCHEMA = "kvzap-route-a4200-observed-resource-contract-1.0"
A4168_SCHEMA = "kvzap-route-a4168-cross-horizon-accounting-report-1.0"
A4167_SCHEMA = "kvzap-route-a4167-long-horizon-three-path-profiler-1.0"
A4163_SCHEMA = "kvzap-route-a4163-cross-workload-three-path-profiler-1.0"
ROUTE_PATH = "same_mask_route_a_external_storage_empty_source_elision"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.2.0 provenance-bound observed Route-A resource/interface contract; no model execution or hardware sizing.")
    parser.add_argument("--cross-horizon-accounting", type=Path, required=True)
    parser.add_argument("--h32-three-path-profiler", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def load_complete(path: Path, schema: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != schema or payload.get("status") != "complete":
        raise ValueError(f"not a completed {schema} artifact: {path}")
    return payload


def require_true(manifest: dict[str, Any], names: tuple[str, ...]) -> None:
    missing = [name for name in names if manifest.get("observational_guards", {}).get(name) is not True]
    if missing:
        raise ValueError(f"artifact lacks required guards: {missing}")


def route_result(summary: dict[str, Any]) -> dict[str, Any]:
    for row in summary.get("results", []):
        if row.get("path") == ROUTE_PATH:
            return row
    raise ValueError("A4163 summary lacks Route-A external-storage/elision result")


def extract_horizons(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {row.get("label"): row for row in report.get("horizons", [])}
    if set(rows) != {"h16", "h32"}:
        raise ValueError("A4168 must contain exactly h16 and h32 accounting rows")
    for label, row in rows.items():
        if not isinstance(row.get("generated_token_count"), int) or row["generated_token_count"] <= 0:
            raise ValueError(f"{label} lacks a positive generated token count")
        if not isinstance(row.get("merge_calls"), int) or row["merge_calls"] <= 0:
            raise ValueError(f"{label} lacks positive merge calls")
        if not 0.0 <= row.get("partial_call_reduction_fraction_from_three_source_unelided", -1.0) <= 1.0:
            raise ValueError(f"{label} has invalid source-elision fraction")
        page = row.get("page_tail_coverage", {})
        if any(not isinstance(page.get(name), int) or page[name] <= 0 for name in ("selected_layer_count", "selected_kv_head_count", "max_packed_page_count", "max_packed_full_page_count", "max_packed_tail_tokens", "page_witness_count")):
            raise ValueError(f"{label} lacks complete page/tail coverage")
    return rows


def build_contract(*, horizons: dict[str, dict[str, Any]], child: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    config = child.get("config", {})
    if config.get("target_layers") != ["all"] or config.get("target_kv_head") != "all" or config.get("admission_budget") != 512:
        raise ValueError("A4.2.0 is bounded to the accepted all-layer/all-head budget-512 observation")
    if config.get("page_tokens") != 64 or config.get("window_size") != 128 or config.get("threshold") != -4.0:
        raise ValueError("A4.2.0 input differs from the accepted Route-A policy point")
    h32 = horizons["h32"]
    guard = route.get("external_storage_guard", {})
    for key in ("selected_layer_count", "selected_kv_head_count", "max_packed_page_count", "max_packed_full_page_count", "max_packed_tail_tokens", "page_witness_count"):
        if guard.get(key) != h32["page_tail_coverage"].get(key):
            raise ValueError(f"A4167 profiler and A4168 h32 page witness differ: {key}")
    source_accounting = route.get("source_phase_accounting", {})
    if source_accounting.get("merge_calls") != h32["merge_calls"]:
        raise ValueError("A4167 profiler and A4168 h32 merge counts differ")
    return {
        "contract_scope": {"model": config["model_name"], "model_revision": config["model_revision"], "predictor": config["predictor_name"], "predictor_revision": config["predictor_revision"], "threshold": config["threshold"], "hot_window_tokens": config["window_size"], "page_tokens": config["page_tokens"], "admission_budget_retained_tokens_per_layer_call": config["admission_budget"], "selected_layers": config["target_layers"], "selected_kv_heads": config["target_kv_head"], "observed_layer_count": guard["selected_layer_count"], "observed_kv_head_count": guard["selected_kv_head_count"]},
        "control_plane_contract": {"full_kv_bypass": {"required_behavior": "No Route-A admission or cold-state ownership is entered when bypass is selected.", "evidence": "A4166/A4167 Full-KV bypass control."}, "route_a_fast_path": {"required_behavior": "Original KVzap keep decisions are replayed; mature retained records are admitted and cold attention is supplied only by pending staging and sealed packed pages.", "evidence": "A4165/A4167 all-layer/all-head execution and native-cold-absence guards."}},
        "data_plane_interfaces": [
            {"name": "hot_source", "required_fields": ["regular hot K/V", "token position", "query-head to KV-head mapping"], "per_evaluation_behavior": "Provide one ordered partial attention or an explicit empty-source outcome."},
            {"name": "pending_retained_cold_staging", "required_fields": ["retained K/V", "original token position", "FIFO/append order"], "per_evaluation_behavior": "Provide one ordered partial attention or an explicit empty-source outcome; it is not supplied by dense native cold KV."},
            {"name": "sealed_packed_cold_pages", "required_fields": ["page identifier", "valid token count", "retained K/V", "original token positions", "append order"], "per_evaluation_behavior": "Provide one ordered partial attention or an explicit empty-source outcome."},
            {"name": "online_softmax_merge", "required_fields": ["per-source partial max", "partial normalization state", "partial value accumulator"], "per_evaluation_behavior": "Merge exactly once after the hot/pending/packed decisions."},
        ],
        "observed_software_structure": {"horizons": horizons, "h32_source_accounting": source_accounting, "contract_invariants": ["Every attention evaluation makes exactly one source decision for hot, pending, and packed.", "Every attention evaluation makes exactly one online-softmax merge decision.", "An empty source is explicitly skipped rather than silently read from dense native cold KV.", "Hot-window records do not enter cold pages; packed page valid counts and original positions remain conserved."]},
        "page_tail_observation": {"h16": horizons["h16"]["page_tail_coverage"], "h32": horizons["h32"]["page_tail_coverage"], "interpretation": "These are observed Python-reference state/page witnesses at one policy point, not FIFO capacity, allocator sizing, or a universal page-count bound."},
        "unresolved_hardware_contract_parameters": [
            {"name": "pending_FIFO_depth_and_overflow_policy", "status": "unresolved", "reason": "Observed pending reads/skips establish interface use but not worst-case queue depth or service rate."},
            {"name": "page_table_entry_bits_and_allocator_seal_policy", "status": "unresolved", "reason": "Observed page counts/valid tails establish fields and witnesses, not physical metadata format or allocator behavior."},
            {"name": "bank_mapping_burst_gather_format", "status": "unresolved", "reason": "A4 profiler rows are Python-reference diagnostics; A3 byte/cycle assumptions require separate sensitivity binding."},
            {"name": "merge_state_precision_and_PE_scheduler_interface", "status": "unresolved", "reason": "Online-softmax semantic interface is validated, but hardware state width, PE count, and scheduling policy are not measured here."},
            {"name": "bypass_switch_timing_and_admission_service_rate", "status": "unresolved", "reason": "Control-plane behavior is explicit; software measurements do not establish implementation timing."},
        ],
        "boundaries": ["This is an observed software resource/interface contract, not an architecture specification or RTL input freeze.", "It does not convert Python call counts, allocator observations, profiler rows, or A3 models into HBM traffic, hardware latency, throughput, energy, area, or frequency.", "Unresolved fields require an explicit A4.2 sensitivity/measurement binding before any hardware sizing decision."],
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    accounting = load_complete(args.cross_horizon_accounting, A4168_SCHEMA)
    require_true(accounting, ("input_artifacts_complete", "h16_internal_provenance_verified", "h32_internal_provenance_verified", "fresh_horizon_sources_not_falsefully_equated", "source_partial_skip_merge_accounting_validated_per_horizon", "page_tail_coverage_validated_per_horizon", "profiler_ranges_not_aggregated_as_latency", "no_model_execution"))
    parent = load_complete(args.h32_three_path_profiler, A4167_SCHEMA)
    require_true(parent, ("a4166_long_horizon_measurement_verified", "a4163_child_complete", "child_source_sha_matches_a4165_and_a4166", "child_profiler_token_digests_match_certificates", "child_route_a_source_partial_or_skip_accounting_matches_merge", "child_phase_rows_coalesced", "profiler_is_separate_from_repeated_timing"))
    if accounting.get("config", {}).get("h32_sha256") != hashlib.sha256(args.h32_three_path_profiler.read_bytes()).hexdigest():
        raise ValueError("A4168 does not bind the supplied A4167 profiler parent")
    child_path = args.h32_three_path_profiler.parent / parent["a4163_child_manifest"]
    child = load_complete(child_path, A4163_SCHEMA)
    require_true(child, ("all_layers_all_kv_heads_external_storage_substituted", "persistent_selected_native_cold_absent", "replay_mask_consumption_complete", "profiler_token_digests_match_certificates", "route_a_source_partial_or_skip_accounting_matches_merge", "route_a_elided_pending_skip_observed"))
    summary = json.loads((child_path.parent / child["phase_summary"]).read_text(encoding="utf-8"))
    contract = build_contract(horizons=extract_horizons(accounting["report"]), child=child, route=route_result(summary))
    config = {"cross_horizon_accounting": str(args.cross_horizon_accounting), "h32_three_path_profiler": str(args.h32_three_path_profiler), "cross_horizon_sha256": hashlib.sha256(args.cross_horizon_accounting.read_bytes()).hexdigest(), "h32_profiler_sha256": hashlib.sha256(args.h32_three_path_profiler.read_bytes()).hexdigest()}
    args.output_dir.mkdir(parents=True)
    manifest = {"schema_version": A4200_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "contract": contract, "observational_guards": {"a4168_cross_horizon_accounting_verified": True, "a4167_h32_profiler_parent_verified": True, "all_layer_all_head_external_storage_semantics_verified": True, "native_cold_absence_verified": True, "cross_horizon_page_tail_witnesses_bound": True, "h32_profiler_and_cross_horizon_counts_agree": True, "unresolved_hardware_parameters_explicit": True, "no_model_execution": True}, "boundaries": contract["boundaries"]}
    output = args.output_dir / "a4200_observed_resource_contract.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.2.0 observed resource/interface contract completed: {output}")


if __name__ == "__main__":
    main()
