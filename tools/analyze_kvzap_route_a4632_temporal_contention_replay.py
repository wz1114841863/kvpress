#!/usr/bin/env python3
"""A4.6.3.2 timestamp-free temporal abstract contention replay.

This replays logical append opportunities, not wall-clock time. Named A4.6.3.0
mappings are applied to each grant, so a lifecycle action is never silently
counted as payload movement. The resulting inventory is still not hardware data.
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
from tools.analyze_kvzap_route_a462_activation_service_envelope import SHARED_POLICY
from tools.analyze_kvzap_route_a4630_physicalization_mapping import EAGER_COPY, SEALED_COPY, SCHEMA as A4630_SCHEMA, page_events
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

SCHEMA = "kvzap-route-a4632-temporal-abstract-contention-replay-1.0"
HORIZONS = (8, 16, 32, 62)
POLICIES = ("strict_attention_first", "hard_reservation", "work_conserving_reserved_minimum", "backlog_deadline_aware")
HARD_RESERVATION_SHARE = 0.25
COST_PROFILES = {"payload_only": {"position": 0, "pte": 0, "seal": 0, "merge": 0}, "metadata_merge_sensitive": {"position": 1, "pte": 4, "seal": 4, "merge": 2}}
MAPPED_FIELDS = ("modeled_kv_payload_source_read_token_units", "modeled_kv_payload_packed_write_token_units", "modeled_position_metadata_update_records", "modeled_page_table_update_records", "modeled_page_seal_records", "modeled_post_service_dual_source_merge_state_records")
Stream = tuple[int, int]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.6.3.2 timestamp-free temporal abstract contention replay; no model execution, measured traffic/timing, or hardware selection.")
    p.add_argument("--a461-report", type=Path, required=True); p.add_argument("--a4630-report", type=Path, required=True)
    p.add_argument("--preflight-only", action="store_true", help="Validate hash-bound sources and mapping coverage without creating output.")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def source_streams(row: dict[str, Any]) -> tuple[dict[Stream, dict[str, int]], dict[Stream, list[int]]]:
    inventory: dict[Stream, dict[str, int]] = {}
    for item in row["activation_commit_logical_inventory_by_layer_kv_head"]:
        key = int(item["layer"]), int(item["kv_head"])
        if key in inventory: raise ValueError("duplicate activation inventory stream")
        pending, packed, hot = (int(item[name]) for name in ("pending_tokens_after_commit", "packed_tokens_after_commit", "hot_tokens_after_commit"))
        if min(pending, packed, hot) < 0: raise ValueError("negative activation inventory")
        inventory[key] = {"pending": pending, "packed": packed, "hot": hot}
    arrivals: dict[Stream, list[int]] = {key: [] for key in inventory}
    for item in row["post_commit_logical_append_events_by_layer_kv_head"]:
        key = int(item["layer"]), int(item["kv_head"])
        if key not in arrivals: raise ValueError("append stream absent from activation inventory")
        arrived = int(item["matured_kept_tokens"])
        if arrived < 0: raise ValueError("negative mature-kept arrival")
        arrivals[key].append(arrived)
    if not inventory or {len(values) for values in arrivals.values()} != {max(HORIZONS)}: raise ValueError("A4.6.1 does not provide the required 62 append opportunities")
    return inventory, arrivals


def minimum_reservation(quantum: int) -> int:
    if quantum < 0: raise ValueError("logical quantum must be nonnegative")
    return math.ceil(quantum * HARD_RESERVATION_SHARE)


def mapped_work(*, movement: str, page_tokens: int, packed_before: int, grant: int) -> dict[str, int]:
    """Apply a named A4.6.3.0 mapping to one actual temporal grant."""
    pages = page_events(packed_before, grant, page_tokens)
    if movement == EAGER_COPY: reads = writes = grant
    elif movement == SEALED_COPY: reads = writes = pages["newly_sealed_page_count"] * page_tokens
    else: raise ValueError(f"unknown mapping assumption: {movement}")
    return {"modeled_kv_payload_source_read_token_units": reads, "modeled_kv_payload_packed_write_token_units": writes, "modeled_position_metadata_update_records": grant, "modeled_page_table_update_records": pages["new_page_allocations"], "modeled_page_seal_records": pages["newly_sealed_page_count"], "modeled_post_service_dual_source_merge_state_records": 0}


def composite_work(mapped: dict[str, int], profile: dict[str, int]) -> int:
    return (mapped["modeled_kv_payload_source_read_token_units"] + mapped["modeled_kv_payload_packed_write_token_units"] + profile["position"] * mapped["modeled_position_metadata_update_records"] + profile["pte"] * mapped["modeled_page_table_update_records"] + profile["seal"] * mapped["modeled_page_seal_records"] + profile["merge"] * mapped["modeled_post_service_dual_source_merge_state_records"])


def service_target(*, policy: str, quantum: int, reservation: int, backlog_after_arrivals: int, future_arrivals: int, remaining_opportunities: int) -> int:
    if policy == "strict_attention_first": return 0
    if policy in {"hard_reservation", "work_conserving_reserved_minimum"}: return reservation
    if policy == "backlog_deadline_aware":
        # Offline bounded-horizon sensitivity using known recorded arrivals, not online control.
        return quantum if backlog_after_arrivals + future_arrivals > reservation * remaining_opportunities else reservation
    raise ValueError(f"unknown temporal policy: {policy}")


def terminal_drain(trace: list[int]) -> int | None:
    if not trace or trace[-1] != 0: return None
    last_positive = max((i + 1 for i, value in enumerate(trace) if value > 0), default=0)
    return last_positive + 1 if last_positive else 0


def layer_fairness(per_head: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in per_head: grouped[int(row["layer"])].append(row)
    result = []
    for layer, rows in sorted(grouped.items()):
        peaks = [int(row["B_max_h"]) for row in rows]; grants = [int(row["G_total_logical_admission_grant"]) for row in rows]
        terminal = [row["T_drain_h"] for row in rows if row["T_drain_h"] is not None]
        result.append({"layer": layer, "kv_head_count": len(rows), "B_max_h_min": min(peaks), "B_max_h_max": max(peaks), "B_max_h_spread": max(peaks) - min(peaks), "G_total_min": min(grants), "G_total_max": max(grants), "G_total_spread": max(grants) - min(grants), "T_drain_h_min": min(terminal) if terminal else None, "T_drain_h_max": max(terminal) if terminal else None, "T_drain_h_spread": max(terminal) - min(terminal) if terminal else None, "deadline_miss_head_count": sum(row["B_final_h"] > 0 for row in rows)})
    return result


def replay(*, inventory: dict[Stream, dict[str, int]], arrivals: dict[Stream, list[int]], variant: dict[str, Any], policy: str) -> dict[str, Any]:
    """Replay B[t+1] = max(0, B[t] + Anew[t] - G[t]) by layer/head."""
    horizon, quantum = int(variant["drain_horizon_append_opportunities"]), int(variant["minimum_logical_service_quantum"])
    movement, page_tokens = str(variant["mapping_assumption"]), int(variant["candidate_page_tokens"])
    heads = sorted(inventory); by_layer: dict[int, list[int]] = defaultdict(list)
    for layer, head in heads: by_layer[layer].append(head)
    pending = {key: inventory[key]["pending"] for key in heads}; packed = {key: inventory[key]["packed"] for key in heads}; grants = {key: 0 for key in heads}
    post_trace = {key: [] for key in heads}; pre_peak = {key: inventory[key]["pending"] for key in heads}; post_peak = dict(pre_peak); rr_next = {layer: 0 for layer in by_layer}; reservation = minimum_reservation(quantum)
    epochs: list[dict[str, Any]] = []; total_mapped = {field: 0 for field in MAPPED_FIELDS}; reservation_idle = 0; attention_borrowed = 0
    for t in range(horizon):
        b_before = sum(pending.values()); a_new = sum(arrivals[key][t] for key in heads)
        for key in heads:
            pending[key] += arrivals[key][t]; pre_peak[key] = max(pre_peak[key], pending[key])
        b_after_arrival = sum(pending.values())
        # This source count is invariant to pending-versus-packed placement after service.
        a_attn = sum(inventory[key]["hot"] + packed[key] + pending[key] for key in heads)
        epoch_grant = 0; epoch_mapped = {field: 0 for field in MAPPED_FIELDS}; epoch_minimum_target = 0
        for layer, layer_heads in sorted(by_layer.items()):
            layer_heads = sorted(layer_heads); layer_backlog = sum(pending[layer, head] for head in layer_heads); remaining = horizon - t
            future = sum(arrivals[layer, head][later] for head in layer_heads for later in range(t + 1, horizon))
            target = service_target(policy=policy, quantum=quantum, reservation=reservation, backlog_after_arrivals=layer_backlog, future_arrivals=future, remaining_opportunities=remaining)
            epoch_minimum_target += reservation if policy != "strict_attention_first" else 0
            if policy == "hard_reservation": reservation_idle += max(0, target - layer_backlog)
            elif policy == "work_conserving_reserved_minimum": attention_borrowed += max(0, quantum - min(target, layer_backlog))
            remaining_grant, misses = min(target, layer_backlog), 0
            while remaining_grant and misses < len(layer_heads):
                head = layer_heads[rr_next[layer] % len(layer_heads)]; key = layer, head; rr_next[layer] = (rr_next[layer] + 1) % len(layer_heads)
                if pending[key] == 0: misses += 1; continue
                pending[key] -= 1; grants[key] += 1; remaining_grant -= 1; epoch_grant += 1; misses = 0
                mapped = mapped_work(movement=movement, page_tokens=page_tokens, packed_before=packed[key], grant=1); packed[key] += 1
                for field in MAPPED_FIELDS: epoch_mapped[field] += mapped[field]; total_mapped[field] += mapped[field]
        # A4.6.3.0 maps dual-source merge state once per stream after all grants
        # in the append opportunity, rather than once for each token grant.
        for key in heads:
            merge = int(pending[key] > 0 and packed[key] > 0)
            epoch_mapped["modeled_post_service_dual_source_merge_state_records"] += merge
            total_mapped["modeled_post_service_dual_source_merge_state_records"] += merge
            post_trace[key].append(pending[key]); post_peak[key] = max(post_peak[key], pending[key])
        epochs.append({"append_opportunity": t + 1, "A_t_attn_source_traversal_token_units": a_attn, "A_t_new_mature_kept_logical_tokens": a_new, "B_t_before_arrivals_logical_tokens": b_before, "B_t_after_arrivals_logical_tokens": b_after_arrival, "G_t_logical_admission_grant": epoch_grant, "B_t_plus_1_after_grant_logical_tokens": sum(pending.values()), "minimum_admission_grant_target_logical_tokens": epoch_minimum_target, "G_t_mapped_work_components": epoch_mapped, "G_t_mapped_abstract_work_units_by_cost_profile": {name: composite_work(epoch_mapped, weights) for name, weights in COST_PROFILES.items()}})
    per_head = []
    for key in heads:
        tail = packed[key] % page_tokens
        per_head.append({"layer": key[0], "kv_head": key[1], "B_max_h": pre_peak[key], "B_max_h_after_grant": post_peak[key], "B_final_h": pending[key], "G_total_logical_admission_grant": grants[key], "T_drain_h": terminal_drain(post_trace[key]), "deadline_miss": pending[key] > 0, "packed_tokens_after_temporal_replay": packed[key], "current_tail_tokens": tail, "current_tail_unused_token_slots": 0 if tail == 0 else page_tokens - tail, "unsealed_tail_reference_token_units": tail if movement == SEALED_COPY else 0})
    b_max = max(row["B_t_after_arrivals_logical_tokens"] for row in epochs); t_drain = terminal_drain([row["B_t_plus_1_after_grant_logical_tokens"] for row in epochs])
    return {"policy": policy, "B_max": b_max, "B_max_after_grant": max(row["B_t_plus_1_after_grant_logical_tokens"] for row in epochs), "B_final": sum(pending.values()), "T_drain": t_drain, "T_drain_censored_at_horizon": t_drain is None, "deadline_miss_head_count": sum(row["deadline_miss"] for row in per_head), "attention_service_occupied_by_admission_abstract_work_units": {name: composite_work(total_mapped, weights) for name, weights in COST_PROFILES.items()}, "reservation_idle_logical_tokens": reservation_idle, "attention_borrowed_logical_admission_capacity": attention_borrowed, "mapped_admission_work_components": total_mapped, "endpoint_unsealed_tail_reference_token_units": sum(row["unsealed_tail_reference_token_units"] for row in per_head), "per_head": per_head, "per_layer_fairness": layer_fairness(per_head), "epoch_records": epochs}


def selected_variants(row: dict[str, Any]) -> list[dict[str, Any]]:
    selected = [v for v in row["mapping_variants"] if v["policy"] == SHARED_POLICY and int(v["drain_horizon_append_opportunities"]) in HORIZONS]
    if len(selected) != len(HORIZONS) * 2 * 3: raise ValueError("A4.6.3.0 lacks expected layer-shared mapping variants")
    return selected


def main() -> None:
    args = parse_args()
    if args.output_dir.exists(): raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a461 = read_completed(args.a461_report, A461_SCHEMA, "A4.6.1"); a4630 = read_completed(args.a4630_report, A4630_SCHEMA, "A4.6.3.0")
    if a4630.get("input_artifacts", {}).get("a461_report_sha256") != sha256_file(args.a461_report): raise ValueError("A4.6.3.0 does not hash-bind this A4.6.1 report")
    source = {(row["anchor"], row["workload"]): row for row in a461["anchor_rows"]}; mapped = {(row["anchor"], row["workload"]): row for row in a4630["anchor_rows"]}
    if set(source) != set(mapped) or len(source) != 6: raise ValueError("A4.6.1/A4.6.3.0 anchor-workload coverage mismatch")
    for row in mapped.values(): selected_variants(row)
    if args.preflight_only:
        print("A4.6.3.2 preflight passed: A4.6.1/A4.6.3.0 hash binding and layer-shared mapping coverage validated; no output created."); return
    rows = []
    for key in sorted(source):
        inventory, arrivals = source_streams(source[key]); variants = []
        for variant in selected_variants(mapped[key]):
            variants.append({"a462_policy": variant["policy"], "quantum_scope": variant["quantum_scope"], "drain_horizon_append_opportunities": variant["drain_horizon_append_opportunities"], "minimum_logical_service_quantum": variant["minimum_logical_service_quantum"], "mapping_assumption": variant["mapping_assumption"], "candidate_page_tokens": variant["candidate_page_tokens"], "temporal_policies": [replay(inventory=inventory, arrivals=arrivals, variant=variant, policy=policy) for policy in POLICIES]})
        rows.append({"anchor": key[0], "workload": key[1], "contention_variants": variants})
    config = {"a461_report": str(args.a461_report), "a4630_report": str(args.a4630_report), "drain_horizons_append_opportunities": list(HORIZONS), "temporal_policies": list(POLICIES), "hard_reservation_share": HARD_RESERVATION_SHARE, "cost_profiles": COST_PROFILES, "input_selection": "A4.6.2 layer-shared candidates only; independent per-head service remains its earlier optimistic bound and is not presented as a shared contention fabric."}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model timestamp-free temporal abstract contention replay over trace-derived arrivals and named modeled A4.6.3.0 mappings; not measured hardware evidence", "input_artifacts": {"a461_report_sha256": sha256_file(args.a461_report), "a4630_report_sha256": sha256_file(args.a4630_report)}, "anchor_rows": rows, "observational_guards": {"a461_a4630_hash_binding_validated": True, "four_temporal_policies_compared": True, "epoch_A_attn_A_new_B_G_fields_recorded": True, "per_head_backlog_deadline_and_fairness_recorded": True, "actual_grants_pass_through_named_a4630_mapping": True, "independent_a462_policy_kept_only_as_prior_optimistic_bound": True, "qwen_llama_rows_separate": True, "no_model_or_runtime_loaded": True, "no_hardware_parameter_selected": True}, "boundaries": ["An append opportunity is a timestamp-free logical replay epoch. A_t_attn is a retained-source traversal count, A_t_new is mature-kept logical arrival, B is logical pending backlog, and G is a logical admission grant. The recorded recurrence is B[t+1]=max(0, B[t]+A_new[t]-G[t]).", "Each G is mapped with the named eager-copy or sealed-page-with-tail-reference A4.6.3.0 assumption. Payload token units, PTE/page-seal/position records, merge-state records, and endpoint tail references are modeled inventories only. They are not measured KV reads/writes, bytes, HBM/DMA traffic, transactions, bandwidth, cycles, latency, throughput, energy, area, FIFO depth, or hardware service.", "The hard reservation is a pessimistic non-borrowing baseline. The work-conserving policy guarantees only its declared minimum while backlog exists and lends unused logical admission capacity to attention. The deadline-aware policy is an offline bounded-horizon sensitivity using recorded future arrivals, not an online scheduler proposal.", "Cost profiles produce only named abstract composite-work accounting. Attention service occupied by admission is not a measured attention delay or a claim that a single real fabric carries these operations. No mapping, page size, reservation, scheduler, controller, or resource point is selected; the trace horizon does not prove unbounded stability, physical implementability, net benefit, or RTL readiness."]}
    args.output_dir.mkdir(parents=True); output = args.output_dir / "a4632_temporal_contention_replay_report.json"; output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.6.3.2 temporal contention replay completed: {output}")


if __name__ == "__main__": main()
