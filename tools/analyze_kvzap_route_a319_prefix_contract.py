"""Derive observed-prefix continuation requirements from aligned A3.11 ledgers.

For a declared lower-bound continuation of N calls, a request may legally end
at any observed prefix >= N.  This tool finds the earliest N whose entire
remaining observed prefix suffix is non-negative in modeled cycles.  It is an
observed-trace sufficiency screen, not a proof about unobserved continuations.
"""
from __future__ import annotations
import argparse, csv, json, math
from collections import defaultdict
from pathlib import Path
from typing import Any
from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a314_request_cap_gate import HARDWARE, hardware_key
from tools.simulate_kvzap_route_a3_traffic import sha256

PER_COLUMNS=("workload","request_id","deferred_decode_steps","admission_flush_token_budget",*HARDWARE,"observed_decode_steps","minimum_observed_safe_continuation_calls","cycle_saving_at_contract_prefix","minimum_cycle_saving_from_contract_to_trace_end","final_cycle_saving_fraction","interpretation")
CROSS_COLUMNS=("deferred_decode_steps","admission_flush_token_budget",*HARDWARE,"workload_count","cross_minimum_observed_safe_continuation_calls","all_workloads_have_observed_safe_contract","minimum_cycle_saving_at_cross_contract","minimum_final_cycle_saving_fraction","interpretation")

def parse_args(argv=None):
 p=argparse.ArgumentParser(description="Offline Route-A3.19 observed-prefix continuation-contract sufficiency DSE; never loads a model.")
 p.add_argument('--deferred-memory-dir',type=Path,action='append',required=True)
 p.add_argument('--workload-label',action='append',required=True)
 p.add_argument('--deferred-decode-steps-points',nargs='+',type=int,required=True)
 p.add_argument('--admission-flush-token-budget-points',nargs='+',type=int,required=True)
 p.add_argument('--output-dir',type=Path,required=True,help='New output directory only.')
 return p.parse_args(argv)
def read(path):
 with path.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def write(path,rows,fields):
 with path.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def policy_key(r):return int(r['deferred_decode_steps']),int(r['admission_flush_token_budget'])
def step_key(r):return policy_key(r),hardware_key(r)
def suffix_requirement(prefix: list[float], eps=1e-9):
 """Earliest one-based prefix whose every later observed prefix is non-negative."""
 suffix_min=math.inf; required=None
 for index in range(len(prefix)-1,-1,-1):
  suffix_min=min(suffix_min,prefix[index])
  if suffix_min>=-eps:required=index+1
 return required
def common_observed_requirement(requirements, lengths):
 if not all(isinstance(x,int) for x in requirements):return None
 candidate=max(requirements)
 return candidate if all(candidate<=length for length in lengths) else None
def load(directory):
 manifest_path=directory/'deferred_memory_system_manifest.json'; step_path=directory/'deferred_memory_system_step_results.csv'; summary_path=directory/'deferred_memory_system_summary.csv'
 if not all(x.is_file() for x in (manifest_path,step_path,summary_path)):raise FileNotFoundError('A3.19 requires A3.11 manifest, step ledger, and summary')
 manifest=json.loads(manifest_path.read_text())
 if manifest.get('schema_version')!='kvzap-route-a311-deferred-memory-system-dse-1.0':raise ValueError('unsupported A3.11 schema')
 return manifest,read(step_path),read(summary_path)
