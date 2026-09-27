#!/usr/bin/env python3
"""A4.13.5 declared target-profile payload service/cost DSE; pre-RTL only."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hardware.route_a.mem.cacti_runner import CactiMacroRunner, MacroSpec
from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4135-target-payload-service-cost-1.0"
EXPECTED_A4133 = ("kvzap-route-a4133-packed-kv-hbm-realization-1.0", "fea9780d44238f5128008793a12e605e411a95355eaa44e4ad6f71f8b6a735f1")
EXPECTED_A4134 = ("kvzap-route-a4134-page-source-reuse-interface-1.0", "2390958f801c63b7a54e725106b9e75bd36de8950b733ab9bac9d4ac2ee94597")
WORKLOADS = ("retrieval", "summarization", "reasoning")
PAGE_BYTES, SIDECAR_BYTES, INTERNAL_BEAT_BYTES, PAGE_BEATS = 32768, 512, 256, 128


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.13.5 declared target-profile HBM/source-buffer service and cost DSE; not measured HBM, PDK, physical timing, throughput, architecture, or RTL.")
    parser.add_argument("--a4133-report", type=Path, required=True)
    parser.add_argument("--a4134-report", type=Path, required=True)
    parser.add_argument("--profile-file", type=Path, default=Path("hardware/route_a/payload/a4135_target_profiles.json"))
    parser.add_argument("--cacti-toolchain-root", type=Path, default=Path("hardware/route_a/mem/cacti_toolchain"))
    parser.add_argument("--preflight-only", action="store_true", help="Validate exact reports, profile and locked CACTI toolchain without output or CACTI runs.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def ceil_div(value: int, divisor: int) -> int:
    return (value + divisor - 1) // divisor


def required_report(path: Path, expected: tuple[str, str], label: str) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != expected[1]:
        raise ValueError(f"{label} requires exact accepted SHA-256 input")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != expected[0] or report.get("status") != "complete":
        raise ValueError(f"{label} report is incomplete or incompatible")
    return report


def read_profiles(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    common, profiles = data.get("common", {}), data.get("profiles", [])
    required = {"modeled_hbm_transfer_transaction_bytes", "read_startup_model_cycles_per_request", "write_startup_model_cycles_per_declared_p3_batch", "hbm_read_energy_pj_per_byte", "hbm_write_energy_pj_per_byte", "source_buffer_consumer_internal_256B_beats_per_model_cycle", "source_buffer_cacti_proxy_node_um", "source_buffer_payload_depth_entries", "source_buffer_payload_width_bits"}
    if data.get("schema_version") != "route-a4135-payload-target-service-profiles-1.0" or not required <= set(common) or len(profiles) != 2:
        raise ValueError("A4.13.5 profile file is incompatible")
    if common["modeled_hbm_transfer_transaction_bytes"] <= 0 or PAGE_BYTES % common["modeled_hbm_transfer_transaction_bytes"] or SIDECAR_BYTES % common["modeled_hbm_transfer_transaction_bytes"] or common["source_buffer_payload_depth_entries"] * common["source_buffer_payload_width_bits"] // 8 != PAGE_BYTES:
        raise ValueError("profile transaction or source-buffer shape incompatible with frozen page")
    primary, sensitivity = profiles
    if primary.get("profile_id") != "primary_256B_per_model_cycle" or sensitivity.get("profile_id") != "sensitivity_128B_per_model_cycle" or primary.get("sustained_modeled_hbm_transfer_transactions_per_cycle") != 4 or sensitivity.get("sustained_modeled_hbm_transfer_transactions_per_cycle") != 2:
        raise ValueError("A4.13.5 allows only the fixed one-factor bandwidth sensitivity")
    return common, profiles


def validate(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], CactiMacroRunner]:
    a4133 = required_report(args.a4133_report, EXPECTED_A4133, "A4.13.3")
    a4134 = required_report(args.a4134_report, EXPECTED_A4134, "A4.13.4")
    if a4134.get("input_artifacts", {}).get("a4133_report", {}).get("sha256") != EXPECTED_A4133[1]:
        raise ValueError("A4.13.4 is not bound to accepted A4.13.3")
    if [row.get("workload") for row in a4134.get("workload_rows", [])] != list(WORKLOADS):
        raise ValueError("A4.13.4 workloads changed")
    common, profiles = read_profiles(args.profile_file)
    runner = CactiMacroRunner(args.cacti_toolchain_root, common["source_buffer_cacti_proxy_node_um"])
    runner.validate_toolchain()
    return a4133, a4134, common, profiles, runner


def actions(row: dict[str, Any], path: str) -> dict[str, int]:
    return row["all_observed_phases_aggregate"][path]["action_counts"]


def hbm_service(bytes_count: int, request_count: int, profile: dict[str, Any], common: dict[str, Any], write: bool = False) -> dict[str, Any]:
    tx_bytes = common["modeled_hbm_transfer_transaction_bytes"]
    transactions = ceil_div(bytes_count, tx_bytes)
    rate = profile["sustained_modeled_hbm_transfer_transactions_per_cycle"]
    startup = common["write_startup_model_cycles_per_declared_p3_batch"] if write else common["read_startup_model_cycles_per_request"]
    cycles = request_count * startup + ceil_div(transactions, rate) if bytes_count else 0
    energy = bytes_count * (common["hbm_write_energy_pj_per_byte"] if write else common["hbm_read_energy_pj_per_byte"])
    return {"declared_bytes": bytes_count, "modeled_transfer_transactions": transactions, "declared_request_or_batch_count": request_count, "modeled_service_cycles": cycles, "declared_dynamic_energy_pj": energy}


def source_buffer_model(page_fills: int, macro: dict[str, Any], profile: dict[str, Any], common: dict[str, Any], candidate: str, include_position_sidecar: bool = True) -> dict[str, Any]:
    rate = profile["sustained_modeled_hbm_transfer_transactions_per_cycle"]
    tx_bytes = common["modeled_hbm_transfer_transaction_bytes"]
    fill_bytes = PAGE_BYTES + (SIDECAR_BYTES if include_position_sidecar else 0)
    fill = common["read_startup_model_cycles_per_request"] + ceil_div(fill_bytes, tx_bytes * rate)
    consume = ceil_div(PAGE_BEATS, common["source_buffer_consumer_internal_256B_beats_per_model_cycle"])
    if candidate.startswith("S1"):
        total = page_fills * (fill + consume)
        stalls = page_fills * fill
        capacity = PAGE_BYTES
        overlap = False
    else:
        total = fill + max(0, page_fills - 1) * max(fill, consume) + consume if page_fills else 0
        stalls = total - page_fills * consume
        capacity = 2 * PAGE_BYTES
        overlap = True
    accesses = page_fills * PAGE_BEATS
    metrics = macro["per_instance_cacti_proxy"]
    energy = accesses * (metrics["dynamic_read_energy_pj"] + metrics["dynamic_write_energy_pj"])
    return {
        "candidate": candidate, "source_buffer_payload_capacity_bytes": capacity, "cacti_proxy_area_mm2": macro["aggregate_data_array_area_mm2"],
        "payload_fill_write_accesses": accesses, "multicast_payload_read_accesses": accesses,
        "estimated_cacti_source_buffer_dynamic_energy_pj": energy,
        "per_page_T_fill_model_cycles": fill, "position_sidecar_included_in_page_fill": include_position_sidecar, "per_page_T_consume_model_cycles": consume,
        "s2_fully_hides_next_fill_condition": "T_consume >= T_fill", "condition_holds_under_profile": consume >= fill,
        "warmup_drain_inclusive_source_stream_model_cycles": total, "modeled_consumer_fill_stall_cycles": stalls,
        "steady_state_fill_engine_utilization_fraction": fill / max(fill, consume), "steady_state_consumer_utilization_fraction": consume / max(fill, consume),
        "logical_page_slot_utilization_when_active": 1.0, "time_occupancy_boundary": "No physical request issue order exists in the software trace; only per-stream S1/S2 service formulas are modeled.", "overlap_enabled": overlap,
    }


def p3_terms(a4133_row: dict[str, Any], profile: dict[str, Any], common: dict[str, Any]) -> dict[str, Any]:
    move = a4133_row["route_a_admission_and_merge_terms"]["p3_carried_admission_mapping"]["declared_admission_movement"]
    batches = int(move["staging_fill_chunks"])
    reads = hbm_service(int(move["hbm_pending_read_bytes"]), batches, profile, common)
    writes = hbm_service(int(move["hbm_pending_write_bytes"]) + int(move["hbm_packed_write_bytes"]), 2 * batches, profile, common, write=True)
    return {"declared_p3_batch_proxy_count": batches, "hbm_pending_read": reads, "hbm_pending_plus_packed_writes": writes, "total_declared_hbm_service_cycles": reads["modeled_service_cycles"] + writes["modeled_service_cycles"], "total_declared_hbm_dynamic_energy_pj": reads["declared_dynamic_energy_pj"] + writes["declared_dynamic_energy_pj"], "boundary": "P3 batches are A4.13.1 staging-fill chunks, not observed HBM request issue groups or DMA commands."}


def path_row(action: dict[str, int], a4133_row: dict[str, Any], profile: dict[str, Any], common: dict[str, Any], macro: dict[str, Any], candidate: str, route: bool) -> dict[str, Any]:
    if route:
        page_fills = action["packed_payload_fill_actions"]
        attention_bytes = action["packed_payload_internal_interface_beats"] * INTERNAL_BEAT_BYTES + action["packed_sidecar_internal_interface_beats"] * INTERNAL_BEAT_BYTES + action["hot_direct_source_internal_interface_beats"] * INTERNAL_BEAT_BYTES + action["pending_direct_source_internal_interface_beats"] * INTERNAL_BEAT_BYTES
        direct_requests = action["hot_direct_source_delivery_actions"] + action["pending_direct_source_delivery_actions"]
        attention_requests = page_fills + direct_requests
        admission = p3_terms(a4133_row, profile, common)
    else:
        page_fills = action["full_kv_payload_fill_actions"]
        attention_bytes = action["full_kv_payload_internal_interface_beats"] * INTERNAL_BEAT_BYTES
        attention_requests = page_fills
        admission = None
    attention = hbm_service(attention_bytes, attention_requests, profile, common)
    buffer = source_buffer_model(page_fills, macro, profile, common, candidate, include_position_sidecar=route)
    total_cycles = attention["modeled_service_cycles"] + (admission["total_declared_hbm_service_cycles"] if admission else 0)
    total_energy = attention["declared_dynamic_energy_pj"] + buffer["estimated_cacti_source_buffer_dynamic_energy_pj"] + (admission["total_declared_hbm_dynamic_energy_pj"] if admission else 0)
    return {"attention_hbm_service": attention, "source_buffer": buffer, "p3_admission_service": admission, "declared_payload_dynamic_energy_pj_excluding_partial_sidecar_latches_attention_arithmetic_and_hbm_area": total_energy, "declared_hbm_service_cycles_including_p3_admission": total_cycles}


def materialize(output: Path, inputs: dict[str, Path]) -> dict[str, dict[str, str]]:
    folder = output / "input_artifacts"; folder.mkdir(); result = {}
    for label, source in inputs.items():
        target = folder / f"{label}_{source.name}"; shutil.copyfile(source, target)
        result[label] = {"source_path": str(source), "materialized_copy": str(target), "sha256": sha256_file(target)}
    return result


def main() -> None:
    args = parse_args(); a4133, a4134, common, profiles, runner = validate(args)
    if args.preflight_only:
        print("A4.13.5 preflight passed: exact A4.13.3/A4.13.4 bindings, fixed two-profile rule, and locked CACTI toolchain validate; no output created."); return
    if args.output_dir.exists(): raise FileExistsError(args.output_dir)
    args.output_dir.mkdir(parents=True)
    artifacts = materialize(args.output_dir, {"a4133_report": args.a4133_report, "a4134_report": args.a4134_report, "target_profiles": args.profile_file})
    macro_dir = args.output_dir / "source_buffer_cacti_proxies"
    specs = {"S1_one_32KiB_page_source_buffer": MacroSpec("a4135_source_buffer_s1", 128, 2048, instances=1, readwrite_ports=1, role="A4.13.5 one-page source-buffer public CACTI proxy"), "S2_two_32KiB_ping_pong_page_source_buffers": MacroSpec("a4135_source_buffer_s2", 128, 2048, instances=2, readwrite_ports=1, role="A4.13.5 two separate ping-pong source-buffer public CACTI proxy")}
    macros = {name: runner.run(spec, macro_dir / name) for name, spec in specs.items()}
    old = {row["workload"]: row for row in a4133["workload_rows"]}; rows = []
    for work in a4134["workload_rows"]:
        name = work["workload"]; full_actions = actions(work, "full_kv_legal_gqa_actions"); route_actions = actions(work, "route_a_packed_legal_gqa_actions")
        profile_rows = []
        for profile in profiles:
            candidates = {candidate: {"full_kv_legal_gqa_reuse": path_row(full_actions, old[name], profile, common, macros[candidate], candidate, False), "route_a_packed_legal_gqa_reuse": path_row(route_actions, old[name], profile, common, macros[candidate], candidate, True)} for candidate in specs}
            s1, s2 = candidates["S1_one_32KiB_page_source_buffer"], candidates["S2_two_32KiB_ping_pong_page_source_buffers"]
            full, route = s2["full_kv_legal_gqa_reuse"], s2["route_a_packed_legal_gqa_reuse"]
            profile_rows.append({"profile": profile, "source_buffer_candidates": candidates, "fair_route_a_vs_full_using_s2": {"attention_hbm_transaction_ratio": route["attention_hbm_service"]["modeled_transfer_transactions"] / full["attention_hbm_service"]["modeled_transfer_transactions"], "attention_hbm_byte_ratio": route["attention_hbm_service"]["declared_bytes"] / full["attention_hbm_service"]["declared_bytes"], "attention_hbm_service_cycle_ratio": route["attention_hbm_service"]["modeled_service_cycles"] / full["attention_hbm_service"]["modeled_service_cycles"], "route_total_hbm_service_cycles_including_p3_admission": route["declared_hbm_service_cycles_including_p3_admission"], "full_hbm_service_cycles": full["declared_hbm_service_cycles_including_p3_admission"], "route_total_estimated_dynamic_energy_pj_excluding_unestimated_terms": route["declared_payload_dynamic_energy_pj_excluding_partial_sidecar_latches_attention_arithmetic_and_hbm_area"], "full_estimated_dynamic_energy_pj_excluding_unestimated_terms": full["declared_payload_dynamic_energy_pj_excluding_partial_sidecar_latches_attention_arithmetic_and_hbm_area"]}})
        rows.append({"workload": name, "a4134_action_binding": {"full_page_fills": full_actions["full_kv_payload_fill_actions"], "route_packed_page_fills": route_actions["packed_payload_fill_actions"], "route_partial_state_actions": {key: route_actions.get(key, 0) for key in ("partial_state_initialize_actions", "partial_state_record_update_actions", "partial_state_finalize_actions", "cross_source_online_merge_actions")}}, "profile_rows": profile_rows})
    config = {"stage": "A4.13.5", "comparison": ["full_kv_legal_gqa_reuse", "route_a_packed_legal_gqa_reuse"], "source_buffer_candidates": list(specs), "profile_count": 2, "one_factor_sensitivity": "sustained_modeled_hbm_transfer_transactions_per_cycle", "partial_state_status": "pipeline-local action counts retained; physical RF/SRAM implementation remains unestimated"}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "execution_classification": "declared target-service profile replay plus public-CACTI source-buffer proxy; not measured HBM/controller traffic, bandwidth, latency, energy, PDK, physical macro, architecture, or RTL evidence", "config": config, "config_hash": stable_hash(config), "input_artifacts": artifacts, "cacti_source_buffer_proxies": macros, "workload_rows": rows, "evidence_classes": {"trace_bound_action_counts": ["A4.13.4 fair Full-KV/Route-A page, direct-source, partial and merge actions"], "declared_target_profile": ["64-B modeled HBM transaction, startup/service cycles, bandwidth sensitivity, HBM pJ/B coefficients"], "public_cacti_proxy_estimate": ["32KiB 1RW source-buffer data-array area and per-access pJ"], "unestimated": ["partial-state RF/SRAM/spill, sidecar latch, attention arithmetic, HBM physical area, controller/interconnect and physical timing"]}, "semantic_guards": {"exact_accepted_a4133_and_a4134_bound": True, "fair_full_kv_and_route_a_legal_gqa_paths_only": True, "only_s1_s2_source_buffers": True, "only_one_factor_bandwidth_sensitivity": True, "source_buffer_multicast_charges_one_read_per_payload_beat_not_four": True, "packed_page_release_and_partial_state_contract_inherited_unchanged": True, "p3_admission_mapping_carried_without_payload_organization_change": True, "no_pruning_admission_queue_execution_scheduler_or_metadata_change": True, "no_measured_hbm_or_physical_implementation_claim": True}, "boundaries": ["Modeled HBM transfer transactions are profile granules, not native HBM protocol transactions or bursts.", "Model cycles are declared target-service coordinates, not measured latency/throughput or a controller implementation.", "HBM energy is a declared profile coefficient; source-buffer energy/area is public-CACTI proxy only. Partial state, sidecar latch, attention arithmetic, controller/interconnect and HBM area are deliberately unestimated.", "S2 overlap applies only to separate page buffers and remains conditional on T_consume >= T_fill; no trace timestamp establishes a physical issue schedule."]}
    path = args.output_dir / "a4135_target_payload_service_cost_report.json"; path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.13.5 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} workloads={len(rows)} profiles={len(profiles)} source_buffer_candidates=2")


if __name__ == "__main__": main()
