#!/usr/bin/env python3
"""A4.6.2 multi-horizon logical admission-service envelope model.

The model consumes A4.6.1's timestamp-free activation inventory and append
arrival records.  A quantum is deliberately a logical tokens-per-append-
opportunity model input: it has no cycle, bandwidth, FIFO, or physical meaning.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import A442_SCHEMA, A460_SCHEMA, SCHEMA as A461_SCHEMA, WORKLOADS, read_completed
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a462-activation-logical-service-envelope-1.0"
HORIZONS = (1, 2, 4, 8, 16, 32, 62)
INDEPENDENT_POLICY = "independent_per_layer_kv_head_fixed_quantum_optimistic_bound"
SHARED_POLICY = "per_layer_shared_unit_token_round_robin_nonempty_heads"
Stream = tuple[int, int]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.6.2 multi-horizon logical admission-service envelope; no model execution, cycles, FIFO, bandwidth, or hardware parameter selection.")
    p.add_argument("--a442-report", type=Path, required=True)
    p.add_argument("--qwen-a460-report", type=Path, required=True)
    p.add_argument("--llama-a460-report", type=Path, required=True)
    p.add_argument("--a461-report", type=Path, required=True)
    p.add_argument("--preflight-only", action="store_true", help="Validate the complete hash-bound source chain without creating output.")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def require_completed_chain(*, a442_path: Path, qwen_path: Path, llama_path: Path, a461_path: Path) -> dict[str, Any]:
    a442 = read_completed(a442_path, A442_SCHEMA, "A4.4.2")
    a461 = read_completed(a461_path, A461_SCHEMA, "A4.6.1")
    inputs = {"qwen3_8b": qwen_path, "llama31_8b_instruct": llama_path}
    for anchor, path in inputs.items():
        a460 = read_completed(path, A460_SCHEMA, anchor)
        item = a461.get("input_artifacts", {}).get(anchor, {})
        if item.get("a460_report_sha256") != sha256_file(path):
            raise ValueError(f"{anchor}: A4.6.1 does not hash-bind this A4.6.0 report")
        if a460.get("provenance", {}).get("a442_report_sha256") != sha256_file(a442_path):
            raise ValueError(f"{anchor}: A4.6.0 does not hash-bind this A4.4.2 report")
        if anchor not in a442.get("input_artifacts", {}):
            raise ValueError(f"{anchor}: A4.4.2 source row absent")
    if {row.get("anchor") for row in a461.get("anchor_rows", [])} != set(inputs):
        raise ValueError("A4.6.1 lacks both anchor rows")
    return a461


def workload_streams(row: dict[str, Any]) -> tuple[dict[Stream, int], dict[Stream, list[int]], int]:
    activation = row.get("activation_commit_logical_inventory_by_layer_kv_head", [])
    appends = row.get("post_commit_logical_append_events_by_layer_kv_head", [])
    initial: dict[Stream, int] = {}
    for item in activation:
        key = (int(item["layer"]), int(item["kv_head"]))
        if key in initial or int(item.get("pending_tokens_after_commit", -1)) < 0:
            raise ValueError("invalid or duplicate A4.6.1 activation stream")
        if int(item["matured_kept_tokens"]) != int(item["pending_tokens_after_commit"]) + int(item["admitted_tokens"]):
            raise ValueError("activation inventory conservation failure")
        if int(item["packed_tokens_after_commit"]) != int(item["admitted_tokens"]):
            raise ValueError("activation packed inventory conservation failure")
        initial[key] = int(item["pending_tokens_after_commit"])
    arrivals: dict[Stream, list[int]] = {key: [] for key in initial}
    for item in appends:
        key = (int(item["layer"]), int(item["kv_head"]))
        if key not in arrivals or int(item.get("matured_kept_tokens", -1)) < 0:
            raise ValueError("A4.6.1 append stream does not match activation inventory")
        arrivals[key].append(int(item["matured_kept_tokens"]))
    lengths = {len(values) for values in arrivals.values()}
    if not initial or len(lengths) != 1 or next(iter(lengths)) < max(HORIZONS):
        raise ValueError("A4.6.1 lacks required multi-horizon append coverage")
    return initial, arrivals, next(iter(lengths))


def make_head_record(*, key: Stream, initial: int, arrivals: list[int], served: int, post_service: list[int]) -> dict[str, Any]:
    last_positive = max((i + 1 for i, value in enumerate(post_service) if value > 0), default=0)
    first_zero = next((i + 1 for i, value in enumerate(post_service) if value == 0), None)
    reaccumulated = first_zero is not None and any(value > 0 for value in post_service[first_zero:])
    final = post_service[-1]
    if final != initial + sum(arrivals) - served:
        raise AssertionError("logical backlog conservation failure")
    return {"layer": key[0], "kv_head": key[1], "initial_pending_tokens_after_commit": initial, "matured_kept_arrivals_within_horizon": sum(arrivals), "logical_service_tokens_granted": served, "max_pending_after_service": max(post_service, default=initial), "final_pending_after_service": final, "first_zero_after_service_opportunity": first_zero, "reaccumulated_after_first_zero": reaccumulated, "terminal_drain_opportunity": None if final else last_positive + 1 if last_positive else 0}


def simulate_independent(initial: dict[Stream, int], arrivals: dict[Stream, list[int]], *, quantum: int, horizon: int) -> list[dict[str, Any]]:
    if quantum < 0:
        raise ValueError("logical service quantum must be nonnegative")
    rows = []
    for key in sorted(initial):
        pending, served, trace = initial[key], 0, []
        for arrival in arrivals[key][:horizon]:
            pending += arrival
            grant = min(quantum, pending)
            pending -= grant; served += grant; trace.append(pending)
        rows.append(make_head_record(key=key, initial=initial[key], arrivals=arrivals[key][:horizon], served=served, post_service=trace))
    return rows


def simulate_layer_shared_round_robin(initial: dict[Stream, int], arrivals: dict[Stream, list[int]], *, quantum: int, horizon: int) -> list[dict[str, Any]]:
    if quantum < 0:
        raise ValueError("logical service quantum must be nonnegative")
    by_layer: dict[int, list[int]] = defaultdict(list)
    for layer, head in initial:
        by_layer[layer].append(head)
    states = {key: initial[key] for key in initial}; served = {key: 0 for key in initial}; traces = {key: [] for key in initial}
    rr_next = {layer: 0 for layer in by_layer}
    for opportunity in range(horizon):
        for key in states:
            states[key] += arrivals[key][opportunity]
        for layer, heads in by_layer.items():
            heads = sorted(heads); remaining = quantum; misses = 0
            while remaining and misses < len(heads):
                index = rr_next[layer] % len(heads); key = (layer, heads[index])
                rr_next[layer] = (index + 1) % len(heads)
                if states[key] > 0:
                    states[key] -= 1; served[key] += 1; remaining -= 1; misses = 0
                else:
                    misses += 1
        for key in states:
            traces[key].append(states[key])
    return [make_head_record(key=key, initial=initial[key], arrivals=arrivals[key][:horizon], served=served[key], post_service=traces[key]) for key in sorted(initial)]


def drains(rows: list[dict[str, Any]]) -> bool:
    return all(int(row["final_pending_after_service"]) == 0 for row in rows)


def minimum_quantum(initial: dict[Stream, int], arrivals: dict[Stream, list[int]], *, horizon: int, policy: str) -> tuple[int, list[dict[str, Any]]]:
    simulator = simulate_independent if policy == INDEPENDENT_POLICY else simulate_layer_shared_round_robin
    # One quantum at the first opportunity can service every recorded input, so this is a valid finite upper bound.
    if policy == INDEPENDENT_POLICY:
        high = max(initial[key] + sum(arrivals[key][:horizon]) for key in initial)
    elif policy == SHARED_POLICY:
        high = max(sum(initial[(layer, head)] + sum(arrivals[(layer, head)][:horizon]) for head in {h for l, h in initial if l == layer}) for layer in {l for l, _ in initial})
    else:
        raise ValueError(f"unknown policy: {policy}")
    low = 0
    while low < high:
        candidate = (low + high) // 2
        if drains(simulator(initial, arrivals, quantum=candidate, horizon=horizon)):
            high = candidate
        else:
            low = candidate + 1
    result = simulator(initial, arrivals, quantum=low, horizon=horizon)
    if not drains(result):
        raise AssertionError("minimum logical service search did not drain its bounded horizon")
    return low, result


def fairness(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["layer"])].append(row)
    output = []
    for layer, group in sorted(grouped.items()):
        terminal = [int(x["terminal_drain_opportunity"]) for x in group if x["terminal_drain_opportunity"] is not None]
        if len(terminal) != len(group):
            raise AssertionError("minimum envelope must drain every head")
        peaks = [int(x["max_pending_after_service"]) for x in group]
        services = [int(x["logical_service_tokens_granted"]) for x in group]
        output.append({"layer": layer, "kv_head_count": len(group), "terminal_drain_opportunity_min": min(terminal), "terminal_drain_opportunity_max": max(terminal), "terminal_drain_opportunity_spread": max(terminal) - min(terminal), "peak_pending_after_service_min": min(peaks), "peak_pending_after_service_max": max(peaks), "peak_pending_after_service_spread": max(peaks) - min(peaks), "logical_service_tokens_granted_min": min(services), "logical_service_tokens_granted_max": max(services), "logical_service_tokens_granted_spread": max(services) - min(services)})
    return output


def model_policy(initial: dict[Stream, int], arrivals: dict[Stream, list[int]], *, policy: str) -> list[dict[str, Any]]:
    output = []
    for horizon in HORIZONS:
        quantum, heads = minimum_quantum(initial, arrivals, horizon=horizon, policy=policy)
        output.append({"drain_horizon_append_opportunities": horizon, "minimum_logical_service_quantum": quantum, "quantum_scope": "per_layer_kv_head" if policy == INDEPENDENT_POLICY else "per_layer_shared_across_kv_heads", "all_heads_drained_at_horizon": True, "per_head_backlog": heads, "per_layer_fairness": fairness(heads)})
    return output


def model_row(row: dict[str, Any]) -> dict[str, Any]:
    initial, arrivals, observed_horizon = workload_streams(row)
    return {"anchor": row["anchor"], "workload": row["workload"], "context_tokens": row["context_tokens"], "observed_post_commit_append_opportunities_per_stream": observed_horizon, "input_interpretation": "initial pending is activation-commit logical state; mature-kept is the post-commit logical arrival sequence; recorded A4.6.1 admission actions are deliberately not used as a service-rate input", "policy_envelopes": {INDEPENDENT_POLICY: model_policy(initial, arrivals, policy=INDEPENDENT_POLICY), SHARED_POLICY: model_policy(initial, arrivals, policy=SHARED_POLICY)}}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a461 = require_completed_chain(a442_path=args.a442_report, qwen_path=args.qwen_a460_report, llama_path=args.llama_a460_report, a461_path=args.a461_report)
    rows = a461.get("anchor_rows", [])
    if {(row.get("anchor"), row.get("workload")) for row in rows} != {(anchor, workload) for anchor in ("qwen3_8b", "llama31_8b_instruct") for workload in WORKLOADS}:
        raise ValueError("A4.6.1 does not contain exactly six anchor/workload rows")
    if args.preflight_only:
        print("A4.6.2 preflight passed: full A4.4.2/A4.6.0/A4.6.1 hash chain and multi-horizon inputs validated; no output created.")
        return
    config = {"a442_report": str(args.a442_report), "qwen_a460_report": str(args.qwen_a460_report), "llama_a460_report": str(args.llama_a460_report), "a461_report": str(args.a461_report), "drain_horizons_append_opportunities": list(HORIZONS), "policies": [INDEPENDENT_POLICY, SHARED_POLICY], "comparison_rule": "per-anchor/per-workload rows remain separate; independent is an optimistic bound and shared uses unit-token round-robin competition; no cross-anchor pooling or parameter selection"}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model logical backlog-service sensitivity model over hash-bound trace-derived/functional inputs; not measured hardware evidence", "input_artifacts": {"a442_report_sha256": sha256_file(args.a442_report), "qwen_a460_report_sha256": sha256_file(args.qwen_a460_report), "llama_a460_report_sha256": sha256_file(args.llama_a460_report), "a461_report_sha256": sha256_file(args.a461_report)}, "anchor_rows": [model_row(row) for row in rows], "observational_guards": {"complete_a442_a460_a461_hash_chain_validated": True, "all_six_anchor_workload_rows_kept_separate": True, "multiple_drain_horizons_modeled": True, "per_head_backlog_and_fairness_recorded": True, "independent_policy_marked_optimistic_bound": True, "layer_shared_policy_uses_declared_round_robin_competition": True, "recorded_a461_admitted_tokens_not_reused_as_service_rate": True, "cross_anchor_numeric_pooling_or_parameter_derivation_absent": True, "no_model_or_runtime_loaded": True, "no_hardware_parameter_selected": True}, "boundaries": ["A4.6.2 logical service quantum is an abstract tokens-per-append-opportunity sensitivity variable. It is not a cycle, service rate, FIFO depth, bandwidth, HBM/DMA transfer, page/bank/PTE resource, or hardware parameter.", "Independent per-(layer, KV-head) service is only an optimistic no-competition bound. Per-layer shared service uses a declared unit-token round-robin allocation to expose head competition and fairness sensitivity; neither policy claims to be a hardware scheduler.", "Every result is bounded by the recorded post-commit append opportunities. A minimum quantum means only that this model drains the stated trace prefix by the stated logical horizon; it does not prove an unbounded workload, physical implementability, net benefit, or Route-A-native overload protection.", "Qwen and Llama remain separate and are not pooled, normalized, range-reduced, or used to freeze a common hardware design. The report is an input to later physicalization-cost and attention/admission-contention DSE, not either DSE."]}
    args.output_dir.mkdir(parents=True)
    out = args.output_dir / "a462_activation_logical_service_envelope_report.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.2 activation logical service envelope completed: {out}")


if __name__ == "__main__":
    main()
