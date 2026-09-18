#!/usr/bin/env python3
"""A4.6.3.0 explicit physicalization-work mapping over A4.6.2 envelopes."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import A442_SCHEMA, A460_SCHEMA, SCHEMA as A461_SCHEMA, WORKLOADS, read_completed
from tools.analyze_kvzap_route_a462_activation_service_envelope import INDEPENDENT_POLICY, SHARED_POLICY, SCHEMA as A462_SCHEMA, require_completed_chain, workload_streams
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

SCHEMA = "kvzap-route-a4630-physicalization-mapping-contract-1.0"
PAGE_TOKENS = (16, 64, 128)
EAGER_COPY = "eager_copy_on_logical_service"
SEALED_COPY = "sealed_page_copy_with_unsealed_tail_reference"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.6.3.0 explicit Route-A physicalization mapping; modeled work inventory only, no measured traffic/timing or hardware selection.")
    p.add_argument("--a442-report", type=Path, required=True); p.add_argument("--qwen-a460-report", type=Path, required=True); p.add_argument("--llama-a460-report", type=Path, required=True)
    p.add_argument("--a461-report", type=Path, required=True); p.add_argument("--a462-report", type=Path, required=True)
    p.add_argument("--preflight-only", action="store_true"); p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def page_events(initial_packed: int, service: int, page_tokens: int) -> dict[str, int]:
    if min(initial_packed, service) < 0 or page_tokens <= 0: raise ValueError("invalid page mapping inputs")
    final = initial_packed + service
    alloc = (final + page_tokens - 1) // page_tokens - (initial_packed + page_tokens - 1) // page_tokens
    sealed = final // page_tokens - initial_packed // page_tokens
    tail = final % page_tokens
    return {"packed_tokens_after_mapping": final, "new_page_allocations": alloc, "newly_sealed_page_count": sealed, "current_tail_tokens": tail, "current_tail_unused_token_slots": 0 if tail == 0 else page_tokens - tail}


def head_inventory(a461_row: dict[str, Any]) -> dict[tuple[int, int], dict[str, int]]:
    out = {}
    for x in a461_row["activation_commit_logical_inventory_by_layer_kv_head"]:
        key = int(x["layer"]), int(x["kv_head"])
        if key in out: raise ValueError("duplicate A4.6.1 activation head")
        if int(x["matured_kept_tokens"]) != int(x["pending_tokens_after_commit"]) + int(x["admitted_tokens"]): raise ValueError("activation conservation failure")
        out[key] = {"pending": int(x["pending_tokens_after_commit"]), "packed": int(x["packed_tokens_after_commit"]), "hot": int(x["hot_tokens_after_commit"])}
    return out


def candidate_states(initial: dict[tuple[int, int], int], arrivals: dict[tuple[int, int], list[int]], packed_initial: dict[tuple[int, int], int], *, policy: str, quantum: int, horizon: int) -> dict[tuple[int, int], dict[str, Any]]:
    pending = dict(initial); granted = {k: 0 for k in initial}; dual = {k: 0 for k in initial}; source_visits = {k: 0 for k in initial}
    if policy == INDEPENDENT_POLICY:
        for t in range(horizon):
            for key in sorted(pending):
                pending[key] += arrivals[key][t]; g = min(quantum, pending[key]); pending[key] -= g; granted[key] += g
                dual[key] += int(pending[key] > 0 and packed_initial[key] + granted[key] > 0)
    elif policy == SHARED_POLICY:
        layers: dict[int, list[int]] = defaultdict(list)
        for layer, head in pending: layers[layer].append(head)
        rr = {layer: 0 for layer in layers}
        for t in range(horizon):
            for key in pending: pending[key] += arrivals[key][t]
            for layer, heads in layers.items():
                heads = sorted(heads); left = quantum; misses = 0
                while left and misses < len(heads):
                    i = rr[layer] % len(heads); key = layer, heads[i]; rr[layer] = (i + 1) % len(heads)
                    if pending[key]: pending[key] -= 1; granted[key] += 1; left -= 1; misses = 0
                    else: misses += 1
            for key in pending: dual[key] += int(pending[key] > 0 and packed_initial[key] + granted[key] > 0)
    else: raise ValueError("unknown A4.6.2 policy")
    return {k: {"granted": granted[k], "final_pending": pending[k], "pending_nonzero_post_service_opportunities": dual[k]} for k in pending}


def map_point(*, a461_row: dict[str, Any], a462_point: dict[str, Any], policy: str, page_tokens: int, movement: str) -> dict[str, Any]:
    inv = head_inventory(a461_row); initial, arrivals, _ = workload_streams(a461_row)
    horizon = int(a462_point["drain_horizon_append_opportunities"]); quantum = int(a462_point["minimum_logical_service_quantum"])
    state = candidate_states(initial, arrivals, {key: value["packed"] for key, value in inv.items()}, policy=policy, quantum=quantum, horizon=horizon)
    recorded = {(int(x["layer"]), int(x["kv_head"])): x for x in a462_point["per_head_backlog"]}
    rows = []
    for key in sorted(inv):
        s, r = state[key], recorded[key]
        if s["granted"] != int(r["logical_service_tokens_granted"]) or s["final_pending"] != int(r["final_pending_after_service"]): raise ValueError("A4.6.2 candidate replay disagrees with recorded per-head state")
        service, pages = s["granted"], page_events(inv[key]["packed"], s["granted"], page_tokens)
        if movement == EAGER_COPY: reads = writes = service; deferred = 0
        elif movement == SEALED_COPY: reads = writes = pages["newly_sealed_page_count"] * page_tokens; deferred = pages["current_tail_tokens"]
        else: raise ValueError("unknown movement mapping")
        # A merge-state record is explicitly mapped only after post-service pending and packed sources coexist.
        merge = s["pending_nonzero_post_service_opportunities"]
        rows.append({"layer": key[0], "kv_head": key[1], "logical_service_tokens": service, "modeled_kv_payload_source_read_token_units": reads, "modeled_kv_payload_packed_write_token_units": writes, "modeled_position_metadata_update_records": service, "modeled_page_table_update_records": pages["new_page_allocations"], "modeled_page_seal_records": pages["newly_sealed_page_count"], "modeled_post_service_dual_source_merge_state_records": merge, "modeled_post_service_pending_nonzero_opportunities": s["pending_nonzero_post_service_opportunities"], "unsealed_tail_reference_token_units": deferred, **pages})
    totals = {field: sum(int(x[field]) for x in rows) for field in rows[0] if field.startswith("modeled_") or field in {"logical_service_tokens", "new_page_allocations", "newly_sealed_page_count", "unsealed_tail_reference_token_units"}}
    return {"policy": policy, "drain_horizon_append_opportunities": horizon, "minimum_logical_service_quantum": quantum, "quantum_scope": a462_point["quantum_scope"], "mapping_assumption": movement, "candidate_page_tokens": page_tokens, "per_head_physicalization_work": rows, "totals": totals}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists(): raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a461 = require_completed_chain(a442_path=args.a442_report, qwen_path=args.qwen_a460_report, llama_path=args.llama_a460_report, a461_path=args.a461_report)
    a462 = read_completed(args.a462_report, A462_SCHEMA, "A4.6.2")
    if a462.get("input_artifacts", {}).get("a461_report_sha256") != sha256_file(args.a461_report): raise ValueError("A4.6.2 does not hash-bind this A4.6.1 report")
    source = {(x["anchor"], x["workload"]): x for x in a461["anchor_rows"]}; modeled = {(x["anchor"], x["workload"]): x for x in a462["anchor_rows"]}
    expected = {(a, w) for a in ("qwen3_8b", "llama31_8b_instruct") for w in WORKLOADS}
    if set(source) != expected or set(modeled) != expected: raise ValueError("A4.6 source rows incomplete")
    if args.preflight_only:
        print("A4.6.3.0 preflight passed: A4.4.2/A4.6.0/A4.6.1/A4.6.2 hash chain and candidate replays validated; no output created."); return
    rows = []
    for key in sorted(expected):
        variants = []
        for policy, envelope in modeled[key]["policy_envelopes"].items():
            for point in envelope:
                for page in PAGE_TOKENS:
                    for movement in (EAGER_COPY, SEALED_COPY): variants.append(map_point(a461_row=source[key], a462_point=point, policy=policy, page_tokens=page, movement=movement))
        rows.append({"anchor": key[0], "workload": key[1], "mapping_variants": variants})
    config = {"a442_report": str(args.a442_report), "qwen_a460_report": str(args.qwen_a460_report), "llama_a460_report": str(args.llama_a460_report), "a461_report": str(args.a461_report), "a462_report": str(args.a462_report), "candidate_page_tokens": list(PAGE_TOKENS), "movement_mappings": [EAGER_COPY, SEALED_COPY]}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model explicit physicalization mapping sensitivity over trace-derived/functional inputs and modeled logical service envelopes; not measured physical traffic or timing evidence", "input_artifacts": {"a442_report_sha256": sha256_file(args.a442_report), "qwen_a460_report_sha256": sha256_file(args.qwen_a460_report), "llama_a460_report_sha256": sha256_file(args.llama_a460_report), "a461_report_sha256": sha256_file(args.a461_report), "a462_report_sha256": sha256_file(args.a462_report)}, "anchor_rows": rows, "observational_guards": {"complete_hash_chain_validated": True, "a462_per_head_candidate_replay_matches": True, "logical_transition_not_automatically_counted_as_payload_movement": True, "all_payload_movement_has_named_mapping_assumption": True, "page_tail_pte_position_and_merge_work_recorded": True, "qwen_llama_rows_separate": True, "no_model_or_runtime_loaded": True, "no_hardware_parameter_selected": True}, "boundaries": ["A4.6.3.0 records modeled token-unit/record work under named mapping assumptions. These are not measured KV reads/writes, HBM/DMA traffic, bytes, transactions, bandwidth, latency, throughput, energy, area, or hardware activity.", "Eager copy maps each logical service token to one source-read and packed-write unit. Sealed-page copy maps payload movement only at declared page seals and leaves the current tail as an explicit reference/deferred unit. Neither mapping is selected as an implementation.", "Post-service dual-source merge records use an explicit candidate-state order and are a mapping inventory only; they do not establish native attention ordering or traffic. A4.6.3.1 must separately place these inventories with attention work into an abstract contention model."]}
    args.output_dir.mkdir(parents=True); out = args.output_dir / "a4630_physicalization_mapping_contract_report.json"; out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(f"A4.6.3.0 physicalization mapping completed: {out}")

if __name__ == "__main__": main()
