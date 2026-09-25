#!/usr/bin/env python3
"""A4.9.1 declared-candidate metadata-engine replay (no model/RTL)."""
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
from tools.analyze_kvzap_route_a4721_metadata_physical_dse import SCHEMA as A4721_SCHEMA
from tools.analyze_kvzap_route_a480_commit_aware_backlog import (
    dependency_predecessors, iter_contexts, make_scheduled_transactions,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

SCHEMA = "kvzap-route-a491-candidate-metadata-engine-1.0"
A490_SCHEMA = "kvzap-route-a490-eager-rmw-envelope-1.0"
LAYOUT = "both_colocated_direct_v1"
# Every tuple is a declared abstract candidate, not a selected implementation.
CANDIDATES = (
    {"name": "ha4_base", "banks": 4, "mapping": "head_affine_v1", "read_ports": 1, "write_ports": 1, "rmw_lanes": 1, "queue_groups_per_bank": 32, "commit_slots": 0},
    {"name": "ha8_base", "banks": 8, "mapping": "head_affine_v1", "read_ports": 1, "write_ports": 1, "rmw_lanes": 1, "queue_groups_per_bank": 32, "commit_slots": 0},
    {"name": "ha8_wide", "banks": 8, "mapping": "head_affine_v1", "read_ports": 2, "write_ports": 2, "rmw_lanes": 2, "queue_groups_per_bank": 32, "commit_slots": 0},
    {"name": "st8_base", "banks": 8, "mapping": "object_identity_striped_v1", "read_ports": 1, "write_ports": 1, "rmw_lanes": 1, "queue_groups_per_bank": 32, "commit_slots": 1},
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.9.1 trace-driven declared-candidate metadata-engine cycle model; not measured hardware timing.")
    p.add_argument("--a468220-trace", type=Path, required=True)
    p.add_argument("--a471-trace", type=Path, required=True)
    p.add_argument("--a4721-report", type=Path, required=True)
    p.add_argument("--a490-report", type=Path, required=True)
    p.add_argument("--post-trace-cycle-limit", type=int, default=4096, help="Declared model drain bound in abstract cycles, not latency.")
    p.add_argument("--preflight-only", action="store_true")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory.")
    return p.parse_args()


def summarize(values: list[int]) -> dict[str, int]:
    if not values: return {"count": 0, "min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "sum": 0}
    s = sorted(values); n = len(s)
    at = lambda q: s[min(n - 1, max(0, int((n - 1) * q)))]
    return {"count": n, "min": s[0], "p50": at(.50), "p95": at(.95), "p99": at(.99), "max": s[-1], "sum": sum(s)}


def validate(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    a490 = read_completed(args.a490_report, A490_SCHEMA, "A4.9.0 _03")
    a4721 = read_completed(args.a4721_report, A4721_SCHEMA, "A4.7.2.1 _03")
    if not all(a490["envelope_exit_observation"].values()): raise ValueError("A4.9.0 exit incomplete")
    if a490["input_artifacts"]["a468220_trace_sha256"] != sha256_file(args.a468220_trace): raise ValueError("A4.9.0 record trace hash mismatch")
    if a490["input_artifacts"]["a471_trace_sha256"] != sha256_file(args.a471_trace): raise ValueError("A4.9.0 transaction trace hash mismatch")
    if a490["input_artifacts"]["a4721_report_sha256"] != sha256_file(args.a4721_report): raise ValueError("A4.9.0 physical-DSE hash mismatch")
    if not any(x.get("layout") == LAYOUT for x in a4721["static_candidate_rows"]): raise ValueError("fixed layout missing")
    return a490, a4721


def duration(tx: Any, candidate: dict[str, Any]) -> int:
    """Declared atomic group reservation: ports/lane capacity set modeled cycles."""
    reads = sum(v for (_, op), v in tx.demands.items() if op == "read")
    writes = sum(v for (_, op), v in tx.demands.items() if op == "write")
    rmw = sum(v for (_, op), v in tx.demands.items() if op == "rmw")
    service = max((reads + candidate["read_ports"] - 1) // candidate["read_ports"], (writes + candidate["write_ports"] - 1) // candidate["write_ports"], 2 * ((rmw + candidate["rmw_lanes"] - 1) // candidate["rmw_lanes"]), 1)
    return service + (1 if len(tx.banks) > 1 else 0)


def replay(transactions: list[Any], opportunities: list[tuple[str, int]], candidate: dict[str, Any], drain_limit: int) -> dict[str, Any]:
    arrivals: dict[int, list[Any]] = defaultdict(list)
    for tx in transactions: arrivals[tx.arrival_ordinal].append(tx)
    pending: list[Any] = []; committed: set[int] = set(); active: list[tuple[int, Any]] = []
    bank_until = [0] * candidate["banks"]; coordinator_until = 0; starts = {}; causes = Counter(); peak = 0; overflow = 0; tick = 0
    last_arrival = len(opportunities) - 1
    while tick <= last_arrival or pending or active:
        if tick > last_arrival + drain_limit: break
        for tx in arrivals.get(tick, []): pending.append(tx)
        finished = [item for item in active if item[0] <= tick]
        active = [item for item in active if item[0] > tick]
        committed.update(tx.index for _, tx in finished)
        peak = max(peak, len(pending) + len(active))
        bank_queued = Counter(b for tx in pending for b in tx.banks)
        overflow = max(overflow, max(bank_queued.values(), default=0) - candidate["queue_groups_per_bank"])
        kept = []
        for tx in pending:
            if any(p not in committed for p in tx.predecessors): causes["intrinsic_dependency"] += 1; kept.append(tx); continue
            if any(bank_until[b] > tick for b in tx.banks): causes["bank_or_rmw_reservation"] += 1; kept.append(tx); continue
            if len(tx.banks) > 1 and candidate["commit_slots"] and coordinator_until > tick: causes["cross_bank_commit"] += 1; kept.append(tx); continue
            d = duration(tx, candidate); starts[tx.index] = tick
            for b in tx.banks: bank_until[b] = tick + d
            if len(tx.banks) > 1 and candidate["commit_slots"]: coordinator_until = tick + d
            active.append((tick + d, tx))
        pending = kept; tick += 1
    delays = [starts[t.index] - t.arrival_ordinal for t in transactions if t.index in starts]
    return {"completed": len(committed), "total": len(transactions), "drained_within_declared_bound": len(committed) == len(transactions), "abstract_cycles_elapsed": tick, "transaction_start_delay_abstract_cycles": summarize(delays), "peak_inflight_or_queued_transaction_groups": peak, "queue_overflow_groups_observed": overflow, "blocking_observation_counts": dict(causes), "model_boundary": "One logical opportunity introduces arrivals at one abstract cycle. An atomic group reserves all touched modeled banks until its declared read/write/RMW service completes; this is a conservative candidate service model, not an SRAM atomic, calibrated timing, or hardware latency."}


def main() -> None:
    args = parse_args(); a490, a4721 = validate(args)
    if args.preflight_only:
        print("A4.9.1 preflight passed: A4.9.0 exit and immutable input bindings validated; no output created."); return
    if args.output_dir.exists(): raise FileExistsError(args.output_dir)
    rows=[]
    for key, record_ops, groups in iter_contexts(args.a468220_trace, args.a471_trace):
        predecessors, _ = dependency_predecessors(record_ops, groups)
        for candidate in CANDIDATES:
            profile={"layout": LAYOUT, "bank_count": candidate["banks"], "bank_mapping": candidate["mapping"]}
            txs, ops = make_scheduled_transactions(groups, predecessors, profile)
            out=replay(txs, ops, candidate, args.post_trace_cycle_limit)
            rows.append({"anchor":key[0],"workload":key[1],"evaluation_horizon_append_opportunities":key[2],"organization_label":key[3],"candidate":candidate,"result":out})
    report={"schema_version":SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"input_artifacts":{"a468220_trace_sha256":sha256_file(args.a468220_trace),"a471_trace_sha256":sha256_file(args.a471_trace),"a4721_report_sha256":sha256_file(args.a4721_report),"a490_report_sha256":sha256_file(args.a490_report)},"config":{"candidates":CANDIDATES,"fixed_layout":LAYOUT,"entry_alignment_bits":64,"boundary":"Candidate parameters and abstract cycles are declared model assumptions. Results are not measured hardware timing, throughput, bandwidth, energy, area, an architecture selection, or RTL evidence."},"semantic_guards":{"a490_exit_and_hash_chain_validated":True,"fifo_ownership_and_commit_predecessors_reused_unchanged":True,"candidate_queue_overflow_is_observed_never_dropped":True,"no_model_or_pruning_path_loaded":True,"no_hardware_measurement_claim":True},"candidate_context_rows":rows}
    report["config_hash"]=stable_hash(report["config"])
    args.output_dir.mkdir(parents=True); path=args.output_dir/"a491_candidate_metadata_engine_report.json"; path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(f"A4.9.1 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} rows={len(rows)}")

if __name__ == "__main__": main()
