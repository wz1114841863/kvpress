#!/usr/bin/env python3
"""A4.6.6 observer-only equal-budget Route-A pending-organization study.

This study intentionally does *not* implement a storage allocator.  It takes
the fixed A4.6.4 causal replay as an input contract, then asks how an identical
per-layer logical capacity budget would be exposed to already-existing pending
state under three ownership organizations.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import SCHEMA as A461_SCHEMA, read_completed
from tools.analyze_kvzap_route_a4630_physicalization_mapping import SCHEMA as A4630_SCHEMA
from tools.analyze_kvzap_route_a4632_temporal_contention_replay import HORIZONS, source_streams
from tools.analyze_kvzap_route_a464_causal_elastic_contract import SCHEMA as A464_SCHEMA
from tools.analyze_kvzap_route_a465_causal_capacity_envelope import (
    CAUSAL_POLICY,
    SCHEMA as A465_SCHEMA,
    expected_a464,
    run_causal_observer,
    validate_against_a464,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a466-pending-organization-contract-1.0"
ORGANIZATIONS = ("head_local_equal_quota", "layer_shared", "hierarchical_private_plus_shared_overflow")
# The same fractions are applied to every row.  They are capacity-ownership
# sensitivities, not trace-specific tuning or a selected hardware partition.
PRIVATE_QUOTA_FRACTIONS = ((0, 1), (1, 4), (1, 2), (3, 4), (1, 1))
# A pre-registered global observer grid. It is deliberately shared by every
# anchor/workload/horizon, rather than derived from a row's own peak.
COMMON_TOTAL_BUDGETS = (0, 512, 1024, 2048, 4096, 8192, 12288, 16384, 18432)
BOUNDED_BREACH_TARGETS = (
    {"maximum_peak_excess_logical_tokens": 256, "maximum_consecutive_breach_duration": 8},
    {"maximum_peak_excess_logical_tokens": 64, "maximum_consecutive_breach_duration": 1},
)
Stream = tuple[int, int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.6.6 equal-total-budget Route-A pending-organization observer; fixed A4.6.4 "
            "arrivals/grants/order only, with no allocator, scheduler, DROP, fallback, model, or hardware selection."
        )
    )
    parser.add_argument("--a461-report", type=Path, required=True)
    parser.add_argument("--a4630-report", type=Path, required=True)
    parser.add_argument("--a464-report", type=Path, required=True)
    parser.add_argument("--a465-report", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate the hash-bound replay chain without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def consecutive_max(opportunities: list[int]) -> int:
    best = run = 0
    previous: int | None = None
    for value in opportunities:
        run = run + 1 if previous == value - 1 else 1
        best = max(best, run)
        previous = value
    return best


def lcm_all(values: list[int]) -> int:
    if not values or min(values) <= 0:
        raise ValueError("head-count LCM requires positive values")
    result = 1
    for value in values:
        result = math.lcm(result, value)
    return result


def layer_samples(observed: dict[str, Any]) -> dict[int, list[tuple[int, list[int]]]]:
    """Return post-arrival, pre-grant pending snapshots grouped by layer.

    The original A4.6.4 grants have already been applied inside ``observed`` to
    form later snapshots.  This function neither accesses nor changes a grant.
    """
    result: dict[int, list[tuple[int, list[int]]]] = defaultdict(list)
    for epoch in observed["epochs"]:
        grouped: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for item in epoch["head_pending_after_arrivals"]:
            grouped[int(item["layer"])].append((int(item["kv_head"]), int(item["pending"])))
        for layer, values in grouped.items():
            ordered = [pending for _, pending in sorted(values)]
            if not ordered or min(ordered) < 0:
                raise ValueError("invalid post-arrival layer pending snapshot")
            result[layer].append((int(epoch["append_opportunity"]), ordered))
    if not result or len({len(values) for values in result.values()}) != 1:
        raise ValueError("incomplete or unequal layer opportunity coverage")
    if len({len(values[0][1]) for values in result.values()}) != 1:
        raise ValueError("head count changes across layers")
    return dict(sorted(result.items()))


def snapshot(*, pending: list[int], total_budget: int, organization: str, private_quota: int = 0) -> dict[str, int]:
    """Pure capacity ownership accounting for one layer/opportunity snapshot."""
    if total_budget < 0 or private_quota < 0 or not pending or min(pending) < 0:
        raise ValueError("invalid logical capacity snapshot")
    head_count = len(pending)
    total_pending = sum(pending)
    if organization == "head_local_equal_quota":
        if total_budget % head_count:
            raise ValueError("head-local equal quota requires budget divisible by head count")
        quota = total_budget // head_count
        overflow_demand = sum(max(0, value - quota) for value in pending)
        private_reserved = total_budget
        shared_capacity = 0
        unused_private = sum(max(0, quota - value) for value in pending)
    elif organization == "layer_shared":
        quota = 0
        overflow_demand = total_pending
        private_reserved = 0
        shared_capacity = total_budget
        unused_private = 0
    elif organization == "hierarchical_private_plus_shared_overflow":
        private_reserved = head_count * private_quota
        if private_reserved > total_budget:
            raise ValueError("hierarchical private quota exceeds equal total budget")
        quota = private_quota
        overflow_demand = sum(max(0, value - quota) for value in pending)
        shared_capacity = total_budget - private_reserved
        unused_private = sum(max(0, quota - value) for value in pending)
    else:
        raise ValueError(f"unknown organization {organization}")
    excess = max(0, overflow_demand - shared_capacity)
    # "Stranded" is deliberately only private capacity inaccessible while this
    # same snapshot breaches.  Idle capacity without a breach is ordinary slack.
    stranded = unused_private if excess else 0
    return {
        "head_count": head_count,
        "total_pending": total_pending,
        "total_budget": total_budget,
        "private_quota_per_head": quota,
        "private_reserved": private_reserved,
        "shared_overflow_capacity": shared_capacity,
        "overflow_demand": overflow_demand,
        "peak_excess": excess,
        "unused_private_reservation": unused_private,
        "stranded_private_reservation": stranded,
    }


def organization_summary(*, samples: dict[int, list[tuple[int, list[int]]]], total_budget: int, organization: str, private_quota: int = 0, include_per_layer: bool = False) -> dict[str, Any]:
    """Summarize one organization at a fixed, equal per-layer budget C."""
    per_layer: list[dict[str, Any]] = []
    all_breach_opportunities = 0
    breached_layer_count = 0
    all_stranded_opportunities = 0
    total_stranded = 0
    peak_stranded = 0
    peak_excess = 0
    max_duration = 0
    for layer, rows in sorted(samples.items()):
        values = [snapshot(pending=pending, total_budget=total_budget, organization=organization, private_quota=private_quota) for _, pending in rows]
        breaches = [opportunity for (opportunity, _), value in zip(rows, values) if value["peak_excess"] > 0]
        stranded = [value["stranded_private_reservation"] for value in values if value["peak_excess"] > 0]
        layer_peak = max(value["peak_excess"] for value in values)
        peak_excess = max(peak_excess, layer_peak)
        max_duration = max(max_duration, consecutive_max(breaches))
        all_breach_opportunities += len(breaches)
        breached_layer_count += bool(breaches)
        all_stranded_opportunities += sum(value > 0 for value in stranded)
        total_stranded += sum(stranded)
        peak_stranded = max(peak_stranded, max(stranded, default=0))
        if include_per_layer:
            per_layer.append({
                "layer": layer,
                "breach_opportunity_count": len(breaches),
                "first_breach_opportunity": breaches[0] if breaches else None,
                "peak_excess": layer_peak,
                "max_consecutive_breach_duration": consecutive_max(breaches),
                "stranded_private_reservation_during_breach_total": sum(stranded),
                "stranded_private_reservation_peak_during_breach": max(stranded, default=0),
            })
    result: dict[str, Any] = {
        "organization": organization,
        "total_logical_capacity_budget_per_layer": total_budget,
        "private_quota_per_head": private_quota,
        "shared_overflow_capacity_per_layer": total_budget - private_quota * len(next(iter(samples.values()))[0][1]),
        "breached_layer_count": breached_layer_count,
        "breach_layer_opportunity_count": all_breach_opportunities,
        "peak_excess_logical_tokens": peak_excess,
        "max_consecutive_breach_duration": max_duration,
        "stranded_private_reservation_during_breach_total": total_stranded,
        "stranded_private_reservation_peak_during_breach": peak_stranded,
        "stranded_breach_layer_opportunity_count": all_stranded_opportunities,
    }
    if include_per_layer:
        result["per_layer"] = per_layer
    return result


def zero_breach_budget(*, samples: dict[int, list[tuple[int, list[int]]]], organization: str, private_quota: int = 0) -> int:
    """Exact Cmin for zero breach under a named fixed ownership arrangement."""
    head_count = len(next(iter(samples.values()))[0][1])
    if organization == "head_local_equal_quota":
        return head_count * max(max(pending) for rows in samples.values() for _, pending in rows)
    if organization == "layer_shared":
        return max(sum(pending) for rows in samples.values() for _, pending in rows)
    if organization == "hierarchical_private_plus_shared_overflow":
        overflow = max(sum(max(0, value - private_quota) for value in pending) for rows in samples.values() for _, pending in rows)
        return head_count * private_quota + overflow
    raise ValueError(f"unknown organization {organization}")


def meets_target(summary: dict[str, Any], target: dict[str, int]) -> bool:
    return summary["peak_excess_logical_tokens"] <= target["maximum_peak_excess_logical_tokens"] and summary["max_consecutive_breach_duration"] <= target["maximum_consecutive_breach_duration"]


def min_budget_for_target(*, samples: dict[int, list[tuple[int, list[int]]]], organization: str, target: dict[str, int], private_quota: int = 0) -> int:
    """Find minimum C for a monotone bounded-breach observer target."""
    head_count = len(next(iter(samples.values()))[0][1])
    high = zero_breach_budget(samples=samples, organization=organization, private_quota=private_quota)
    if organization == "head_local_equal_quota":
        low_quota, high_quota = 0, high // head_count
        while low_quota < high_quota:
            middle = (low_quota + high_quota) // 2
            result = organization_summary(samples=samples, total_budget=middle * head_count, organization=organization)
            if meets_target(result, target):
                high_quota = middle
            else:
                low_quota = middle + 1
        return low_quota * head_count
    low = head_count * private_quota if organization == "hierarchical_private_plus_shared_overflow" else 0
    while low < high:
        middle = (low + high) // 2
        if organization == "hierarchical_private_plus_shared_overflow" and middle < head_count * private_quota:
            low = head_count * private_quota
            continue
        result = organization_summary(samples=samples, total_budget=middle, organization=organization, private_quota=private_quota)
        if meets_target(result, target):
            high = middle
        else:
            low = middle + 1
    return low


def a465_horizon(a465_row: dict[str, Any], horizon: int) -> dict[str, Any]:
    return next(item for item in a465_row["horizon_rows"] if int(item["evaluation_horizon_append_opportunities"]) == horizon)


def validate_against_a465(observed: dict[str, Any], prior: dict[str, Any]) -> None:
    if observed["B_max"] != prior["causal_outcome"]["B_max"] or observed["B_final"] != prior["causal_outcome"]["B_final"] or observed["deadline_miss_head_count"] != prior["causal_outcome"]["deadline_miss_head_count"] or observed["T_drain"] != prior["causal_outcome"]["T_drain"]:
        raise ValueError("A4.6.6 observer replay disagrees with A4.6.5 causal outcome")
    left = {(item["layer"], item["kv_head"]): item for item in observed["per_head"]}
    right = {(item["layer"], item["kv_head"]): item for item in prior["per_head_age_backlog_tail"]}
    if set(left) != set(right):
        raise ValueError("A4.6.6/A4.6.5 per-head coverage mismatch")
    for key in left:
        for name in ("B_max_h", "B_final_h", "T_drain_h"):
            if left[key][name] != right[key][name]:
                raise ValueError(f"A4.6.6 observer replay disagrees with A4.6.5 for {key} {name}")


def analyze_row(*, source_row: dict[str, Any], a464_row: dict[str, Any], a465_row: dict[str, Any], common_budget_alignment: int) -> dict[str, Any]:
    inventory, arrivals = source_streams(source_row)
    horizon_rows = []
    for horizon in HORIZONS:
        observed = run_causal_observer(inventory=inventory, arrivals=arrivals, horizon=horizon)
        validate_against_a464(observed, expected_a464(a464_row, horizon))
        validate_against_a465(observed, a465_horizon(a465_row, horizon))
        samples = layer_samples(observed)
        head_count = len(next(iter(samples.values()))[0][1])
        # C values are shared across all rows. Four-way private fractions remain
        # integral because each pre-registered C meets the global alignment.
        cmax = zero_breach_budget(samples=samples, organization="head_local_equal_quota")
        if cmax > COMMON_TOTAL_BUDGETS[-1]:
            raise ValueError("pre-registered common budget grid does not cover head-local zero-breach observer bound")
        if any(budget % common_budget_alignment for budget in COMMON_TOTAL_BUDGETS):
            raise ValueError("common budget grid cannot represent integral global quarter-quota splits")
        budgets = list(COMMON_TOTAL_BUDGETS)
        equal_budget_frontier = []
        for budget in budgets:
            head_local = organization_summary(samples=samples, total_budget=budget, organization="head_local_equal_quota")
            shared = organization_summary(samples=samples, total_budget=budget, organization="layer_shared")
            hierarchical = []
            for numerator, denominator in PRIVATE_QUOTA_FRACTIONS:
                quota = budget * numerator // (denominator * head_count)
                hierarchical.append({"private_quota_fraction": {"numerator": numerator, "denominator": denominator}, **organization_summary(samples=samples, total_budget=budget, organization="hierarchical_private_plus_shared_overflow", private_quota=quota)})
            equal_budget_frontier.append({"total_logical_capacity_budget_per_layer": budget, "head_local": head_local, "layer_shared": shared, "hierarchical_private_quota_sweep": hierarchical})
        quota_ladder = sorted({0, 16, 64, 128, 256, 512, 1024, max(max(pending) for rows in samples.values() for _, pending in rows)})
        zero_frontier = {
            "head_local_equal_quota": {"Cmin_zero_breach_logical_tokens_per_layer": zero_breach_budget(samples=samples, organization="head_local_equal_quota")},
            "layer_shared": {"Cmin_zero_breach_logical_tokens_per_layer": zero_breach_budget(samples=samples, organization="layer_shared")},
            "hierarchical_private_quota_sweep": [{"private_quota_per_head": quota, "Cmin_zero_breach_logical_tokens_per_layer": zero_breach_budget(samples=samples, organization="hierarchical_private_plus_shared_overflow", private_quota=quota)} for quota in quota_ladder],
        }
        bounded = []
        for target in BOUNDED_BREACH_TARGETS:
            bounded.append({
                "target": target,
                "head_local_equal_quota_Cmin": min_budget_for_target(samples=samples, organization="head_local_equal_quota", target=target),
                "layer_shared_Cmin": min_budget_for_target(samples=samples, organization="layer_shared", target=target),
                "hierarchical_private_quota_Cmin": [{"private_quota_per_head": quota, "Cmin": min_budget_for_target(samples=samples, organization="hierarchical_private_plus_shared_overflow", private_quota=quota, target=target)} for quota in quota_ladder],
            })
        horizon_rows.append({
            "evaluation_horizon_append_opportunities": horizon,
            "a464_causal_replay_match": True,
            "a465_causal_replay_match": True,
            "causal_outcome": {name: observed[name] for name in ("B_max", "B_final", "deadline_miss_head_count", "T_drain")},
            "head_count_per_layer": head_count,
            "common_equal_budget_grid_logical_tokens_per_layer": list(COMMON_TOTAL_BUDGETS),
            "common_equal_budget_alignment_logical_tokens_per_layer": common_budget_alignment,
            "capacity_efficiency_frontier_equal_total_budget": equal_budget_frontier,
            "Cmin_zero_breach_capacity_efficiency_frontier": zero_frontier,
            "bounded_breach_capacity_sensitivity": bounded,
            "per_head_age_backlog_tail_unchanged": [{name: item[name] for name in ("layer", "kv_head", "B_max_h", "Age_max_h", "B_final_h", "T_drain_h")} for item in observed["per_head"]],
        })
    return {"anchor": source_row["anchor"], "workload": source_row["workload"], "reasoning_priority_row": source_row["workload"] == "reasoning", "horizon_rows": horizon_rows}


def validate_chain(*, a461: dict[str, Any], a4630: dict[str, Any], a464: dict[str, Any], a465: dict[str, Any], paths: argparse.Namespace) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]], int]:
    if a4630.get("input_artifacts", {}).get("a461_report_sha256") != sha256_file(paths.a461_report):
        raise ValueError("A4.6.3.0 does not hash-bind this A4.6.1 report")
    a464_inputs = a464.get("input_artifacts", {})
    if a464_inputs.get("a461_report_sha256") != sha256_file(paths.a461_report) or a464_inputs.get("a4630_report_sha256") != sha256_file(paths.a4630_report):
        raise ValueError("A4.6.4 does not hash-bind supplied A4.6.1/A4.6.3.0 reports")
    a465_inputs = a465.get("input_artifacts", {})
    if a465_inputs != {"a461_report_sha256": sha256_file(paths.a461_report), "a4630_report_sha256": sha256_file(paths.a4630_report), "a464_report_sha256": sha256_file(paths.a464_report)}:
        raise ValueError("A4.6.5 does not hash-bind the supplied causal replay chain")
    if not all(a465.get("observational_guards", {}).get(name) is True for name in ("complete_hash_binding_validated", "a465_causal_replay_matches_a464_each_horizon", "caps_do_not_change_grants_or_causal_state", "no_drop_fallback_or_backing_action")):
        raise ValueError("A4.6.5 observer-only guards are incomplete")
    source = {(row["anchor"], row["workload"]): row for row in a461["anchor_rows"]}
    prior = {(row["anchor"], row["workload"]): row for row in a464["anchor_rows"]}
    capacity = {(row["anchor"], row["workload"]): row for row in a465["anchor_rows"]}
    if len(source) != 6 or set(source) != set(prior) or set(source) != set(capacity):
        raise ValueError("A4.6.1/A4.6.4/A4.6.5 six-row coverage mismatch")
    counts = []
    for row in source.values():
        inventory, _ = source_streams(row)
        counts.append(len({head for _, head in inventory}))
    return source, prior, capacity, 4 * lcm_all(sorted(set(counts)))


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a461 = read_completed(args.a461_report, A461_SCHEMA, "A4.6.1")
    a4630 = read_completed(args.a4630_report, A4630_SCHEMA, "A4.6.3.0")
    a464 = read_completed(args.a464_report, A464_SCHEMA, "A4.6.4")
    a465 = read_completed(args.a465_report, A465_SCHEMA, "A4.6.5")
    source, prior, capacity, budget_step = validate_chain(a461=a461, a4630=a4630, a464=a464, a465=a465, paths=args)
    if args.preflight_only:
        print("A4.6.6 preflight passed: hash-bound A4.6.1/A4.6.3.0/A4.6.4/A4.6.5 chain, guards, and six-row coverage validated; no output created.")
        return
    rows = [analyze_row(source_row=source[key], a464_row=prior[key], a465_row=capacity[key], common_budget_alignment=budget_step) for key in sorted(source)]
    config = {
        "a461_report": str(args.a461_report), "a4630_report": str(args.a4630_report), "a464_report": str(args.a464_report), "a465_report": str(args.a465_report),
        "evaluation_horizons_append_opportunities": list(HORIZONS), "causal_policy_replayed": CAUSAL_POLICY,
        "organizations": list(ORGANIZATIONS), "private_quota_fractions": [{"numerator": n, "denominator": d} for n, d in PRIVATE_QUOTA_FRACTIONS],
        "common_total_budget_grid_logical_tokens_per_layer": list(COMMON_TOTAL_BUDGETS),
        "common_budget_alignment_rule": "Each C is globally pre-registered and divisible by 4*lcm(observed per-layer head counts), so all sampled rows support integral quarter-quota hierarchical splits.",
        "bounded_breach_targets": list(BOUNDED_BREACH_TARGETS),
        "observer_rule": "For each post-arrival/pre-grant snapshot, organization changes only capacity ownership under the same per-layer C. It cannot change A4.6.4 grants, controller state, per-head order, admission, DROP, fallback, backing, or lifecycle state.",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "execution_classification": "no-model observer-only equal-total-logical-capacity pending-organization sensitivity over hash-bound causal replay; not measured hardware evidence",
        "input_artifacts": {"a461_report_sha256": sha256_file(args.a461_report), "a4630_report_sha256": sha256_file(args.a4630_report), "a464_report_sha256": sha256_file(args.a464_report), "a465_report_sha256": sha256_file(args.a465_report)},
        "anchor_rows": rows,
        "observational_guards": {
            "complete_hash_binding_validated": True, "a464_causal_replay_matches_each_horizon": True, "a465_causal_replay_matches_each_horizon": True,
            "same_total_logical_budget_per_layer_across_organizations": True, "organization_does_not_change_grants_controller_or_per_head_order": True,
            "no_allocator_or_storage_state_simulated": True, "no_drop_fallback_or_backing_action": True, "qwen_llama_rows_separate": True,
            "no_model_or_runtime_loaded": True, "no_hardware_parameter_selected": True,
        },
        "boundaries": [
            "Head-local, layer-shared, and hierarchical rows observe exactly the same post-arrival/pre-grant pending snapshots and total logical capacity C per layer. They do not allocate storage, schedule admission, or change a grant, controller state, per-head order, or lifecycle state.",
            "Hierarchical private quota plus shared overflow is a capacity-affiliation sensitivity. Its overflow demand is aggregate; it does not claim a physical allocator, overflow arbitration, descriptor format, ownership transfer, port count, banking, or page layout.",
            "Cmin and bounded-breach frontiers are logical observer quantities under fixed traces and fixed causal grants. They are not FIFO depth, physical memory, bytes, HBM/DMA traffic, bandwidth, cycles, timing, latency, throughput, energy, area, net benefit, protection policy, architecture specification, or RTL evidence.",
            "A pure layer-shared pool has maximal logical pooling for a given C. The study measures the capacity tax of preserving private per-head reservations; it does not select layer-shared or hierarchical implementation.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a466_pending_organization_contract_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.6 pending-organization contract completed: {output}")


if __name__ == "__main__":
    main()
