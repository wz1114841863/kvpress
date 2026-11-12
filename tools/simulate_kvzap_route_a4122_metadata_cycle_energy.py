#!/usr/bin/env python3
"""A4.12.2 declared metadata service/cycle and CACTI-access-energy replay."""
from __future__ import annotations

from kvpress.research.metadata import BANKS, service_summary as summary, macro_metrics, Active, service_duration as duration, resource_capacities, access_plan, can_use, commit_ready_groups, service_replay as replay

import argparse
import hashlib
import json
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a480_commit_aware_backlog import dependency_predecessors, iter_contexts, make_scheduled_transactions
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash
from tools.simulate_kvzap_route_a410_queue_contract import LOCAL_CAPACITY, SHARED_CAPACITY, STAGING_CAPACITY
from tools.simulate_kvzap_route_a491_candidate_metadata_engine import LAYOUT
from tools.simulate_kvzap_route_a492_record_granular_engine import MicroOp, build_micro_ops

SCHEMA = "kvzap-route-a4122-metadata-cycle-energy-1.0"
A4120_SCHEMA = "kvzap-route-a4120-metadata-interface-inventory-1.0"
A4121_SCHEMA = "kvzap-route-a4121-metadata-macro-envelope-1.0"
A410_SCHEMA = "kvzap-route-a410-queue-staging-credit-contract-1.0"
A492_SCHEMA = "kvzap-route-a492-record-granular-engine-1.0"
A4120_SHA256 = "e5a7ad30b45be7acbda7c2b0b788fdfa4ee74553d6fc93bc9317dce0c4be3534"
A4121_SHA256 = "d5f0f436251cb607b884e3102788caf2e775e398542686ad9ca88b58a96e3f7d"
A410_SHA256 = "97f9cec11c8ffff95ce8405d303f35ddf76ea2c4078512f0d98d38e6ec0ec9e4"
A492_SHA256 = "746a03453914294ecd7a48333bebe60d047689626f3ee8e3e4c76def5e00dae8"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.12.2 fixed metadata cycle/service and estimated SRAM-energy replay; declared model only, not hardware timing or RTL.")
    p.add_argument("--a4120-report", type=Path, required=True)
    p.add_argument("--a4121-report", type=Path, required=True)
    p.add_argument("--a410-report", type=Path, required=True)
    p.add_argument("--a492-report", type=Path, required=True)
    p.add_argument("--a468220-trace", type=Path, required=True)
    p.add_argument("--a471-trace", type=Path, required=True)
    p.add_argument("--post-trace-cycle-limit", type=int, default=4096, help="Fixed declared drain bound in service-model cycles, not latency.")
    p.add_argument("--preflight-only", action="store_true", help="Validate frozen bindings and service mappings without output or replay.")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()




def required_report(path: Path, schema: str, expected_sha: str, label: str) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != expected_sha:
        raise ValueError(f"{label} requires its accepted exact SHA-256 input")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != schema or report.get("status") != "complete":
        raise ValueError(f"{label} report is incomplete or schema-incompatible")
    return report




def validate(args: argparse.Namespace) -> dict[str, Any]:
    a4120 = required_report(args.a4120_report, A4120_SCHEMA, A4120_SHA256, "A4.12.0")
    a4121 = required_report(args.a4121_report, A4121_SCHEMA, A4121_SHA256, "A4.12.1")
    a410 = required_report(args.a410_report, A410_SCHEMA, A410_SHA256, "A4.10")
    a492 = required_report(args.a492_report, A492_SCHEMA, A492_SHA256, "A4.9.2")
    if a4121.get("input_artifacts", {}).get("a4120_report_sha256") != A4120_SHA256:
        raise ValueError("A4.12.1 is not bound to accepted A4.12.0")
    service = a4120["interface_inventory"]["frozen_service_requirement"]
    logical = a4120["interface_inventory"]["logical_resource_contract"]
    if service.get("bank_count") != BANKS or service.get("mapping") != "head_affine_v1":
        raise ValueError("A4.12.0 HA8-wide service requirement changed")
    if (logical.get("local_queue_capacity_per_bank_transaction_groups"), logical.get("shared_overflow_capacity_per_layer_transaction_groups"), logical.get("staging_capacity_per_layer_transaction_groups")) != (LOCAL_CAPACITY, SHARED_CAPACITY, STAGING_CAPACITY):
        raise ValueError("A4.10 logical queue contract changed")
    guards = a410.get("semantic_guards", {})
    for key in ("a492_record_granular_execution_fixed_without_new_variant", "ha8_wide_primary_and_ha8_base_control_only", "transaction_fifo_ownership_and_single_commit_boundary_unchanged", "lossless_credit_only_delays_transactions_without_drop_or_reorder"):
        if guards.get(key) is not True: raise ValueError("A4.10 semantic guard missing")
    if a410.get("input_artifacts", {}).get("a492_report_sha256") != A492_SHA256:
        raise ValueError("A4.10 is not bound to accepted A4.9.2")
    if a410.get("input_artifacts", {}).get("a468220_trace_sha256") != sha256_file(args.a468220_trace) or a410.get("input_artifacts", {}).get("a471_trace_sha256") != sha256_file(args.a471_trace):
        raise ValueError("A4.10 raw trace binding mismatch")
    a492_guards = a492.get("semantic_guards", {})
    for key in ("record_granular_interleaving_is_internal_and_all_external_publication_is_commit_gated", "same_record_lock_is_explicit_and_released_only_at_group_commit", "no_third_execution_granularity_or_semantic_variant_introduced"):
        if a492_guards.get(key) is not True: raise ValueError("A4.9.2 semantic guard missing")
    wide = next((x for x in a492.get("config", {}).get("candidates", []) if x.get("name") == "ha8_wide"), None)
    if wide != {"name":"ha8_wide", "banks":8, "mapping":"head_affine_v1", "read_ports":2, "write_ports":2, "rmw_lanes":2, "queue_groups_per_bank":32, "commit_slots":0}:
        raise ValueError("A4.9.2 HA8-wide declared candidate changed")
    if args.post_trace_cycle_limit < 0: raise ValueError("negative drain limit")
    return {"a4120": a4120, "a4121": a4121, "macros": macro_metrics(a4121)}
















