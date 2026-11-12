#!/usr/bin/env python3
"""A4.14.1 evidence-classified Route-A accounted ledger; pre-RTL only.

Capacity/payload service and metadata replay are separate model inputs. The
workload rows join those inputs without treating their service coordinates as
a common latency or presenting the dynamic-energy proxy as measured PPA.
"""
from __future__ import annotations

from kvpress.research.cost import (WORKLOADS, S2, PRIMARY, SENSITIVITY, WINDOW, LAYERS, KV_HEADS, KV_WORD_BYTES, P3_STAGING_BYTES, ratio, saving_fraction, energy_budget, inferred_trace_end_pending_residual, observed_positions, profile_rows, payload_profile, infrastructure)

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










def materialize(output: Path, inputs: dict[str, Path]) -> dict[str, dict[str, str]]:
    folder = output / "input_artifacts"; folder.mkdir()
    copied = {}
    for label, path in inputs.items():
        target = folder / f"{label}_source.json"; shutil.copyfile(path, target)
        if sha256_file(target) != EXPECTED[label][1]:
            raise AssertionError("input changed while materializing")
        copied[label] = {"source_path": str(path), "materialized_copy": str(target), "sha256": sha256_file(target)}
    return copied


def build_workload_rows(reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Join the validated payload and metadata inputs per fixed workload."""
    a4131, a4133, a4135, a4140 = (rows_by_workload(reports[name]) for name in ("a4131", "a4133", "a4135", "a4140"))
    rows = []
    for workload in WORKLOADS:
        positions = observed_positions(a4133[workload])
        profiles = [payload_profile(item, a4140[workload], positions) for item in profile_rows(a4135[workload]).values()]
        rows.append({"workload": workload, "observed_attention_positions": positions, "benefit_retention_chain": capacity_chain(a4131[workload], reports["a4140"], workload), "profile_rows": profiles, "unestimated_differential_dynamic_costs": ["M2 pooled queue/staging SRAM dynamic accesses lack an explicit A4.14.0 access map.", "P3 staging dynamic energy and physical macro area.", "sidecar latch/page management, partial-state RF/SRAM/spill, merge arithmetic/interconnect.", "HBM controller/PHY/interconnect, clock/wire/leakage and HBM physical area."], "evidence_classes": {"trace_derived": ["lifecycle extent and matured cold counts"], "deterministic_accounting": ["resident bytes, P3 bytes and fair transferred-byte ratios"], "modeled": ["separate payload and metadata service coordinates"], "cacti_proxy": ["S2/M2 area and explicit access energy"], "unestimated": ["listed differential hardware terms"]}})
    return rows


def main() -> None:
    args = parse_args()
    reports = {label: read_exact(getattr(args, f"{label}_report"), label) for label in EXPECTED}
    validate_bindings(reports)
    rows = build_workload_rows(reports)
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
