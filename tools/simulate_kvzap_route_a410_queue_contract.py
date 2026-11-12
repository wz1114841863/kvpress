#!/usr/bin/env python3
"""A4.10 queue/staging/credit resource-contract DSE (no model/RTL)."""
from __future__ import annotations

from kvpress.research.metadata import LOCAL_CAPACITY, SHARED_CAPACITY, STAGING_CAPACITY, QUEUE_REFERENCE_WORD_BITS, queue_summary as summary, queue_replay as replay

import argparse
import hashlib
import json
from collections import Counter, defaultdict, deque
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