def main() -> None:
    args = parse_args(); checked = validate(args)
    if args.preflight_only:
        print("A4.12.2 preflight passed: A4.12.0/A4.12.1/A4.10/A4.9.2 exact bindings and fixed M1/M2/M3 service mappings validated; no output created."); return
    if args.output_dir.exists(): raise FileExistsError(f"output directory already exists: {args.output_dir}")
    profile = {"layout":LAYOUT,"bank_count":BANKS,"bank_mapping":"head_affine_v1"}
    rows=[]
    for key, records, groups in iter_contexts(args.a468220_trace,args.a471_trace):
        predecessors,_ = dependency_predecessors(records,groups)
        txs,ops = make_scheduled_transactions(groups,predecessors,profile)
        ha8={"name":"ha8_wide","banks":8,"mapping":"head_affine_v1","read_ports":2,"write_ports":2,"rmw_lanes":2,"queue_groups_per_bank":32,"commit_slots":0}
        members=build_micro_ops(groups,txs,ha8)
        for candidate in ("M1_banked_sram_pipelined_rmw","M2_replicated_or_duplicated_control_storage","M3_register_hot_state_with_sram_backing"):
            rows.append({"anchor":key[0],"workload":key[1],"evaluation_horizon_append_opportunities":key[2],"organization_label":key[3],"physical_candidate":candidate,"result":replay(txs,ops,members,candidate,checked["macros"],args.post_trace_cycle_limit)})
    config={"stage":"A4.12.2","fixed_execution":"A4.9.2 record-granular HA8-wide only","queue_contract":"local32/shared256/staging512 only","physical_candidates":["M1_banked_sram_pipelined_rmw","M2_replicated_or_duplicated_control_storage","M3_register_hot_state_with_sram_backing"],"service_cycle":"declared arbitration/access coordinate; not CACTI ns or a clock period","commit_publish":"unchanged A4.9.2 single external boundary with no synthesized global commit slot; all same-coordinate ready groups publish together"}
    report={"schema_version":SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"execution_classification":"fixed trace-driven declared metadata service/cycle model plus CACTI-access-count estimated SRAM dynamic energy; not hardware timing, throughput measurement, PDK, physical implementation, architecture, or RTL evidence","input_artifacts":{"a4120_report_sha256":A4120_SHA256,"a4121_report_sha256":A4121_SHA256,"a410_report_sha256":A410_SHA256,"a492_report_sha256":A492_SHA256,"a468220_trace_sha256":sha256_file(args.a468220_trace),"a471_trace_sha256":sha256_file(args.a471_trace)},"config":config,"config_hash":stable_hash(config),"candidate_context_rows":rows,"semantic_guards":{"only_m1_m2_m3_from_a4121_compared":True,"ha8_wide_record_granular_and_a410_queue_contract_fixed":True,"single_commit_boundary_fifo_ownership_and_dependency_release_remain_commit_gated":True,"no_global_commit_slot_synthesized_when_a492_ha8_wide_declares_none":True,"no_pruning_admission_queue_or_execution_variant_introduced":True,"cacti_pj_per_access_multiplied_only_by_explicit_macro_access_counts":True,"m3_register_energy_not_invented":True,"no_hardware_measurement_or_rtl_claim":True},"boundaries":["A4.12.2 service cycles are declared model coordinates rather than CACTI ns, a clock period, timing closure, or measured throughput.","The frozen single semantic commit boundary is preserved, but no physical global commit controller or commit-port throughput is inferred when A4.9.2 HA8-wide declares no commit slot.","Estimated SRAM dynamic energy excludes M3 register energy, arbitration, scoreboard, commit, leakage, wiring, clocking, layout, and all KV payload-path energy."]}
    args.output_dir.mkdir(parents=True); output=args.output_dir/"a4122_metadata_cycle_energy_report.json"; output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"A4.12.2 complete: {output} sha256={hashlib.sha256(output.read_bytes()).hexdigest()} rows={len(rows)}")


if __name__ == "__main__": main()
