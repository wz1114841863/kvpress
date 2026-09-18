#!/usr/bin/env python3
"""A4.6.3.1 aggregate abstract attention/admission contention envelope."""
from __future__ import annotations
import argparse, json, math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import SCHEMA as A461_SCHEMA, read_completed
from tools.analyze_kvzap_route_a4630_physicalization_mapping import SCHEMA as A4630_SCHEMA
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

SCHEMA="kvzap-route-a4631-aggregate-attention-admission-contention-1.0"
COSTS={"payload_only":{"position":0,"pte":0,"seal":0,"merge":0},"metadata_merge_sensitive":{"position":1,"pte":4,"seal":4,"merge":2}}
SHARES=(0.10,0.25,0.50)

def args():
 p=argparse.ArgumentParser(description="A4.6.3.1 aggregate abstract attention/admission contention envelope; no measured traffic, timing, bandwidth, or hardware selection.")
 p.add_argument("--a461-report",type=Path,required=True);p.add_argument("--a4630-report",type=Path,required=True);p.add_argument("--preflight-only",action="store_true");p.add_argument("--output-dir",type=Path,required=True,help="Previously absent output directory only.");return p.parse_args()

def attention_units(a461:dict[str,Any], horizon:int, merge_records:int, merge_weight:int)->int:
 hot={(int(x['layer']),int(x['kv_head'])):int(x['hot_tokens_after_commit'])+int(x['packed_tokens_after_commit'])+int(x['pending_tokens_after_commit']) for x in a461['activation_commit_logical_inventory_by_layer_kv_head']}
 arrivals={(int(x['layer']),int(x['kv_head'])):[] for x in a461['activation_commit_logical_inventory_by_layer_kv_head']}
 for x in a461['post_commit_logical_append_events_by_layer_kv_head']: arrivals[(int(x['layer']),int(x['kv_head']))].append(int(x['matured_kept_tokens']))
 if any(len(v)<horizon for v in arrivals.values()): raise ValueError('insufficient A4.6.1 horizon')
 return sum(horizon*hot[k]+sum((horizon-i)*a for i,a in enumerate(arrivals[k][:horizon])) for k in hot)+merge_records*merge_weight

def main():
 a=args()
 if a.output_dir.exists(): raise FileExistsError(f"output directory already exists: {a.output_dir}")
 a461=read_completed(a.a461_report,A461_SCHEMA,'A4.6.1'); m=read_completed(a.a4630_report,A4630_SCHEMA,'A4.6.3.0')
 if m.get('input_artifacts',{}).get('a461_report_sha256')!=sha256_file(a.a461_report): raise ValueError('A4.6.3.0 does not bind A4.6.1')
 source={(x['anchor'],x['workload']):x for x in a461['anchor_rows']}
 if {(x['anchor'],x['workload']) for x in m['anchor_rows']}!=set(source): raise ValueError('anchor/workload rows differ')
 if a.preflight_only: print('A4.6.3.1 preflight passed: A4.6.1/A4.6.3.0 hash binding and aggregate source traversal inputs validated; no output created.');return
 rows=[]
 for row in m['anchor_rows']:
  source_row=source[(row['anchor'],row['workload'])]; points=[]
  for v in row['mapping_variants']:
   t=v['totals']; h=int(v['drain_horizon_append_opportunities'])
   for name,w in COSTS.items():
    admission=int(t['modeled_kv_payload_source_read_token_units'])+int(t['modeled_kv_payload_packed_write_token_units'])+w['position']*int(t['modeled_position_metadata_update_records'])+w['pte']*int(t['modeled_page_table_update_records'])+w['seal']*int(t['modeled_page_seal_records'])
    attention=attention_units(source_row,h,int(t['modeled_post_service_dual_source_merge_state_records']),w['merge'])
    total=attention+admission
    reserved=[{"reserved_admission_share":s,"minimum_shared_abstract_work_units":max(math.ceil(attention/(1-s)),math.ceil(admission/s)),"attention_requirement_units":attention,"admission_requirement_units":admission,"admission_deadline_inherited_from_a462":True} for s in SHARES]
    points.append({"policy":v['policy'],"drain_horizon_append_opportunities":h,"mapping_assumption":v['mapping_assumption'],"candidate_page_tokens":v['candidate_page_tokens'],"cost_profile":name,"attention_source_traversal_and_merge_abstract_work_units":attention,"admission_physicalization_abstract_work_units":admission,"admission_isolated":{"attention_requirement_units":attention,"admission_requirement_units":admission,"shared_fabric_not_assumed":True},"attention_first":{"minimum_shared_abstract_work_units":total,"attention_requirement_units":attention,"admission_requirement_units":admission,"admission_deadline_inherited_from_a462":True},"reserved_admission_share":reserved})
  rows.append({"anchor":row['anchor'],"workload":row['workload'],"contention_variants":points})
 config={"a461_report":str(a.a461_report),"a4630_report":str(a.a4630_report),"cost_profiles":COSTS,"reserved_admission_shares":list(SHARES),"scope":"aggregate bounded-horizon abstract work only; no temporal controller or hardware mapping"}
 report={"schema_version":SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"config":config,"config_hash":stable_hash(config),"execution_classification":"no-model aggregate abstract-work contention sensitivity over named physicalization mappings; not measured or temporally calibrated hardware evidence","input_artifacts":{"a461_report_sha256":sha256_file(a.a461_report),"a4630_report_sha256":sha256_file(a.a4630_report)},"anchor_rows":rows,"observational_guards":{"a461_a4630_hash_binding_validated":True,"all_mapping_variants_retained":True,"attention_admission_work_separated":True,"admission_isolated_attention_first_reserved_share_compared":True,"qwen_llama_rows_separate":True,"no_model_or_runtime_loaded":True,"no_hardware_parameter_selected":True},"boundaries":["Abstract work units use named cost profiles and are not bytes, transactions, HBM/DMA traffic, cycles, bandwidth, latency, throughput, energy, area, FIFO depth, or hardware resources.","Attention-first and reserved-share values are aggregate bounded-horizon capacity requirements, not a temporal arbitration/controller proof. A4.6.2 head backlog/fairness deadline is inherited, not recomputed under a temporal shared fabric.","No mapping/page/cost/share is selected. This result narrows inputs for a later temporal contention or physical-cost model and establishes no net benefit or RTL conclusion."]}
 a.output_dir.mkdir(parents=True);out=a.output_dir/'a4631_attention_admission_contention_report.json';out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(f'A4.6.3.1 contention envelope completed: {out}')
if __name__=='__main__':main()
