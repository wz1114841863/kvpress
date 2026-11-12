"""A4.14.1 declared cost accounting, not measured system energy or PPA."""
from __future__ import annotations

from typing import Any

WORKLOADS = ("retrieval", "summarization", "reasoning")

S2 = "S2_two_32KiB_ping_pong_page_source_buffers"

PRIMARY = "primary_256B_per_model_cycle"

SENSITIVITY = "sensitivity_128B_per_model_cycle"

WINDOW, LAYERS, KV_HEADS, KV_WORD_BYTES = 128, 36, 8, 512

P3_STAGING_BYTES = LAYERS * 64 * KV_WORD_BYTES

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
