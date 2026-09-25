#!/usr/bin/env python3
"""A4.10 queue/staging/credit resource-contract DSE (no model/RTL)."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a480_commit_aware_backlog import dependency_predecessors, iter_contexts, make_scheduled_transactions
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash
from tools.simulate_kvzap_route_a491_candidate_metadata_engine import CANDIDATES, LAYOUT
from tools.simulate_kvzap_route_a492_record_granular_engine import SCHEMA as A492_SCHEMA, build_micro_ops, micro_op_duration

SCHEMA = "kvzap-route-a410-queue-staging-credit-contract-1.0"
LOCAL_CAPACITY = 32
SHARED_CAPACITY = 256
STAGING_CAPACITY = 512
QUEUE_REFERENCE_WORD_BITS = 64
CANDIDATE_NAMES = ("ha8_base", "ha8_wide")
ORGANIZATIONS = (
    {"name": "local_q32_shared_unbounded_envelope", "shared_capacity_per_layer": None, "staging_capacity_per_layer": 0, "credit_control": False},
    {"name": "local_q32_shared_q256_credit", "shared_capacity_per_layer": SHARED_CAPACITY, "staging_capacity_per_layer": 0, "credit_control": True},
    {"name": "local_q32_shared_q256_staging_q512_credit", "shared_capacity_per_layer": SHARED_CAPACITY, "staging_capacity_per_layer": STAGING_CAPACITY, "credit_control": True},
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.10 declared queue/staging/credit resource-contract replay; no timing, macro, or RTL claim.")
    p.add_argument("--a468220-trace", type=Path, required=True)
    p.add_argument("--a471-trace", type=Path, required=True)
    p.add_argument("--a492-report", type=Path, required=True)
    p.add_argument("--post-trace-cycle-limit", type=int, default=4096)
    p.add_argument("--preflight-only", action="store_true")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def summary(values: list[int]) -> dict[str, int]:
    if not values: return {"count": 0, "min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "sum": 0}
    values = sorted(values); n = len(values)
    return {"count": n, "min": values[0], "p50": values[int((n-1)*.5)], "p95": values[int((n-1)*.95)], "p99": values[int((n-1)*.99)], "max": values[-1], "sum": sum(values)}


def key_of(row: dict[str, Any]) -> tuple[str, str, int, str, str]:
    return (str(row["anchor"]), str(row["workload"]), int(row["evaluation_horizon_append_opportunities"]), str(row["organization_label"]), str(row["candidate"]["name"]))


def validate(args: argparse.Namespace) -> dict[str, Any]:
    a492 = read_completed(args.a492_report, A492_SCHEMA, "A4.9.2")
    needed = (
        "a491_hash_chain_candidate_catalog_and_exact_baseline_reproduction_validated",
        "immutable_transaction_groups_predecessors_fifo_and_single_commit_boundary_unchanged",
        "record_granular_interleaving_is_internal_and_all_external_publication_is_commit_gated",
        "same_record_lock_is_explicit_and_released_only_at_group_commit",
        "queue_overflow_is_observed_never_dropped",
        "no_third_execution_granularity_or_semantic_variant_introduced",
    )
    if not all(a492.get("semantic_guards", {}).get(item) is True for item in needed): raise ValueError("A4.9.2 guards incomplete")
    inputs = a492.get("input_artifacts", {})
    if inputs.get("a468220_trace_sha256") != sha256_file(args.a468220_trace): raise ValueError("A4.9.2 record-trace hash mismatch")
    if inputs.get("a471_trace_sha256") != sha256_file(args.a471_trace): raise ValueError("A4.9.2 transaction-trace hash mismatch")
    if a492.get("config", {}).get("fixed_layout") != LAYOUT: raise ValueError("A4.9.2 layout changed")
    catalog = {item["name"]: item for item in a492.get("config", {}).get("candidates", [])}
    if set(CANDIDATE_NAMES) - set(catalog): raise ValueError("required HA8 candidates absent")
    rows = {key_of(row): row for row in a492.get("candidate_context_rows", [])}
    if len(rows) != len(a492.get("candidate_context_rows", [])): raise ValueError("duplicate A4.9.2 rows")
    if args.post_trace_cycle_limit < 0: raise ValueError("negative drain limit")
    return {"a492": a492, "catalog": catalog, "rows": rows}


def replay(transactions: list[Any], opportunities: list[tuple[str, int]], members: dict[int, tuple[Any, ...]], candidate: dict[str, Any], org: dict[str, Any], drain_limit: int) -> dict[str, Any]:
    """Lossless queue hierarchy; state is published only by the fixed commit."""
    arrivals: dict[int, list[int]] = defaultdict(list)
    for tx in transactions: arrivals[tx.arrival_ordinal].append(tx.index)
    location: dict[int, str] = {}
    committed, started, completed = set(), defaultdict(set), defaultdict(set)
    locks: dict[Any, int] = {}; active: list[tuple[int, Any]] = []
    local: set[int] = set(); shared: set[int] = set(); staging: set[int] = set(); held: set[int] = set()
    local_samples: list[list[int]] = [[] for _ in range(candidate["banks"])]
    shared_samples: dict[int, list[int]] = defaultdict(list); staging_samples: dict[int, list[int]] = defaultdict(list)
    active_samples: list[int] = []; held_samples: list[int] = []; bp_flags: list[bool] = []; stranded_samples: list[int] = []
    reasons: Counter[str] = Counter(); bp_events = 0; coordinator_until = 0; tick = 0; last = len(opportunities)-1
    def local_counts() -> Counter[int]: return Counter(bank for i in local for bank in transactions[i].banks)
    def layer_count(pool: set[int], layer: int) -> int: return sum(transactions[i].layer == layer for i in pool)
    def can_local(i: int) -> bool:
        counts = local_counts(); return all(counts[b] < LOCAL_CAPACITY for b in transactions[i].banks)
    def put_arrival(i: int) -> None:
        nonlocal bp_events
        layer = transactions[i].layer
        if can_local(i): local.add(i); location[i] = "local"; return
        cap = org["shared_capacity_per_layer"]
        if cap is None or layer_count(shared, layer) < cap: shared.add(i); location[i] = "shared"; return
        if org["staging_capacity_per_layer"] and layer_count(staging, layer) < org["staging_capacity_per_layer"]: staging.add(i); location[i] = "staging"; return
        held.add(i); location[i] = "held"; bp_events += 1
    def advance_buffers() -> None:
        # Stable transaction order; transfers never alter transaction identity or commit order.
        changed = True
        while changed:
            changed = False
            for i in sorted(staging):
                cap = org["shared_capacity_per_layer"]
                if cap is None or layer_count(shared, transactions[i].layer) < cap:
                    staging.remove(i); shared.add(i); location[i] = "shared"; changed = True
            for i in sorted(held):
                if org["staging_capacity_per_layer"] and layer_count(staging, transactions[i].layer) < org["staging_capacity_per_layer"]:
                    held.remove(i); staging.add(i); location[i] = "staging"; changed = True
            for i in sorted(shared):
                if can_local(i): shared.remove(i); local.add(i); location[i] = "local"; changed = True
    while tick <= last or local or shared or staging or held or active:
        if tick > last + drain_limit: break
        for i in arrivals.get(tick, []): put_arrival(i)
        finished = [item for item in active if item[0] <= tick]; active = [item for item in active if item[0] > tick]
        for _, member in finished: completed[member.transaction_index].add(member)
        # The sole A4.7.1 commit boundary releases locks and all dependent work.
        for i in sorted(set(location) - committed):
            tx = transactions[i]
            if any(parent not in committed for parent in tx.predecessors) or len(completed[i]) != len(members[i]): continue
            if len(tx.banks) > 1 and candidate["commit_slots"] and coordinator_until > tick:
                reasons["cross_bank_commit_coordination"] += 1; continue
            if len(tx.banks) > 1 and candidate["commit_slots"]: coordinator_until = tick + 1
            committed.add(i); local.discard(i); shared.discard(i); staging.discard(i); held.discard(i)
            for member in members[i]:
                if locks.get(member.object_key) != i: raise AssertionError("commit without all member locks")
                del locks[member.object_key]
        advance_buffers()
        counts = local_counts()
        for b in range(candidate["banks"]): local_samples[b].append(counts[b])
        for layer in {tx.layer for tx in transactions}:
            shared_samples[layer].append(layer_count(shared, layer)); staging_samples[layer].append(layer_count(staging, layer))
        stranded_samples.append(sum(LOCAL_CAPACITY-value for value in counts.values()) if (shared or staging or held) else 0)
        active_resource = Counter((m.bank, m.operation) for _, m in active)
        for i in sorted(local):
            tx = transactions[i]
            if any(parent not in committed for parent in tx.predecessors): reasons["intrinsic_dependency"] += 1; continue
            for member in members[i]:
                if member in started[i]: continue
                owner = locks.get(member.object_key)
                if owner is not None and owner != i: reasons["same_record_lock"] += 1; continue
                field = {"read":"read_ports", "write":"write_ports", "rmw":"rmw_lanes"}[member.operation]
                if active_resource[(member.bank, member.operation)] >= candidate[field]: reasons["bank_" + member.operation if member.operation != "rmw" else "rmw_lane"] += 1; continue
                locks[member.object_key] = i; started[i].add(member); active.append((tick + micro_op_duration(member.operation), member)); active_resource[(member.bank, member.operation)] += 1
                local.discard(i)  # Queue slot is released only on first internal start, matching A4.9.2 queue accounting.
        held_samples.append(len(held)); bp_flags.append(bool(held)); active_samples.append(len(active)); tick += 1
    if any(owner in committed for owner in locks.values()): raise AssertionError("committed transaction retained a lock")
    if any(i in committed and any(parent not in committed for parent in tx.predecessors) for i, tx in enumerate(transactions)): raise AssertionError("commit released an unmet predecessor")
    longest = run = 0
    for flag in bp_flags: run = run + 1 if flag else 0; longest = max(longest, run)
    peak_local = [max(values, default=0) for values in local_samples]
    shared_peaks = [max(values, default=0) for values in shared_samples.values()]
    staging_peaks = [max(values, default=0) for values in staging_samples.values()]
    peak_shared, peak_staging = sum(shared_peaks), sum(staging_peaks)
    return {"completed":len(committed), "total":len(transactions), "drained_within_declared_bound":len(committed)==len(transactions), "abstract_cycles_elapsed":tick,
        "per_bank_local_occupancy":{str(bank):summary(values) for bank, values in enumerate(local_samples)}, "per_bank_peak_occupancy":summary(peak_local), "cross_bank_peak_skew":max(peak_local,default=0)-min(peak_local,default=0),
        "stranded_local_capacity_observations":sum(stranded_samples),
        "shared_overflow_per_layer_peak":summary(shared_peaks), "shared_overflow_total_peak":peak_shared, "shared_overflow_active_opportunities":sum(any(values) for values in zip(*shared_samples.values())) if shared_samples else 0,
        "staging_per_layer_peak":summary(staging_peaks), "staging_total_peak":peak_staging, "backpressure_event_count":bp_events, "backpressure_active_opportunities":sum(bp_flags), "longest_backpressure_opportunity_run":longest, "held_transaction_high_water":max(held_samples,default=0), "trace_end_residual_backlog":len(local|shared|staging|held)+len(active),
        "active_micro_op_concurrency":summary(active_samples), "blocking_observation_counts":dict(reasons),
        "declared_queue_reference_word_bits":QUEUE_REFERENCE_WORD_BITS, "peak_modeled_queue_staging_bits":QUEUE_REFERENCE_WORD_BITS*(sum(peak_local)+peak_shared+peak_staging),
        "boundary":"Queue/staging references and abstract opportunities are declared model quantities, not FIFO/SRAM macro sizing, timing, traffic, throughput, energy, area, architecture, or RTL evidence."}


def main() -> None:
    args = parse_args(); checked = validate(args)
    if args.preflight_only:
        print("A4.10 preflight passed: A4.9.2 trace/report chain and fixed HA8 catalog validated; no output created."); return
    if args.output_dir.exists(): raise FileExistsError(args.output_dir)
    rows=[]; seen=set()
    for key, records, groups in iter_contexts(args.a468220_trace,args.a471_trace):
        predecessors,_=dependency_predecessors(records,groups)
        for name in CANDIDATE_NAMES:
            candidate=checked["catalog"][name]; profile={"layout":LAYOUT,"bank_count":candidate["banks"],"bank_mapping":candidate["mapping"]}
            txs,ops=make_scheduled_transactions(groups,predecessors,profile); members=build_micro_ops(groups,txs,candidate)
            marker=(*key,name); baseline=checked["rows"].get(marker)
            if baseline is None: raise AssertionError("A4.9.2 baseline context absent")
            org_rows=[]
            for org in ORGANIZATIONS:
                result=replay(txs,ops,members,candidate,org,args.post_trace_cycle_limit)
                org_rows.append({"organization":org,"result":result,"cmin_delta_vs_a492_record_granular":result["abstract_cycles_elapsed"]-baseline["record_granular_internal_execution"]["abstract_cycles_elapsed"]})
            rows.append({"anchor":key[0],"workload":key[1],"evaluation_horizon_append_opportunities":key[2],"organization_label":key[3],"candidate":candidate,"a492_record_granular_baseline":baseline["record_granular_internal_execution"],"queue_organization_rows":org_rows}); seen.add(marker)
    expected={key for key in checked["rows"] if key[-1] in CANDIDATE_NAMES}
    if seen != expected: raise AssertionError("A4.10 context coverage differs from A4.9.2 HA8 rows")
    config={"fixed_execution":"A4.9.2 record-granular only", "candidates":CANDIDATE_NAMES, "local_capacity_per_bank":LOCAL_CAPACITY, "shared_capacity_per_layer":SHARED_CAPACITY, "staging_capacity_per_layer":STAGING_CAPACITY, "queue_reference_word_bits":QUEUE_REFERENCE_WORD_BITS, "organizations":ORGANIZATIONS, "boundary":"No pruning/admission/transaction semantics, FIFO/ownership, or commit boundary changes. Full-KV is a protection classification only, not a default queue remedy."}
    report={"schema_version":SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"input_artifacts":{"a468220_trace_sha256":sha256_file(args.a468220_trace),"a471_trace_sha256":sha256_file(args.a471_trace),"a492_report_sha256":sha256_file(args.a492_report)},"config":config,"config_hash":stable_hash(config),"semantic_guards":{"a492_record_granular_execution_fixed_without_new_variant":True,"ha8_wide_primary_and_ha8_base_control_only":True,"transaction_fifo_ownership_and_single_commit_boundary_unchanged":True,"lossless_credit_only_delays_transactions_without_drop_or_reorder":True,"queue_overflow_reference_and_finite_credit_staging_both_reported":True,"no_model_default_pruning_path_or_hardware_measurement_loaded":True},"candidate_context_rows":rows}
    args.output_dir.mkdir(parents=True); path=args.output_dir/"a410_queue_staging_credit_contract_report.json"; path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"A4.10 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} rows={len(rows)}")
if __name__=="__main__": main()
