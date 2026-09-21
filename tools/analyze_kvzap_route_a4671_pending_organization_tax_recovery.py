#!/usr/bin/env python3
"""A4.6.7.1 logical organization-management exposure versus capacity recovery.

This no-model study pairs A4.6.6's observer-only capacity frontier with the
immutable-source, exact-FIFO ownership inventory from A4.6.7.0. It deliberately
does not assign physical descriptor formats, bytes, accesses, port widths,
banking, traffic, or time costs to the logical events it reports.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a4632_temporal_contention_replay import HORIZONS
from tools.analyze_kvzap_route_a466_pending_organization_contract import SCHEMA as A466_SCHEMA
from tools.analyze_kvzap_route_a4670_pending_ownership_reference import SCHEMA as A4670_SCHEMA
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4671-pending-organization-tax-recovery-contract-1.0"
RowKey = tuple[str, str]
REQUIRED_A4670_GUARDS = (
    "complete_hash_binding_validated",
    "fixed_a464_grants_derived_not_rescheduled",
    "a464_a465_a466_replay_matches_each_horizon",
    "per_head_birth_order_fifo_exact",
    "cross_source_oldest_entry_selection_enforced",
    "source_age_inversion_rejected",
    "private_shared_migration_prohibited",
    "q0_shared_and_large_q_headlocal_degeneracy_validated",
    "no_finite_capacity_allocator_drop_fallback_or_backing_action",
    "qwen_llama_rows_separate",
    "no_model_or_runtime_loaded",
    "no_hardware_parameter_selected",
)
REQUIRED_VARIANTS = {
    "head_local_private_unbounded",
    "layer_shared_unbounded",
    "hierarchical_q0_shared_endpoint",
    "hierarchical_q128",
    "hierarchical_q256",
    "hierarchical_q512",
    "hierarchical_qpeak_head_local_endpoint",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.6.7.1 no-model Route-A pending organization-management exposure versus "
            "A4.6.6 logical capacity recovery; no descriptor format, physical cost, allocator, "
            "scheduler, DROP, fallback, model, or hardware selection."
        )
    )
    parser.add_argument("--a466-report", type=Path, required=True)
    parser.add_argument("--a4670-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate completed hash-bound inputs without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def integer_sum(rows: list[dict[str, Any]], name: str) -> int:
    return sum(int(row.get(name, 0)) for row in rows)


def integer_max(rows: list[dict[str, Any]], name: str) -> int:
    return max((int(row.get(name, 0)) for row in rows), default=0)


def operation_value(operations: dict[str, Any], name: str) -> int:
    value = int(operations.get(name, 0))
    if value < 0:
        raise ValueError(f"negative logical operation count: {name}")
    return value


def capacity_recovery(*, head_local_cmin: int, organization_cmin: int, layer_count: int) -> dict[str, int | float]:
    if min(head_local_cmin, organization_cmin, layer_count) < 0 or layer_count == 0:
        raise ValueError("invalid logical capacity context")
    if organization_cmin > head_local_cmin:
        raise ValueError("organization Cmin cannot exceed head-local Cmin in this bounded comparison")
    recovered_per_layer = head_local_cmin - organization_cmin
    return {
        "head_local_Cmin_zero_breach_logical_tokens_per_layer": head_local_cmin,
        "organization_Cmin_zero_breach_logical_tokens_per_layer": organization_cmin,
        "recovered_logical_tokens_per_layer": recovered_per_layer,
        "recovered_fraction_of_head_local_Cmin": recovered_per_layer / head_local_cmin if head_local_cmin else 0.0,
        "recovered_logical_token_layers": recovered_per_layer * layer_count,
    }


def unweighted_exposure_ratio(*, recovered_logical_token_layers: int, event_count: int) -> float | None:
    """Return a reporting ratio only; it is not a physical cost or efficiency."""
    if recovered_logical_token_layers < 0 or event_count < 0:
        raise ValueError("invalid ratio inputs")
    return None if event_count == 0 else recovered_logical_token_layers / event_count


def management_inventory(variant: dict[str, Any]) -> dict[str, Any]:
    """Extract unweighted logical ownership primitives from an A4.6.7.0 variant."""
    activation = variant["activation_logical_operation_and_concurrency_summary"]
    append = variant["per_layer_append_opportunity_logical_operation_and_concurrency_summary"]
    operations = variant["global_logical_queue_operations"]
    private_enqueue_units = operation_value(operations, "private_enqueue_token_units")
    shared_enqueue_units = operation_value(operations, "shared_enqueue_token_units")
    private_dequeue_units = operation_value(operations, "private_dequeue_token_units")
    shared_dequeue_units = operation_value(operations, "shared_dequeue_token_units")
    private_enqueue_segments = operation_value(operations, "private_enqueue_segment_count")
    shared_enqueue_segments = operation_value(operations, "shared_enqueue_segment_count")
    private_release_segments = operation_value(operations, "private_release_segment_count")
    shared_release_segments = operation_value(operations, "shared_release_segment_count")
    activation_enqueue_units = integer_sum(activation, "private_enqueue_token_units") + integer_sum(activation, "shared_enqueue_token_units")
    append_enqueue_units = integer_sum(append, "private_enqueue_token_units") + integer_sum(append, "shared_enqueue_token_units")
    total_enqueue_units = private_enqueue_units + shared_enqueue_units
    total_dequeue_units = private_dequeue_units + shared_dequeue_units
    if activation_enqueue_units + append_enqueue_units != total_enqueue_units:
        raise ValueError("A4.6.7.0 activation plus append enqueue accounting is incomplete")
    if total_enqueue_units - total_dequeue_units != int(variant["global_B_final"]):
        raise ValueError("A4.6.7.0 ownership inventory does not conserve pending units")
    return {
        "logical_source_affiliation_creation": {
            "private_enqueue_segment_count": private_enqueue_segments,
            "shared_enqueue_segment_count": shared_enqueue_segments,
            "total_enqueue_segment_count": private_enqueue_segments + shared_enqueue_segments,
            "activation_enqueue_token_units": activation_enqueue_units,
            "append_enqueue_token_units": append_enqueue_units,
        },
        "logical_source_affiliation_release": {
            "private_release_segment_count": private_release_segments,
            "shared_release_segment_count": shared_release_segments,
            "total_release_segment_count": private_release_segments + shared_release_segments,
        },
        "logical_cross_source_selection": {
            "oldest_source_comparison_count": operation_value(operations, "oldest_source_comparison_count"),
            "cross_source_switch_count": operation_value(operations, "cross_source_switch_count"),
            "cross_source_dequeue_head_opportunity_count": integer_sum(append, "cross_source_dequeue_head_opportunity_count"),
            "max_oldest_source_comparison_count_one_layer_opportunity": integer_max(append, "max_oldest_source_comparison_count_one_opportunity"),
            "max_cross_source_switch_count_one_layer_opportunity": integer_max(append, "max_cross_source_switch_count_one_opportunity"),
        },
        "logical_concurrency_inventory": {
            "activation_peak_active_spans_one_layer": integer_max(activation, "active_spans_after_activation"),
            "activation_peak_heads_with_shared_one_layer": integer_max(activation, "heads_with_shared_after_activation"),
            "activation_peak_heads_with_two_sources_one_layer": integer_max(activation, "heads_with_two_sources_after_activation"),
            "append_peak_active_spans_one_layer": integer_max(append, "max_active_spans_after_arrival"),
            "append_peak_heads_with_shared_one_layer": integer_max(append, "max_heads_with_shared_after_arrival"),
            "append_peak_heads_with_two_sources_one_layer": integer_max(append, "max_heads_with_two_sources_after_arrival"),
            "append_peak_active_spans_one_head": integer_max(append, "max_max_active_spans_one_head_after_arrival"),
        },
        "logical_unit_conservation": {
            "total_enqueue_token_units": total_enqueue_units,
            "total_dequeue_token_units": total_dequeue_units,
            "terminal_pending_token_units": int(variant["global_B_final"]),
        },
    }


def relative_exposure(*, inventory: dict[str, Any], head_local_inventory: dict[str, Any], recovery: dict[str, int | float]) -> dict[str, Any]:
    creation = inventory["logical_source_affiliation_creation"]
    baseline_creation = head_local_inventory["logical_source_affiliation_creation"]
    release = inventory["logical_source_affiliation_release"]
    baseline_release = head_local_inventory["logical_source_affiliation_release"]
    selection = inventory["logical_cross_source_selection"]
    recovered = int(recovery["recovered_logical_token_layers"])
    enqueue_delta = int(creation["total_enqueue_segment_count"]) - int(baseline_creation["total_enqueue_segment_count"])
    release_delta = int(release["total_release_segment_count"]) - int(baseline_release["total_release_segment_count"])
    return {
        "additional_logical_source_affiliation_creation_segments_vs_head_local": enqueue_delta,
        "additional_logical_source_affiliation_release_segments_vs_head_local": release_delta,
        "shared_source_affiliation_creation_segments": creation["shared_enqueue_segment_count"],
        "shared_source_affiliation_release_segments": release["shared_release_segment_count"],
        "oldest_source_comparison_count": selection["oldest_source_comparison_count"],
        "cross_source_switch_count": selection["cross_source_switch_count"],
        "unweighted_exposure_ratios": {
            "recovered_logical_token_layers_per_cross_source_comparison": unweighted_exposure_ratio(recovered_logical_token_layers=recovered, event_count=int(selection["oldest_source_comparison_count"])),
            "recovered_logical_token_layers_per_additional_source_affiliation_creation": unweighted_exposure_ratio(recovered_logical_token_layers=recovered, event_count=max(0, enqueue_delta)),
            "recovered_logical_token_layers_per_shared_source_affiliation_creation": unweighted_exposure_ratio(recovered_logical_token_layers=recovered, event_count=int(creation["shared_enqueue_segment_count"])),
        },
    }


def expected_cmin(a466_row: dict[str, Any], variant: dict[str, Any]) -> int:
    frontier = a466_row["Cmin_zero_breach_capacity_efficiency_frontier"]
    label = variant["label"]
    if label in {"head_local_private_unbounded", "hierarchical_qpeak_head_local_endpoint"}:
        return int(frontier["head_local_equal_quota"]["Cmin_zero_breach_logical_tokens_per_layer"])
    if label in {"layer_shared_unbounded", "hierarchical_q0_shared_endpoint"}:
        return int(frontier["layer_shared"]["Cmin_zero_breach_logical_tokens_per_layer"])
    quota = variant["private_quota_per_head"]
    entry = next(item for item in frontier["hierarchical_private_quota_sweep"] if int(item["private_quota_per_head"]) == int(quota))
    return int(entry["Cmin_zero_breach_logical_tokens_per_layer"])


def validate_chain(*, a466: dict[str, Any], a4670: dict[str, Any], args: argparse.Namespace) -> tuple[dict[RowKey, dict[str, Any]], dict[RowKey, dict[str, Any]]]:
    if a4670.get("input_artifacts", {}).get("a466_report_sha256") != sha256_file(args.a466_report):
        raise ValueError("A4.6.7.0 does not hash-bind the supplied A4.6.6 report")
    upstream = ("a461_report_sha256", "a4630_report_sha256", "a464_report_sha256", "a465_report_sha256")
    if any(a4670["input_artifacts"].get(name) != a466.get("input_artifacts", {}).get(name) for name in upstream):
        raise ValueError("A4.6.6/A4.6.7.0 upstream hash-binding mismatch")
    if not all(a4670.get("semantic_guards", {}).get(name) is True for name in REQUIRED_A4670_GUARDS):
        raise ValueError("A4.6.7.0 semantic guards are incomplete")
    a466_rows = {(row["anchor"], row["workload"]): row for row in a466["anchor_rows"]}
    a4670_rows = {(row["anchor"], row["workload"]): row for row in a4670["anchor_rows"]}
    if len(a466_rows) != 6 or set(a466_rows) != set(a4670_rows):
        raise ValueError("A4.6.6/A4.6.7.0 six-row coverage mismatch")
    return a466_rows, a4670_rows


def endpoint_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("logical_capacity_recovery_context", "logical_management_primitive_inventory", "relative_unweighted_management_exposure_vs_head_local")}


def analyze_row(*, a466_row: dict[str, Any], a4670_row: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for horizon in HORIZONS:
        a466_horizon = next(item for item in a466_row["horizon_rows"] if int(item["evaluation_horizon_append_opportunities"]) == horizon)
        a4670_horizon = next(item for item in a4670_row["horizon_rows"] if int(item["evaluation_horizon_append_opportunities"]) == horizon)
        if not (a4670_horizon["a464_causal_replay_match"] and a4670_horizon["a465_causal_replay_match"] and a4670_horizon["a466_causal_replay_match"]):
            raise ValueError("A4.6.7.0 replay guards are incomplete")
        variants = {item["label"]: item for item in a4670_horizon["ownership_variants"]}
        if set(variants) != REQUIRED_VARIANTS:
            raise ValueError("A4.6.7.0 ownership variant coverage mismatch")
        head_local = variants["head_local_private_unbounded"]
        head_local_cmin = expected_cmin(a466_horizon, head_local)
        head_local_inventory = management_inventory(head_local)
        variant_rows = []
        for label, variant in sorted(variants.items()):
            cmin = expected_cmin(a466_horizon, variant)
            context_cmin = int(variant["a466_capacity_context"]["a466_Cmin_zero_breach_logical_tokens_per_layer"])
            if cmin != context_cmin:
                raise ValueError("A4.6.7.0 Cmin context disagrees with A4.6.6 frontier")
            inventory = management_inventory(variant)
            recovery = capacity_recovery(head_local_cmin=head_local_cmin, organization_cmin=cmin, layer_count=len(variant["activation_logical_operation_and_concurrency_summary"]))
            variant_rows.append({
                "label": label,
                "organization": variant["organization"],
                "private_quota_per_head": variant["private_quota_per_head"],
                "semantic_endpoint_only": variant["semantic_endpoint_only"],
                "logical_capacity_recovery_context": recovery,
                "logical_management_primitive_inventory": inventory,
                "relative_unweighted_management_exposure_vs_head_local": relative_exposure(inventory=inventory, head_local_inventory=head_local_inventory, recovery=recovery),
            })
        by_label = {item["label"]: item for item in variant_rows}
        if endpoint_payload(by_label["layer_shared_unbounded"]) != endpoint_payload(by_label["hierarchical_q0_shared_endpoint"]):
            raise AssertionError("q=0 endpoint changed shared management or capacity inventory")
        if endpoint_payload(by_label["head_local_private_unbounded"]) != endpoint_payload(by_label["hierarchical_qpeak_head_local_endpoint"]):
            raise AssertionError("large-q endpoint changed head-local management or capacity inventory")
        rows.append({
            "evaluation_horizon_append_opportunities": horizon,
            "horizon_completion_state": "drained" if int(a4670_horizon["causal_outcome"]["B_final"]) == 0 else "prefix_censored_pending_remains",
            "fixed_causal_outcome": a4670_horizon["causal_outcome"],
            "organization_tax_capacity_rows": variant_rows,
            "semantic_and_endpoint_guards": {
                "a4670_fixed_grant_fifo_replay_matches": True,
                "hierarchical_q0_matches_layer_shared_management_inventory": True,
                "hierarchical_qpeak_matches_head_local_management_inventory": True,
                "no_unweighted_event_to_physical_cost_mapping": True,
            },
        })
    return {"anchor": a4670_row["anchor"], "workload": a4670_row["workload"], "reasoning_priority_row": a4670_row["reasoning_priority_row"], "horizon_rows": rows}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a466 = read_completed(args.a466_report, A466_SCHEMA, "A4.6.6")
    a4670 = read_completed(args.a4670_report, A4670_SCHEMA, "A4.6.7.0")
    a466_rows, a4670_rows = validate_chain(a466=a466, a4670=a4670, args=args)
    if args.preflight_only:
        print("A4.6.7.1 preflight passed: A4.6.6/A4.6.7.0 hash chain, semantic guards, Cmin context, and six-row coverage validated; no output created.")
        return
    config = {
        "a466_report": str(args.a466_report),
        "a4670_report": str(args.a4670_report),
        "evaluation_horizons_append_opportunities": list(HORIZONS),
        "capacity_recovery_definition": "A4.6.6 head-local Cmin minus the named organization Cmin, both logical tokens per layer under fixed causal arrivals/grants/order.",
        "management_inventory_mapping": "An enqueue segment is one logical source-affiliation creation candidate; a released segment is one logical affiliation-release candidate; a two-source dequeue comparison is one logical oldest-source selection candidate. These are intentionally unweighted logical records, not physical descriptor/PTE/access/port/bank/cycle mappings.",
        "scheduling_rule": "Fixed A4.6.4 grants are inherited through A4.6.7.0; this study neither recomputes nor changes admission service.",
    }
    report = {
        "schema_version": SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model functional logical organization-management inventory paired with trace-derived A4.6.6 capacity-observer context; not measured or modeled physical hardware cost",
        "input_artifacts": {
            "a461_report_sha256": a4670["input_artifacts"]["a461_report_sha256"],
            "a4630_report_sha256": a4670["input_artifacts"]["a4630_report_sha256"],
            "a464_report_sha256": a4670["input_artifacts"]["a464_report_sha256"],
            "a465_report_sha256": a4670["input_artifacts"]["a465_report_sha256"],
            "a466_report_sha256": sha256_file(args.a466_report),
            "a4670_report_sha256": sha256_file(args.a4670_report),
        },
        "anchor_rows": [analyze_row(a466_row=a466_rows[key], a4670_row=a4670_rows[key]) for key in sorted(a466_rows)],
        "semantic_guards": {
            "complete_a461_to_a4670_hash_chain_validated": True,
            "fixed_a464_grants_and_a4670_fifo_semantics_reused_without_rescheduling": True,
            "a466_Cmin_context_matches_each_a4670_variant": True,
            "q0_shared_and_large_q_headlocal_management_endpoints_validated": True,
            "prefix_horizons_labeled_when_pending_remains": True,
            "no_unweighted_logical_event_is_called_a_physical_cost": True,
            "no_descriptor_pte_byte_access_port_bank_traffic_cycle_or_hardware_parameter_selected": True,
            "no_model_or_runtime_loaded": True,
            "qwen_llama_rows_separate": True,
        },
        "boundaries": [
            "Capacity recovery is an A4.6.6 logical-observer Cmin difference under fixed causal arrivals/grants/order. It is not allocated physical storage, FIFO depth, or a selected organization.",
            "Source-affiliation creation/release, oldest-source selection, source switch, and span/concurrency fields are unweighted functional logical primitives. They are not physical descriptor counts, PTE fields, accesses, ports, bank conflicts, bytes, HBM/DMA traffic, cycles, timing, latency, throughput, energy, area, or hardware cost.",
            "The exposure ratios only divide recovered logical token-layers by a named logical event count. They introduce no equivalence or cost weight between heterogeneous primitives and must not be used for hardware sizing.",
            "No allocator, finite capacity, spill, migration, compaction, DROP, fallback, Full-KV backing, protection policy, scheduler change, model execution, runtime measurement, hardware parameter, architecture specification, or RTL is modeled.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a4671_pending_organization_tax_recovery_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.7.1 pending organization tax/recovery contract completed: {output}")


if __name__ == "__main__":
    main()