def run(args):
 if len(args.deferred_memory_dir)!=len(args.workload_label) or len(args.workload_label)<2 or len(set(args.workload_label))!=len(args.workload_label):raise ValueError('supply at least two unique ordered memory-dir/workload pairs')
 policies={(d,b) for d in args.deferred_decode_steps_points for b in args.admission_flush_token_budget_points}
 if not policies or any(d<0 or b<=0 for d,b in policies):raise ValueError('invalid policy points')
 loaded=[]; provenance={}; expected_hw={}
 for label,directory in zip(args.workload_label,args.deferred_memory_dir,strict=True):
  manifest,steps,summaries=load(directory)
  chosen=[r for r in summaries if policy_key(r) in policies]
  maps={}
  for policy in policies:
   sm={hardware_key(r):r for r in chosen if policy_key(r)==policy}
   if not sm or len(sm)!=sum(policy_key(r)==policy for r in chosen):raise ValueError(f'missing or duplicate A3.11 policy {policy} for {label}')
   if policy in expected_hw and set(sm)!=expected_hw[policy]:raise ValueError(f'hardware grid differs for {label} policy {policy}')
   expected_hw[policy]=set(sm);maps[policy]=sm
  grouped=defaultdict(list)
  for r in steps:
   if policy_key(r) in policies:grouped[step_key(r)].append(r)
  prefixes={}
  for policy,sm in maps.items():
   for hw,summary in sm.items():
    rows=sorted(grouped[(policy,hw)],key=lambda r:int(r['decode_step']))
    count=int(summary['decode_steps'])
    if [int(r['decode_step']) for r in rows]!=list(range(1,count+1)):raise ValueError(f'{label}: non-contiguous A3.11 step ledger')
    full=candidate=0.0;values=[]
    for r in rows:
     full+=float(r['full_total_cycle_proxy']);candidate+=float(r['candidate_total_cycle_proxy']);values.append((full-candidate)/full)
    final=float(summary['net_cycle_proxy_saved_fraction'])
    if not math.isclose(values[-1],final,abs_tol=1e-9):raise ValueError(f'{label}: prefix sum disagrees with A3.11 summary')
    prefixes[(policy,hw)]=values
  provenance[label]={"deferred_memory_dir":str(directory),"request_id":summaries[0]['request_id'],"memory_manifest_sha256":sha256(manifest_path:=directory/'deferred_memory_system_manifest.json'),"memory_step_sha256":sha256(step_path:=directory/'deferred_memory_system_step_results.csv'),"memory_summary_sha256":sha256(summary_path:=directory/'deferred_memory_system_summary.csv')}
  loaded.append((label,summaries[0]['request_id'],prefixes))
 per=[]; per_map={}
 for label,request,prefixes in loaded:
  for (policy,hw),values in prefixes.items():
   needed=suffix_requirement(values)
   row={"workload":label,"request_id":request,"deferred_decode_steps":policy[0],"admission_flush_token_budget":policy[1],**dict(zip(HARDWARE,hw)),"observed_decode_steps":len(values),"minimum_observed_safe_continuation_calls":needed if needed is not None else 'not_found',"cycle_saving_at_contract_prefix":values[needed-1] if needed else 'not_found',"minimum_cycle_saving_from_contract_to_trace_end":min(values[needed-1:]) if needed else 'not_found',"final_cycle_saving_fraction":values[-1],"interpretation":"Earliest observed prefix N for which every observed endpoint from N through trace end is non-negative; not an unobserved-horizon guarantee or hardware measurement."}
   per.append(row);per_map[(label,policy,hw)]=row
 cross=[]
 for policy,hws in expected_hw.items():
  for hw in sorted(hws):
   rows=[per_map[(label,policy,hw)] for label,_,_ in loaded]
   needs=[r['minimum_observed_safe_continuation_calls'] for r in rows]
   common=common_observed_requirement(needs,[len(prefixes[(policy,hw)]) for _,_,prefixes in loaded])
   valid=common is not None;cross_n=common if valid else 'not_found'
   at=[]
   if valid:
    for label,_,prefixes in loaded:at.append(prefixes[(policy,hw)][cross_n-1])
   cross.append({"deferred_decode_steps":policy[0],"admission_flush_token_budget":policy[1],**dict(zip(HARDWARE,hw)),"workload_count":len(rows),"cross_minimum_observed_safe_continuation_calls":cross_n,"all_workloads_have_observed_safe_contract":valid,"minimum_cycle_saving_at_cross_contract":min(at) if at else 'not_found',"minimum_final_cycle_saving_fraction":min(float(r['final_cycle_saving_fraction']) for r in rows),"interpretation":"Cross maximum of per-workload observed-prefix requirements; all values remain trace-derived/modelled only."})
 return per,cross,provenance
def main():
 a=parse_args()
 if a.output_dir.exists():raise FileExistsError(f'Output directory already exists: {a.output_dir}')
 per,cross,provenance=run(a);a.output_dir.mkdir(parents=True,exist_ok=False)
 write(a.output_dir/'prefix_contract_per_workload.csv',per,PER_COLUMNS);write(a.output_dir/'prefix_contract_cross_summary.csv',cross,CROSS_COLUMNS)
 (a.output_dir/'prefix_contract_manifest.json').write_text(json.dumps({"schema_version":"kvzap-route-a319-prefix-contract-1.0","git_commit":get_git_commit(),"workloads":provenance,"assumptions":{"policies":[{"deferred_decode_steps":d,"admission_flush_token_budget":b} for d,b in sorted({(d,b) for d in a.deferred_decode_steps_points for b in a.admission_flush_token_budget_points})]},"boundaries":["A continuation contract is a lower bound; this derives the earliest observed prefix with non-negative modeled suffix endpoints.","Observed trace suffixes do not prove behavior after the trace ends or under another request.","No result is an online controller, sparse-attention execution, HBM/DRAM, allocator, latency, or throughput measurement."]},indent=2,sort_keys=True)+'\n')
 print(f'Route-A3.19 analyzed {len(provenance)} workloads and {len(cross)} policy/hardware points: {a.output_dir}')
if __name__=='__main__':main()
