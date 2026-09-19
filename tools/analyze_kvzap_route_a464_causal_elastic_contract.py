#!/usr/bin/env python3
"""A4.6.4 causal elastic-admission contract over Route-A logical arrivals."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import SCHEMA as A461_SCHEMA, read_completed
from tools.analyze_kvzap_route_a4630_physicalization_mapping import SCHEMA as A4630_SCHEMA
from tools.analyze_kvzap_route_a4632_temporal_contention_replay import (
    COST_PROFILES,
    HORIZONS,
    MAPPED_FIELDS,
    SEALED_COPY,
    composite_work,
    layer_fairness,
    mapped_work,
    selected_variants,
    source_streams,
    terminal_drain,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a464-causal-elastic-admission-contract-1.0"
POLICIES = (
    "minimum_only_work_conserving",
    "causal_counter_hysteresis_v1",
    "same_levels_offline_oracle_reference",
)
# Pre-registered global logical sensitivity levels.  They are deliberately not
# taken from A4.6.2's per-trace envelope and are not hardware service rates.
SERVICE_LEVELS = (16, 64, 256)
COUNTER_POLICY = {
    "layer_backlog_medium_threshold": 512,
    "head_backlog_high_threshold": 64,
    "age_high_threshold_append_opportunities": 16,
    "deescalation_consecutive_low_pressure_opportunities": 2,
}
Stream = tuple[int, int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.6.4 causal Route-A admission contract; no model execution, future-aware "
            "causal policy input, measured timing/traffic, or hardware selection."
        )
    )
    parser.add_argument("--a461-report", type=Path, required=True)
    parser.add_argument("--a4630-report", type=Path, required=True)
    parser.add_argument("--a4632-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate hash-bound inputs without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def consume_oldest(cohorts: deque[tuple[int, int]], grant: int) -> None:
    remaining = grant
    while remaining:
        born, count = cohorts[0]
        used = min(remaining, count)
        remaining -= used
        if used == count:
            cohorts.popleft()
        else:
            cohorts[0] = (born, count - used)


def oldest_age(cohorts: deque[tuple[int, int]], opportunity: int) -> int:
    return 0 if not cohorts else opportunity - cohorts[0][0]


def causal_level(*, state: dict[str, int], layer_backlog: int, max_head_backlog: int, age_max: int) -> tuple[int, str]:
    """Use only current/history counters; no H, future arrivals, or trace quantum."""
    if max_head_backlog >= COUNTER_POLICY["head_backlog_high_threshold"] or age_max >= COUNTER_POLICY["age_high_threshold_append_opportunities"]:
        desired = 2
    elif layer_backlog >= COUNTER_POLICY["layer_backlog_medium_threshold"]:
        desired = 1
    else:
        desired = 0
    current = state["level_index"]
    if desired >= current:
        state["level_index"] = desired
        state["quiet_streak"] = 0
        return desired, "escalate" if desired > current else "hold"
    state["quiet_streak"] += 1
    if state["quiet_streak"] >= COUNTER_POLICY["deescalation_consecutive_low_pressure_opportunities"]:
        state["level_index"] = max(desired, current - 1)
        state["quiet_streak"] = 0
        return state["level_index"], "deescalate"
    return current, "hold_hysteresis"


def oracle_level(*, layer_backlog: int, future_arrivals: int, remaining_opportunities: int) -> int:
    """Clairvoyant reference only: choose the lowest same-level capacity that can drain."""
    for index, level in enumerate(SERVICE_LEVELS):
        if layer_backlog + future_arrivals <= level * remaining_opportunities:
            return index
    return len(SERVICE_LEVELS) - 1


def rr_grants(*, layer: int, heads: list[int], pending: dict[Stream, int], budget: int, rr_next: dict[int, int]) -> dict[Stream, int]:
    grants = {(layer, head): 0 for head in heads}
    available = {(layer, head): pending[layer, head] for head in heads}
    remaining, misses = min(budget, sum(pending[layer, head] for head in heads)), 0
    while remaining and misses < len(heads):
        head = heads[rr_next[layer] % len(heads)]
        key = layer, head
        rr_next[layer] = (rr_next[layer] + 1) % len(heads)
        if available[key] == 0:
            misses += 1
            continue
        grants[key] += 1
        available[key] -= 1
        remaining -= 1
        misses = 0
    return grants


def replay(*, inventory: dict[Stream, dict[str, int]], arrivals: dict[Stream, list[int]], variant: dict[str, Any], policy: str) -> dict[str, Any]:
    horizon = int(variant["drain_horizon_append_opportunities"])
    movement, page_tokens = str(variant["mapping_assumption"]), int(variant["candidate_page_tokens"])
    heads = sorted(inventory)
    by_layer: dict[int, list[int]] = defaultdict(list)
    for layer, head in heads:
        by_layer[layer].append(head)
    for layer in by_layer:
        by_layer[layer].sort()
    pending = {key: inventory[key]["pending"] for key in heads}
    packed = {key: inventory[key]["packed"] for key in heads}
    cohorts = {key: deque([(1, pending[key])]) if pending[key] else deque() for key in heads}
    grants_total = {key: 0 for key in heads}
    post_trace = {key: [] for key in heads}
    pre_peak = {key: pending[key] for key in heads}
    post_peak = dict(pre_peak)
    age_peak = {key: 0 for key in heads}
    rr_next = {layer: 0 for layer in by_layer}
    controller = {layer: {"level_index": 0, "quiet_streak": 0} for layer in by_layer}
    layer_summary = {
        layer: {"layer": layer, "service_level_selection_counts": {name: 0 for name in ("minimum", "medium", "high")}, "escalation_count": 0, "deescalation_count": 0, "max_layer_backlog": 0, "max_head_backlog": 0, "Age_max": 0, "logical_grant_total": 0}
        for layer in by_layer
    }
    total_mapped = {field: 0 for field in MAPPED_FIELDS}
    epochs: list[dict[str, Any]] = []
    attention_borrowed = 0

    for index in range(horizon):
        opportunity = index + 1
        b_before = sum(pending.values())
        a_new = sum(arrivals[key][index] for key in heads)
        for key in heads:
            arrived = arrivals[key][index]
            pending[key] += arrived
            if arrived:
                cohorts[key].append((opportunity, arrived))
            pre_peak[key] = max(pre_peak[key], pending[key])
            age_peak[key] = max(age_peak[key], oldest_age(cohorts[key], opportunity))
        b_after_arrival = sum(pending.values())
        a_attn = sum(inventory[key]["hot"] + packed[key] + pending[key] for key in heads)
        epoch_mapped = {field: 0 for field in MAPPED_FIELDS}
        epoch_grant = 0
        layer_epoch = []

        for layer, layer_heads in sorted(by_layer.items()):
            layer_backlog = sum(pending[layer, head] for head in layer_heads)
            max_head = max(pending[layer, head] for head in layer_heads)
            age_max = max(oldest_age(cohorts[layer, head], opportunity) for head in layer_heads)
            future = sum(arrivals[layer, head][later] for head in layer_heads for later in range(index + 1, horizon))
            if policy == "minimum_only_work_conserving":
                level_index, transition = 0, "fixed_minimum"
            elif policy == "causal_counter_hysteresis_v1":
                level_index, transition = causal_level(state=controller[layer], layer_backlog=layer_backlog, max_head_backlog=max_head, age_max=age_max)
            elif policy == "same_levels_offline_oracle_reference":
                level_index, transition = oracle_level(layer_backlog=layer_backlog, future_arrivals=future, remaining_opportunities=horizon - index), "offline_reference"
            else:
                raise ValueError(f"unknown policy: {policy}")
            budget = SERVICE_LEVELS[level_index]
            allocation = rr_grants(layer=layer, heads=layer_heads, pending=pending, budget=budget, rr_next=rr_next)
            actual = sum(allocation.values())
            attention_borrowed += budget - actual
            names = ("minimum", "medium", "high")
            summary = layer_summary[layer]
            summary["service_level_selection_counts"][names[level_index]] += 1
            summary["escalation_count"] += int(transition == "escalate")
            summary["deescalation_count"] += int(transition == "deescalate")
            summary["max_layer_backlog"] = max(summary["max_layer_backlog"], layer_backlog)
            summary["max_head_backlog"] = max(summary["max_head_backlog"], max_head)
            summary["Age_max"] = max(summary["Age_max"], age_max)
            summary["logical_grant_total"] += actual
            layer_epoch.append({"layer": layer, "B_layer": layer_backlog, "B_max_h": max_head, "Age_max": age_max, "A_t_new_mature_kept_logical_tokens": sum(arrivals[layer, head][index] for head in layer_heads), "service_level": names[level_index], "service_level_logical_budget": budget, "G_layer": actual, "transition": transition})
            for key, grant in allocation.items():
                if not grant:
                    continue
                pending[key] -= grant
                consume_oldest(cohorts[key], grant)
                grants_total[key] += grant
                epoch_grant += grant
                mapped = mapped_work(movement=movement, page_tokens=page_tokens, packed_before=packed[key], grant=grant)
                packed[key] += grant
                for field in MAPPED_FIELDS:
                    epoch_mapped[field] += mapped[field]
                    total_mapped[field] += mapped[field]
        for key in heads:
            merge = int(pending[key] > 0 and packed[key] > 0)
            epoch_mapped["modeled_post_service_dual_source_merge_state_records"] += merge
            total_mapped["modeled_post_service_dual_source_merge_state_records"] += merge
            post_trace[key].append(pending[key])
            post_peak[key] = max(post_peak[key], pending[key])
            age_peak[key] = max(age_peak[key], oldest_age(cohorts[key], opportunity))
        grant_mapped = dict(epoch_mapped)
        grant_mapped["modeled_post_service_dual_source_merge_state_records"] = 0
        epochs.append({"append_opportunity": opportunity, "A_t_attn_source_traversal_token_units": a_attn, "A_t_new_mature_kept_logical_tokens": a_new, "B_t_before_arrivals_logical_tokens": b_before, "B_t_after_arrivals_logical_tokens": b_after_arrival, "G_t_logical_admission_grant": epoch_grant, "B_t_plus_1_after_grant_logical_tokens": sum(pending.values()), "layer_controller_observations": layer_epoch, "G_t_mapped_admission_work_components": grant_mapped, "G_t_mapped_admission_abstract_work_units_by_cost_profile": {name: composite_work(grant_mapped, weights) for name, weights in COST_PROFILES.items()}, "post_service_dual_source_merge_state_records": epoch_mapped["modeled_post_service_dual_source_merge_state_records"], "post_service_dual_source_merge_attention_abstract_work_units_by_cost_profile": {name: weights["merge"] * epoch_mapped["modeled_post_service_dual_source_merge_state_records"] for name, weights in COST_PROFILES.items()}})

    per_head = []
    for key in heads:
        tail = packed[key] % page_tokens
        per_head.append({"layer": key[0], "kv_head": key[1], "B_max_h": pre_peak[key], "B_max_h_after_grant": post_peak[key], "B_final_h": pending[key], "Age_max_h": age_peak[key], "G_total_logical_admission_grant": grants_total[key], "T_drain_h": terminal_drain(post_trace[key]), "deadline_miss": pending[key] > 0, "packed_tokens_after_temporal_replay": packed[key], "current_tail_tokens": tail, "current_tail_unused_token_slots": 0 if tail == 0 else page_tokens - tail, "unsealed_tail_reference_token_units": tail if movement == SEALED_COPY else 0})
    grant_mapped_total = dict(total_mapped)
    grant_mapped_total["modeled_post_service_dual_source_merge_state_records"] = 0
    merge_total = total_mapped["modeled_post_service_dual_source_merge_state_records"]
    t_drain = terminal_drain([row["B_t_plus_1_after_grant_logical_tokens"] for row in epochs])
    return {"policy": policy, "B_max": max(row["B_t_after_arrivals_logical_tokens"] for row in epochs), "B_max_after_grant": max(row["B_t_plus_1_after_grant_logical_tokens"] for row in epochs), "B_final": sum(pending.values()), "T_drain": t_drain, "T_drain_censored_at_horizon": t_drain is None, "deadline_miss_head_count": sum(row["deadline_miss"] for row in per_head), "attention_service_occupied_by_admission_abstract_work_units": {name: composite_work(grant_mapped_total, weights) for name, weights in COST_PROFILES.items()}, "post_service_dual_source_merge_state_records": merge_total, "post_service_dual_source_merge_attention_abstract_work_units": {name: weights["merge"] * merge_total for name, weights in COST_PROFILES.items()}, "attention_borrowed_logical_admission_capacity": attention_borrowed, "grant_mapped_admission_work_components": grant_mapped_total, "endpoint_unsealed_tail_reference_token_units": sum(row["unsealed_tail_reference_token_units"] for row in per_head), "per_head": per_head, "per_layer_fairness": layer_fairness(per_head), "per_layer_control_summary": [layer_summary[layer] for layer in sorted(layer_summary)], "epoch_records": epochs}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a461 = read_completed(args.a461_report, A461_SCHEMA, "A4.6.1")
    a4630 = read_completed(args.a4630_report, A4630_SCHEMA, "A4.6.3.0")
    a4632 = read_completed(args.a4632_report, "kvzap-route-a4632-temporal-abstract-contention-replay-1.0", "A4.6.3.2")
    if a4630.get("input_artifacts", {}).get("a461_report_sha256") != sha256_file(args.a461_report):
        raise ValueError("A4.6.3.0 does not hash-bind this A4.6.1 report")
    if a4632.get("input_artifacts", {}).get("a461_report_sha256") != sha256_file(args.a461_report) or a4632.get("input_artifacts", {}).get("a4630_report_sha256") != sha256_file(args.a4630_report):
        raise ValueError("A4.6.3.2 does not hash-bind the supplied sources")
    source = {(row["anchor"], row["workload"]): row for row in a461["anchor_rows"]}
    mapped = {(row["anchor"], row["workload"]): row for row in a4630["anchor_rows"]}
    if set(source) != set(mapped) or len(source) != 6:
        raise ValueError("A4.6 source coverage mismatch")
    for row in mapped.values():
        selected_variants(row)
    if args.preflight_only:
        print("A4.6.4 preflight passed: A4.6.1/A4.6.3.0/A4.6.3.2 hash bindings and mapping coverage validated; no output created.")
        return
    rows = []
    for key in sorted(source):
        inventory, arrivals = source_streams(source[key])
        variants = []
        for variant in selected_variants(mapped[key]):
            variants.append({"source_a4630_quantum_not_controller_input": True, "drain_horizon_append_opportunities": variant["drain_horizon_append_opportunities"], "mapping_assumption": variant["mapping_assumption"], "candidate_page_tokens": variant["candidate_page_tokens"], "policy_results": [replay(inventory=inventory, arrivals=arrivals, variant=variant, policy=policy) for policy in POLICIES]})
        rows.append({"anchor": key[0], "workload": key[1], "contention_variants": variants})
    config = {"a461_report": str(args.a461_report), "a4630_report": str(args.a4630_report), "a4632_report": str(args.a4632_report), "evaluation_horizons_append_opportunities": list(HORIZONS), "service_levels_logical_tokens_per_layer_append_opportunity": {"minimum": SERVICE_LEVELS[0], "medium": SERVICE_LEVELS[1], "high": SERVICE_LEVELS[2]}, "causal_counter_hysteresis_v1": COUNTER_POLICY, "policies": list(POLICIES), "policy_scope": "One fixed global configuration for every anchor/workload; no anchor/workload identifier, future arrival, evaluation horizon, or A4.6.2 quantum is supplied to the causal controller."}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model causal-control sensitivity over trace-derived arrivals and named modeled A4.6.3.0 mappings; not measured hardware evidence", "input_artifacts": {"a461_report_sha256": sha256_file(args.a461_report), "a4630_report_sha256": sha256_file(args.a4630_report), "a4632_report_sha256": sha256_file(args.a4632_report)}, "anchor_rows": rows, "observational_guards": {"complete_hash_binding_validated": True, "causal_policy_uses_current_history_counters_only": True, "evaluation_horizon_not_controller_input": True, "a462_trace_optimal_quantum_not_controller_input": True, "fixed_global_levels_and_thresholds_across_all_rows": True, "offline_oracle_uses_same_levels_only_as_reference": True, "per_head_backlog_age_deadline_and_fairness_recorded": True, "actual_grants_pass_through_named_a4630_mapping": True, "qwen_llama_rows_separate": True, "no_model_or_runtime_loaded": True, "no_hardware_parameter_selected": True}, "boundaries": ["The causal controller receives only current/history logical counters: current layer/head backlog, pending-cohort age, previous level, and hysteresis state. Evaluation horizon, future arrival, anchor/workload identity, and A4.6.2 per-trace quantum are not controller inputs.", "The same-level offline oracle sees future arrivals only to establish a clairvoyant reference under the identical fixed logical level set. It is not an online policy or hardware-controller implementation.", "Service levels and all thresholds are pre-registered global logical sensitivity values, not cycles, bandwidth, FIFO depth, HBM/DMA traffic, transactions, measured timing, hardware service rate, or selected hardware parameters.", "Mapped token units/records and attention-borrow accounting are modeled inventories only, not measured traffic, latency, throughput, energy, area, net benefit, architecture specification, or RTL evidence."]}
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a464_causal_elastic_contract_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.4 causal elastic contract completed: {output}")


if __name__ == "__main__":
    main()
