#!/usr/bin/env python3
"""A4.14.1 evidence-classified Route-A accounted ledger; pre-RTL only."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4141-accounted-net-benefit-ledger-1.0"
WORKLOADS = ("retrieval", "summarization", "reasoning")
S2 = "S2_two_32KiB_ping_pong_page_source_buffers"
PRIMARY = "primary_256B_per_model_cycle"
SENSITIVITY = "sensitivity_128B_per_model_cycle"
WINDOW, LAYERS, KV_HEADS, KV_WORD_BYTES = 128, 36, 8, 512
P3_STAGING_BYTES = LAYERS * 64 * KV_WORD_BYTES
EXPECTED = {
    "a4131": ("kvzap-route-a4131-payload-organization-envelope-1.0", "ba6ec8291d213317e953dd0ac3a050524cf10a327705c6390fe652531a98950c"),
    "a4133": ("kvzap-route-a4133-packed-kv-hbm-realization-1.0", "fea9780d44238f5128008793a12e605e411a95355eaa44e4ad6f71f8b6a735f1"),
    "a4135": ("kvzap-route-a4135-target-payload-service-cost-1.0", "8a3c07255d8e6382807701b437935c89207b60065df5d671dacad0b8cfb7a502"),
    "a4140": ("kvzap-route-a4140-workload-aligned-metadata-cost-1.0", "3d3cc52eade09c20ed305159d78b7bc43673db0072a4d1b9bc211bd061ae8034"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.14.1 evidence-classified accounted Route-A ledger and omitted-cost budget; not measured energy/PPA/latency, architecture signoff, or RTL.")
    for label in EXPECTED:
        parser.add_argument(f"--{label.replace('_', '-')}-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate exact bindings and ledger invariants without output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def saving_fraction(route: float, full: float) -> float | None:
    return 1.0 - route / full if full else None


def energy_budget(full_pj: float, route_payload_pj: float, route_m2_pj: float, positions: int) -> dict[str, Any]:
    route_total = route_payload_pj + route_m2_pj
    budget = full_pj - route_total
    return {
        "full_accounted_dynamic_energy_pj": full_pj,
        "route_payload_p3_and_source_buffer_accounted_dynamic_energy_pj": route_payload_pj,
        "route_m2_control_entry_dynamic_energy_pj": route_m2_pj,
        "route_accounted_dynamic_energy_pj": route_total,
        "route_over_full_accounted_dynamic_energy_ratio": ratio(route_total, full_pj),
        "accounted_dynamic_energy_saving_fraction": saving_fraction(route_total, full_pj),
        "differential_omitted_cost_budget_pj_per_request": budget,
        "differential_omitted_cost_budget_pj_per_observed_attention_position": ratio(budget, positions),
        "differential_omitted_cost_budget_fraction_of_full_accounted_energy": ratio(budget, full_pj),
        "sign_condition": "Route-A retains an accounted energy advantage exactly when route_unestimated_dynamic_energy - full_unestimated_dynamic_energy is less than this budget.",
    }


def read_exact(path: Path, label: str) -> dict[str, Any]:
    schema, digest = EXPECTED[label]
    if not path.is_file() or sha256_file(path) != digest:
        raise ValueError(f"A4.14.1 requires exact accepted {label} SHA-256 input")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != schema or report.get("status") != "complete":
        raise ValueError(f"{label} is incomplete or schema-incompatible")
    return report


def rows_by_workload(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {str(row["workload"]): row for row in report.get("workload_rows", [])}
    if set(rows) != set(WORKLOADS):
        raise ValueError("workload coverage changed")
    return rows


def validate_bindings(reports: dict[str, dict[str, Any]]) -> None:
    a4131, a4133, a4135, a4140 = (reports[name] for name in ("a4131", "a4133", "a4135", "a4140"))
    if a4135.get("input_artifacts", {}).get("a4133_report", {}).get("sha256") != EXPECTED["a4133"][1]:
        raise ValueError("A4.13.5 does not bind A4.13.3")
    left = {key: value.get("sha256") for key, value in a4131.get("input_artifacts", {}).items() if key.endswith("_manifest")}
    right = {key: value.get("sha256") for key, value in a4133.get("input_artifacts", {}).items() if key.endswith("_manifest")}
    if left != right or set(left) != {f"{name}_manifest" for name in WORKLOADS}:
        raise ValueError("A4.13.1 capacity and A4.13.3 traffic are not manifest-aligned")
    guards_4140 = ("all_workload_m2_replays_drain_losslessly", "m2_fixed_area_not_repeated_per_workload", "metadata_and_payload_service_coordinates_not_summed", "only_complete_m2_mapping_replayed_m1_rejected_m3_unestimated")
    if not all(a4140.get("semantic_guards", {}).get(key) is True for key in guards_4140):
        raise ValueError("A4.14.0 M2 guards are incomplete")
    guards_4135 = ("fair_full_kv_and_route_a_legal_gqa_paths_only", "only_s1_s2_source_buffers", "only_one_factor_bandwidth_sensitivity", "p3_admission_mapping_carried_without_payload_organization_change", "no_pruning_admission_queue_execution_scheduler_or_metadata_change")
    if not all(a4135.get("semantic_guards", {}).get(key) is True for key in guards_4135):
        raise ValueError("A4.13.5 payload guards are incomplete")


def materialized_path(item: dict[str, Any], label: str) -> Path:
    path = Path(item["materialized_copy"])
    if not path.is_file() or sha256_file(path) != item["sha256"]:
        raise ValueError(f"materialized {label} is missing or has a hash mismatch")
    return path


def final_tokens_from_lifecycle(a4140: dict[str, Any], workload: str) -> int:
    path = materialized_path(a4140["input_artifacts"]["lifecycle"][workload]["trace"], f"{workload} lifecycle trace")
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle if line.strip()]
    final = {int(event["layer"]): int(event["end_position"]) for event in events}
    if sorted(final) != list(range(LAYERS)) or len(set(final.values())) != 1:
        raise ValueError(f"{workload}: no common full-KV final extent in lifecycle trace")
    return next(iter(final.values())) + 1


def logical_cold(a4140: dict[str, Any], workload: str) -> dict[str, Any]:
    path = materialized_path(a4140["input_artifacts"]["reports"]["a4112b"], "A4.11.2b")
    report = json.loads(path.read_text(encoding="utf-8"))
    direct = next(row["direct_software_observation"] for row in report["workloads"] if row["workload"] == workload)
    kept, dropped = int(direct["matured_kept_tokens"]), int(direct["matured_dropped_tokens"])
    return {
        "matured_kept_tokens": kept,
        "matured_dropped_tokens": dropped,
        "matured_removed_fraction": ratio(dropped, kept + dropped),
        "full_logical_cold_payload_bytes": (kept + dropped) * KV_WORD_BYTES,
        "route_a_logical_cold_payload_bytes": kept * KV_WORD_BYTES,
        "evidence_class": "trace-derived lifecycle plus deterministic byte accounting",
    }


def inferred_trace_end_pending_residual(lifecycle: dict[str, Any], workload: str) -> int:
    """Prove final packed publication instead of inventing a missing trace field.

    A4.13.1 reports the total admitted retained tokens and its final packed
    state, but does not expose a field literally named ``trace_end_residual``.
    Equality is therefore a deterministic finalization check: every admitted
    retained token is published in a packed page and no logical pending token
    remains.  It is not claimed to be a separately instrumented event.
    """
    admitted = int(lifecycle["admitted_retained_tokens"])
    packed = int(lifecycle["final_packed_state"]["packed_tokens"])
    if packed > admitted:
        raise ValueError(f"{workload}: packed tokens exceed admitted retained tokens")
    return admitted - packed


def capacity_chain(a4131_row: dict[str, Any], a4140: dict[str, Any], workload: str) -> dict[str, Any]:
    page = a4131_row["deterministic_page_accounting"]
    lifecycle = a4131_row["direct_software_lifecycle"]
    inferred_residual = inferred_trace_end_pending_residual(lifecycle, workload)
    if inferred_residual != 0:
        raise ValueError(f"{workload}: final packed state leaves {inferred_residual} admitted tokens unpublished")
    packed_payload = int(page["final_packed_page_payload_capacity_bytes"])
    sidecar = int(page["final_page_slot_position_sidecar_capacity_bytes"])
    hot = LAYERS * KV_HEADS * WINDOW * KV_WORD_BYTES
    full = final_tokens_from_lifecycle(a4140, workload) * LAYERS * KV_HEADS * KV_WORD_BYTES
    route = hot + packed_payload + sidecar
    return {
        "logical_matured_cold": logical_cold(a4140, workload),
        "packed_cold_resident": {
            "packed_payload_capacity_bytes": packed_payload,
            "packed_position_sidecar_capacity_bytes": sidecar,
            "packed_payload_utilization": page["final_packed_page_payload_utilization"],
            "tail_capacity_amplification": page["final_packed_page_capacity_amplification"],
            "evidence_class": "deterministic page accounting",
        },
        "trace_end_finalization_check": {
            "inferred_pending_residual_tokens": inferred_residual,
            "basis": "A4.13.1 admitted_retained_tokens minus final_packed_state.packed_tokens; not a separately recorded trace-end event",
            "evidence_class": "deterministic accounting over directly observed lifecycle totals",
        },
        "final_resident": {
            "full_kv_payload_bytes": full,
            "route_a_hot_payload_bytes_common": hot,
            "route_a_packed_payload_capacity_bytes": packed_payload,
            "route_a_position_sidecar_capacity_bytes": sidecar,
            "route_a_total_resident_bytes_including_sidecar": route,
            "route_a_over_full_resident_ratio": ratio(route, full),
            "resident_saving_fraction": saving_fraction(route, full),
            "full_kv_payload_bytes_per_final_token": ratio(full, final_tokens_from_lifecycle(a4140, workload)),
            "route_a_total_resident_bytes_per_final_token": ratio(route, final_tokens_from_lifecycle(a4140, workload)),
            "boundary": "Scalar lifecycle plus fixed page accounting, not physical allocation or HBM capacity measurement.",
            "evidence_class": "trace-derived scalar extent plus deterministic accounting",
        },
    }


def observed_positions(a4133_row: dict[str, Any]) -> int:
    phase_rows = a4133_row["all_observed_phases_aggregate"]["fair_full_kv_legal_gqa_reuse"]["per_observed_attention_position"]
    values = [int(row["observed_positions"]) for row in phase_rows.values()]
    if not values or any(value <= 0 for value in values):
        raise ValueError("observed attention position count is invalid")
    return sum(values)


def profile_rows(a4135_row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {str(row["profile"]["profile_id"]): row for row in a4135_row["profile_rows"]}
    if set(rows) != {PRIMARY, SENSITIVITY}:
        raise ValueError("A4.13.5 fixed target profile set changed")
    return rows


def payload_profile(row: dict[str, Any], metadata: dict[str, Any], positions: int) -> dict[str, Any]:
    candidates = row["source_buffer_candidates"]
    if set(candidates) != {"S1_one_32KiB_page_source_buffer", S2}:
        raise ValueError("unregistered source buffer candidate")
    full = candidates[S2]["full_kv_legal_gqa_reuse"]
    route = candidates[S2]["route_a_packed_legal_gqa_reuse"]
    full_hbm, route_hbm, p3 = full["attention_hbm_service"], route["attention_hbm_service"], route["p3_admission_service"]
    p3_bytes = int(p3["hbm_pending_read"]["declared_bytes"]) + int(p3["hbm_pending_plus_packed_writes"]["declared_bytes"])
    p3_tx = int(p3["hbm_pending_read"]["modeled_transfer_transactions"]) + int(p3["hbm_pending_plus_packed_writes"]["modeled_transfer_transactions"])
    full_bytes, route_bytes = int(full_hbm["declared_bytes"]), int(route_hbm["declared_bytes"]) + p3_bytes
    full_tx, route_tx = int(full_hbm["modeled_transfer_transactions"]), int(route_hbm["modeled_transfer_transactions"]) + p3_tx
    fair = row["fair_route_a_vs_full_using_s2"]
    m2 = float(metadata["m2_declared_metadata_replay"]["estimated_sram_dynamic_energy_pj_excluding_unestimated_registers"])
    budget = energy_budget(float(fair["full_estimated_dynamic_energy_pj_excluding_unestimated_terms"]), float(fair["route_total_estimated_dynamic_energy_pj_excluding_unestimated_terms"]), m2, positions)
    return {
        "profile": row["profile"],
        "payload_hbm": {
            "full_fair_bytes": full_bytes,
            "route_attention_bytes": int(route_hbm["declared_bytes"]),
            "route_p3_admission_bytes": p3_bytes,
            "route_total_bytes_including_p3": route_bytes,
            "route_over_full_byte_ratio": ratio(route_bytes, full_bytes),
            "route_total_byte_saving_fraction": saving_fraction(route_bytes, full_bytes),
            "full_fair_bytes_per_observed_attention_position": ratio(full_bytes, positions),
            "route_total_bytes_per_observed_attention_position": ratio(route_bytes, positions),
            "full_fair_modeled_transactions": full_tx,
            "route_total_modeled_transactions_including_p3": route_tx,
            "route_over_full_transaction_ratio": ratio(route_tx, full_tx),
            "full_fair_transactions_per_observed_attention_position": ratio(full_tx, positions),
            "route_total_transactions_per_observed_attention_position": ratio(route_tx, positions),
            "evidence_class": "deterministic accounting mapped to declared target-profile transaction granule",
        },
        "service_coordinates": {
            "payload_full_hbm_service_cycles": int(fair["full_hbm_service_cycles"]),
            "payload_route_hbm_service_cycles_including_p3": int(fair["route_total_hbm_service_cycles_including_p3_admission"]),
            "payload_route_over_full_service_cycle_ratio": ratio(int(fair["route_total_hbm_service_cycles_including_p3_admission"]), int(fair["full_hbm_service_cycles"])),
            "payload_full_service_cycles_per_observed_attention_position": ratio(int(fair["full_hbm_service_cycles"]), positions),
            "payload_route_service_cycles_per_observed_attention_position": ratio(int(fair["route_total_hbm_service_cycles_including_p3_admission"]), positions),
            "metadata_m2_service_coordinate": int(metadata["m2_declared_metadata_replay"]["service_model_cycles_elapsed"]),
            "non_addition_rule": "Payload and metadata service coordinates have no common clock/dependency/overlap model and are not summed.",
            "evidence_class": "separate declared payload and metadata models",
        },
        "dynamic_energy": {
            **budget,
            "full_source_buffer_dynamic_energy_pj": float(full["source_buffer"]["estimated_cacti_source_buffer_dynamic_energy_pj"]),
            "route_source_buffer_dynamic_energy_pj": float(route["source_buffer"]["estimated_cacti_source_buffer_dynamic_energy_pj"]),
            "evidence_class": "declared HBM pJ/B plus CACTI source-buffer and explicit M2 control-entry proxy; not measured energy",
        },
        "engineering_hbm_gate": {"threshold_route_over_full_max": 0.5, "passed": route_bytes <= 0.5 * full_bytes, "boundary": "Two is an engineering omitted-cost margin, not a natural-law threshold."},
    }


def infrastructure(a4135: dict[str, Any], a4140: dict[str, Any]) -> dict[str, Any]:
    s2 = a4135["cacti_source_buffer_proxies"][S2]
    return {
        "common_baseline_infrastructure": [{"name": S2, "public_cacti_proxy_area_mm2": float(s2["aggregate_data_array_area_mm2"]), "payload_capacity_bytes": 65536, "rule": "Common Full-KV/Route-A legal-GQA source-buffer infrastructure; fixed area is not Route-A incremental area.", "evidence_class": "public CACTI proxy"}],
        "route_a_specific_fixed_provision": [{"name": "M2_metadata_engine", **a4140["fixed_provisioned_m2_proxy"], "evidence_class": "public CACTI proxy"}],
        "route_a_specific_provision_envelopes_unestimated": [
            {"name": "P3_one_page_per_layer_staging", "capacity_bytes": P3_STAGING_BYTES, "rule": "Fixed P3 staging envelope; no macro/area/dynamic access mapping.", "evidence_class": "deterministic accounting; physical realization unestimated"},
            {"name": "packed_sidecar_page_management", "rule": "Per-workload sidecar capacity is reported; latch/page-management physical cost is unestimated.", "evidence_class": "deterministic accounting plus unestimated implementation"},
            {"name": "partial_softmax_merge", "rule": "Pipeline-local partial interface remains unimplemented; RF/SRAM/spill, arithmetic and interconnect are unestimated.", "evidence_class": "unestimated"},
        ],
    }


def materialize(output: Path, inputs: dict[str, Path]) -> dict[str, dict[str, str]]:
    folder = output / "input_artifacts"; folder.mkdir()
    copied = {}
    for label, path in inputs.items():
        target = folder / f"{label}_source.json"; shutil.copyfile(path, target)
        if sha256_file(target) != EXPECTED[label][1]:
            raise AssertionError("input changed while materializing")
        copied[label] = {"source_path": str(path), "materialized_copy": str(target), "sha256": sha256_file(target)}
    return copied


def main() -> None:
    args = parse_args()
    reports = {label: read_exact(getattr(args, f"{label}_report"), label) for label in EXPECTED}
    validate_bindings(reports)
    a4131, a4133, a4135, a4140 = (rows_by_workload(reports[name]) for name in ("a4131", "a4133", "a4135", "a4140"))
    rows = []
    for workload in WORKLOADS:
        positions = observed_positions(a4133[workload])
        profiles = [payload_profile(item, a4140[workload], positions) for item in profile_rows(a4135[workload]).values()]
        rows.append({"workload": workload, "observed_attention_positions": positions, "benefit_retention_chain": capacity_chain(a4131[workload], reports["a4140"], workload), "profile_rows": profiles, "unestimated_differential_dynamic_costs": ["M2 pooled queue/staging SRAM dynamic accesses lack an explicit A4.14.0 access map.", "P3 staging dynamic energy and physical macro area.", "sidecar latch/page management, partial-state RF/SRAM/spill, merge arithmetic/interconnect.", "HBM controller/PHY/interconnect, clock/wire/leakage and HBM physical area."], "evidence_classes": {"trace_derived": ["lifecycle extent and matured cold counts"], "deterministic_accounting": ["resident bytes, P3 bytes and fair transferred-byte ratios"], "modeled": ["separate payload and metadata service coordinates"], "cacti_proxy": ["S2/M2 area and explicit access energy"], "unestimated": ["listed differential hardware terms"]}})
    hbm_pass = all(profile["engineering_hbm_gate"]["passed"] for row in rows for profile in row["profile_rows"])
    budget_pass = all(profile["dynamic_energy"]["differential_omitted_cost_budget_pj_per_request"] > 0 for row in rows for profile in row["profile_rows"])
    disposition = "conditional_go_to_architecture_spec_pending_omitted_cost_budget" if hbm_pass and budget_pass else "no_go_under_preregistered_accounted_ledger_gates"
    if args.preflight_only:
        print(f"A4.14.1 preflight passed: exact bindings, common/incremental cost separation, no-cycle-addition rule, HBM gate={hbm_pass}, positive-budget={budget_pass}; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    inputs = {label: getattr(args, f"{label}_report") for label in EXPECTED}
    artifacts = materialize(args.output_dir, inputs)
    config = {"stage": "A4.14.1", "workloads": list(WORKLOADS), "profiles": [PRIMARY, SENSITIVITY], "common_fixed_infrastructure": S2, "route_a_incremental_metadata_candidate": "M2_replicated_or_duplicated_control_storage", "engineering_hbm_gate": "route_total_hbm_bytes_including_p3 <= 0.5 * full_fair_hbm_bytes", "cycle_rule": "payload and metadata service coordinates are separate and never added"}
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(),
        "execution_classification": "evidence-classified ledger joining trace-derived/deterministic payload accounting, declared service profiles, public-CACTI proxies and explicit unestimated terms; not measured energy/PPA/latency, architecture signoff, or RTL evidence",
        "config": config, "config_hash": stable_hash(config), "input_artifacts": artifacts, "fixed_infrastructure": infrastructure(reports["a4135"], reports["a4140"]), "workload_rows": rows,
        "decision": {"disposition": disposition, "engineering_hbm_gate_all_profiles_and_workloads": hbm_pass, "positive_differential_omitted_cost_budget_all_profiles_and_workloads": budget_pass, "rule": "Conditional go is bounded by the reported differential omitted-cost budget. It does not assert omitted costs are zero or establish physical implementation readiness.", "next_step_if_conditional_go": "Freeze architecture specification with common/incremental interface, omitted-cost budget, no-cycle-addition rule and fill-stall risk; do not create another A4.14 DSE variant."},
        "semantic_guards": {"exact_a4131_a4133_a4135_a4140_inputs_bound": True, "a4131_capacity_and_a4133_traffic_bind_same_workload_manifests": True, "fair_legal_gqa_full_and_route_paths_only": True, "s2_fixed_area_classified_common_not_route_incremental": True, "m2_fixed_area_classified_once_not_per_workload": True, "m2_queue_staging_dynamic_access_explicitly_unestimated": True, "p3_partial_merge_controller_and_interconnect_costs_not_invented": True, "all_ratios_report_absolute_normalized_and_relative_values": True, "payload_and_metadata_service_coordinates_not_summed": True, "no_pruning_admission_queue_execution_scheduler_or_payload_variant_introduced": True, "no_measured_energy_ppa_latency_architecture_or_rtl_claim": True},
        "boundaries": ["The ledger combines declared HBM pJ/B with public-CACTI pJ/access only as an accounted dynamic-energy proxy; it is not technology-coherent measured energy.", "S2 fixed area is common infrastructure. Route-A M2 fixed area and unestimated P3/merge/control provisions are separate.", "The omitted-cost budget constrains differential unestimated dynamic energy only; it is not a model of omitted modules.", "Payload and metadata service coordinates have no common clock/controller/overlap schedule and are never added into latency or throughput."],
    }
    path = args.output_dir / "a4141_accounted_net_benefit_ledger_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.14.1 complete: {path} sha256={sha256_file(path)} workloads={len(rows)} disposition={disposition}")


if __name__ == "__main__":
    main()
