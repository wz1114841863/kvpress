#!/usr/bin/env python3
"""A4.6.5 observer-only pending-capacity and service-shortage envelope."""
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
from tools.analyze_kvzap_route_a4632_temporal_contention_replay import HORIZONS, source_streams, terminal_drain
from tools.analyze_kvzap_route_a464_causal_elastic_contract import (
    COUNTER_POLICY,
    SERVICE_LEVELS,
    causal_level,
    consume_oldest,
    rr_grants,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a465-causal-capacity-envelope-1.0"
A464_SCHEMA = "kvzap-route-a464-causal-elastic-admission-contract-1.0"
HEAD_LOCAL_CAPS = (32, 64, 128, 256, 512, 1024)
LAYER_SHARED_CAPS = (256, 512, 1024, 2048, 4096, 8192)
CAUSAL_POLICY = "causal_counter_hysteresis_v1"
Stream = tuple[int, int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.6.5 observer-only Route-A pending-capacity and service-shortage envelope; "
            "no DROP, fallback, grant modification, model execution, or hardware selection."
        )
    )
    parser.add_argument("--a461-report", type=Path, required=True)
    parser.add_argument("--a4630-report", type=Path, required=True)
    parser.add_argument("--a464-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate hash-bound sources without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def run_causal_observer(*, inventory: dict[Stream, dict[str, int]], arrivals: dict[Stream, list[int]], horizon: int) -> dict[str, Any]:
    """Replay the fixed A4.6.4 causal policy; caps are deliberately absent."""
    heads = sorted(inventory)
    by_layer: dict[int, list[int]] = defaultdict(list)
    for layer, head in heads:
        by_layer[layer].append(head)
    for layer in by_layer:
        by_layer[layer].sort()
    pending = {key: inventory[key]["pending"] for key in heads}
    cohorts = {key: deque([(1, pending[key])]) if pending[key] else deque() for key in heads}
    grants = {key: 0 for key in heads}
    head_peak = dict(pending)
    head_age_peak = {key: 0 for key in heads}
    post_trace = {key: [] for key in heads}
    rr_next = {layer: 0 for layer in by_layer}
    controller = {layer: {"level_index": 0, "quiet_streak": 0} for layer in by_layer}
    epochs = []

    for index in range(horizon):
        opportunity = index + 1
        for key in heads:
            arrived = arrivals[key][index]
            pending[key] += arrived
            if arrived:
                cohorts[key].append((opportunity, arrived))
            head_peak[key] = max(head_peak[key], pending[key])
        head_before_grant = dict(pending)
        layer_records = []
        for layer, layer_heads in sorted(by_layer.items()):
            layer_backlog = sum(pending[layer, head] for head in layer_heads)
            max_head = max(pending[layer, head] for head in layer_heads)
            age_max = max(0 if not cohorts[layer, head] else opportunity - cohorts[layer, head][0][0] for head in layer_heads)
            level_index, transition = causal_level(state=controller[layer], layer_backlog=layer_backlog, max_head_backlog=max_head, age_max=age_max)
            budget = SERVICE_LEVELS[level_index]
            allocation = rr_grants(layer=layer, heads=layer_heads, pending=pending, budget=budget, rr_next=rr_next)
            actual = sum(allocation.values())
            for key, grant in allocation.items():
                if grant:
                    pending[key] -= grant
                    consume_oldest(cohorts[key], grant)
                    grants[key] += grant
            post_grant = sum(pending[layer, head] for head in layer_heads)
            layer_records.append({"layer": layer, "B_layer_after_arrivals": layer_backlog, "B_max_h_after_arrivals": max_head, "Age_max": age_max, "A_layer_new": sum(arrivals[layer, head][index] for head in layer_heads), "service_level_index": level_index, "service_level_logical_budget": budget, "G_layer": actual, "B_layer_after_grant": post_grant, "positive_debt": max(0, sum(arrivals[layer, head][index] for head in layer_heads) - actual), "high_level_saturated_with_post_grant_backlog": level_index == 2 and post_grant > 0, "transition": transition})
        for key in heads:
            age = 0 if not cohorts[key] else opportunity - cohorts[key][0][0]
            head_age_peak[key] = max(head_age_peak[key], age)
            post_trace[key].append(pending[key])
        epochs.append({"append_opportunity": opportunity, "head_pending_after_arrivals": [{"layer": key[0], "kv_head": key[1], "pending": head_before_grant[key]} for key in heads], "layer_records": layer_records})
    per_head = [{"layer": key[0], "kv_head": key[1], "B_max_h": head_peak[key], "B_final_h": pending[key], "Age_max_h": head_age_peak[key], "G_total": grants[key], "T_drain_h": terminal_drain(post_trace[key])} for key in heads]
    return {"B_max": max(sum(item["pending"] for item in epoch["head_pending_after_arrivals"]) for epoch in epochs), "B_final": sum(pending.values()), "deadline_miss_head_count": sum(item["B_final_h"] > 0 for item in per_head), "T_drain": terminal_drain([sum(item["B_final_h"] for item in per_head)] if not epochs else [sum(record["B_layer_after_grant"] for record in epoch["layer_records"]) for epoch in epochs]), "per_head": per_head, "epochs": epochs}


def consecutive_max(opportunities: list[int]) -> int:
    best = run = 0
    previous = None
    for value in opportunities:
        run = run + 1 if previous == value - 1 else 1
        best = max(best, run)
        previous = value
    return best


def observer_summary(samples: dict[tuple[int, int], list[tuple[int, int]]], caps: tuple[int, ...], *, scope: str) -> list[dict[str, Any]]:
    result = []
    for cap in caps:
        per_stream = []
        for key, values in sorted(samples.items()):
            breaches = [(opportunity, value - cap) for opportunity, value in values if value > cap]
            if breaches:
                per_stream.append({"stream": {"layer": key[0], "kv_head": key[1]} if scope == "head_local" else {"layer": key[0]}, "first_breach_opportunity": breaches[0][0], "breach_opportunity_count": len(breaches), "peak_excess": max(excess for _, excess in breaches), "max_consecutive_breach_duration": consecutive_max([opportunity for opportunity, _ in breaches])})
        result.append({"logical_capacity_observer_cap": cap, "scope": scope, "breached_stream_count": len(per_stream), "breach_opportunity_count": sum(row["breach_opportunity_count"] for row in per_stream), "first_breach_opportunity": min((row["first_breach_opportunity"] for row in per_stream), default=None), "peak_excess": max((row["peak_excess"] for row in per_stream), default=0), "max_consecutive_breach_duration": max((row["max_consecutive_breach_duration"] for row in per_stream), default=0), "breached_streams": per_stream})
    return result


def layer_pressure(epochs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_layer: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for epoch in epochs:
        for record in epoch["layer_records"]:
            by_layer[int(record["layer"])].append({"opportunity": epoch["append_opportunity"], **record})
    output = []
    for layer, records in sorted(by_layer.items()):
        saturated = [record["opportunity"] for record in records if record["high_level_saturated_with_post_grant_backlog"]]
        debt = [record for record in records if record["positive_debt"] > 0]
        output.append({"layer": layer, "max_layer_backlog_after_arrivals": max(record["B_layer_after_arrivals"] for record in records), "max_head_backlog_after_arrivals": max(record["B_max_h_after_arrivals"] for record in records), "Age_max": max(record["Age_max"] for record in records), "high_level_saturation_opportunity_count": len(saturated), "high_level_saturation_max_consecutive_duration": consecutive_max(saturated), "max_post_grant_backlog_while_high": max((record["B_layer_after_grant"] for record in records if record["high_level_saturated_with_post_grant_backlog"]), default=0), "positive_debt_opportunity_count": len(debt), "positive_debt_max_consecutive_duration": consecutive_max([record["opportunity"] for record in debt]), "peak_positive_debt": max((record["positive_debt"] for record in debt), default=0)})
    return output


def expected_a464(a464_row: dict[str, Any], horizon: int) -> dict[str, Any]:
    variant = next(item for item in a464_row["contention_variants"] if int(item["drain_horizon_append_opportunities"]) == horizon and item["mapping_assumption"] == "eager_copy_on_logical_service" and int(item["candidate_page_tokens"]) == 64)
    return next(item for item in variant["policy_results"] if item["policy"] == CAUSAL_POLICY)


def validate_against_a464(observed: dict[str, Any], expected: dict[str, Any]) -> None:
    for field in ("B_max", "B_final", "deadline_miss_head_count", "T_drain"):
        if observed[field] != expected[field]:
            raise ValueError(f"A4.6.5 observer replay disagrees with A4.6.4 for {field}")
    left = {(row["layer"], row["kv_head"]): row for row in observed["per_head"]}
    right = {(row["layer"], row["kv_head"]): row for row in expected["per_head"]}
    if set(left) != set(right):
        raise ValueError("A4.6.5/A4.6.4 per-head coverage mismatch")
    for key in left:
        for field, expected_field in (("B_max_h", "B_max_h"), ("B_final_h", "B_final_h"), ("G_total", "G_total_logical_admission_grant"), ("T_drain_h", "T_drain_h")):
            if left[key][field] != right[key][expected_field]:
                raise ValueError(f"A4.6.5 observer replay disagrees with A4.6.4 for {key} {field}")


def analyze_row(*, source_row: dict[str, Any], a464_row: dict[str, Any]) -> dict[str, Any]:
    inventory, arrivals = source_streams(source_row)
    horizon_rows = []
    for horizon in HORIZONS:
        observed = run_causal_observer(inventory=inventory, arrivals=arrivals, horizon=horizon)
        validate_against_a464(observed, expected_a464(a464_row, horizon))
        head_samples: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
        layer_samples: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
        for epoch in observed["epochs"]:
            for item in epoch["head_pending_after_arrivals"]:
                head_samples[(item["layer"], item["kv_head"])].append((epoch["append_opportunity"], item["pending"]))
            for item in epoch["layer_records"]:
                layer_samples[(item["layer"], 0)].append((epoch["append_opportunity"], item["B_layer_after_arrivals"]))
        pressure = layer_pressure(observed["epochs"])
        horizon_rows.append({"evaluation_horizon_append_opportunities": horizon, "a464_causal_replay_match": True, "causal_outcome": {field: observed[field] for field in ("B_max", "B_final", "deadline_miss_head_count", "T_drain")}, "head_local_capacity_observer": observer_summary(head_samples, HEAD_LOCAL_CAPS, scope="head_local"), "layer_shared_capacity_observer": observer_summary(layer_samples, LAYER_SHARED_CAPS, scope="layer_shared"), "per_layer_service_shortage_pressure": pressure, "per_head_age_backlog_tail": [{field: item[field] for field in ("layer", "kv_head", "B_max_h", "Age_max_h", "B_final_h", "T_drain_h")} for item in observed["per_head"]]})
    return {"anchor": source_row["anchor"], "workload": source_row["workload"], "reasoning_priority_row": source_row["workload"] == "reasoning", "horizon_rows": horizon_rows}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a461 = read_completed(args.a461_report, A461_SCHEMA, "A4.6.1")
    a4630 = read_completed(args.a4630_report, A4630_SCHEMA, "A4.6.3.0")
    a464 = read_completed(args.a464_report, A464_SCHEMA, "A4.6.4")
    if a4630.get("input_artifacts", {}).get("a461_report_sha256") != sha256_file(args.a461_report):
        raise ValueError("A4.6.3.0 does not hash-bind this A4.6.1 report")
    inputs = a464.get("input_artifacts", {})
    if inputs.get("a461_report_sha256") != sha256_file(args.a461_report) or inputs.get("a4630_report_sha256") != sha256_file(args.a4630_report):
        raise ValueError("A4.6.4 does not hash-bind the supplied A4.6.1/A4.6.3.0 reports")
    source = {(row["anchor"], row["workload"]): row for row in a461["anchor_rows"]}
    prior = {(row["anchor"], row["workload"]): row for row in a464["anchor_rows"]}
    if set(source) != set(prior) or len(source) != 6:
        raise ValueError("A4.6.1/A4.6.4 anchor-workload coverage mismatch")
    if args.preflight_only:
        print("A4.6.5 preflight passed: A4.6.1/A4.6.3.0/A4.6.4 hash bindings and six-row coverage validated; no output created.")
        return
    rows = [analyze_row(source_row=source[key], a464_row=prior[key]) for key in sorted(source)]
    config = {"a461_report": str(args.a461_report), "a4630_report": str(args.a4630_report), "a464_report": str(args.a464_report), "evaluation_horizons_append_opportunities": list(HORIZONS), "causal_policy_replayed": CAUSAL_POLICY, "fixed_service_levels_logical_tokens_per_layer_append_opportunity": list(SERVICE_LEVELS), "fixed_counter_policy": COUNTER_POLICY, "head_local_observer_caps_logical_pending_tokens": list(HEAD_LOCAL_CAPS), "layer_shared_observer_caps_logical_pending_tokens": list(LAYER_SHARED_CAPS), "observer_rule": "Caps inspect pending immediately after arrivals and before grant; they cannot alter grants, causal state, admission, DROP, fallback, backing, or any lifecycle state."}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model observer-only logical pending-capacity and service-shortage sensitivity over hash-bound causal replay; not measured hardware evidence", "input_artifacts": {"a461_report_sha256": sha256_file(args.a461_report), "a4630_report_sha256": sha256_file(args.a4630_report), "a464_report_sha256": sha256_file(args.a464_report)}, "anchor_rows": rows, "observational_guards": {"complete_hash_binding_validated": True, "a465_causal_replay_matches_a464_each_horizon": True, "head_local_and_layer_shared_caps_observer_only": True, "caps_do_not_change_grants_or_causal_state": True, "no_drop_fallback_or_backing_action": True, "reasoning_peak_excess_saturation_age_retained_separately": True, "qwen_llama_rows_separate": True, "no_model_or_runtime_loaded": True, "no_hardware_parameter_selected": True}, "boundaries": ["Capacity caps are observer-only logical pending thresholds sampled after arrivals and before grant. A breach is not an overflow action and never causes DROP, fallback, Full-KV backing, admission change, state freezing, reordering, or any policy change.", "Head-local and layer-shared capacities are alternative logical accounting sensitivities, not FIFO depth, allocator capacity, page/bank organization, physical memory, or a selected resource contract. Peak excess, duration, age, and debt are timestamp-free logical pressure descriptors.", "The fixed A4.6.4 causal policy is replayed only to reproduce its already hash-bound behavior. Evaluation horizon is not controller input, and this report does not introduce a new controller, scheduler, protection mode, or hardware service rate.", "No output is measured HBM/DMA traffic, bytes, cycles, bandwidth, timing, latency, throughput, energy, area, net benefit, architecture specification, or RTL evidence."]}
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a465_causal_capacity_envelope_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.5 causal capacity envelope completed: {output}")


if __name__ == "__main__":
    main()
