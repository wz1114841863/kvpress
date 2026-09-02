"""Compare an honest A3.17 contract gate with one breach counterfactual.

Both inputs must use the same source workloads, policies, thresholds, and
hardware grid.  They differ only in externally declared continuation contracts.
Observed lifecycle length is never a gate input; this tool verifies it only
through each A3.17 audit and reports the modeled penalty of a false contract.
"""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from typing import Any
from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a314_request_cap_gate import HARDWARE
from tools.simulate_kvzap_route_a3_traffic import sha256

PER = ("workload","request_id","required_minimum_continuation_calls","deferred_decode_steps","admission_flush_token_budget",*HARDWARE,"honest_gate_path","breach_gate_path","honest_contract_held","breach_contract_held","honest_net_cycle_proxy_saved_fraction","breach_net_cycle_proxy_saved_fraction","breach_minus_honest_cycle_fraction","honest_net_bytes_saved_fraction","breach_net_bytes_saved_fraction","breach_minus_honest_bytes_fraction")
CROSS = ("required_minimum_continuation_calls","deferred_decode_steps","admission_flush_token_budget",*HARDWARE,"honest_all_workloads_nonnegative_cycle","breach_all_workloads_nonnegative_cycle","honest_active_workload_count","breach_active_workload_count","breach_contract_violation_count","honest_min_net_cycle_proxy_saved_fraction","breach_min_net_cycle_proxy_saved_fraction","breach_minus_honest_min_cycle_fraction","honest_mean_net_cycle_proxy_saved_fraction","breach_mean_net_cycle_proxy_saved_fraction","breach_minus_honest_mean_cycle_fraction","interpretation")

def parse_args(argv=None):
 p=argparse.ArgumentParser(description="Offline Route-A3.18 honest-versus-breached continuation-contract comparison; never loads a model.")
 p.add_argument("--honest-gate-dir",type=Path,required=True)
 p.add_argument("--breach-gate-dir",type=Path,required=True)
 p.add_argument("--breach-workload",required=True,help="Workload intentionally given a false continuation declaration in the breach input.")
 p.add_argument("--output-dir",type=Path,required=True)
 return p.parse_args(argv)
def read(path):
 with path.open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def write(path,rows,cols):
 with path.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
def load(directory):
 files={"manifest":directory/'contract_policy_sweep_manifest.json',"per":directory/'contract_policy_sweep_per_workload.csv',"cross":directory/'contract_policy_sweep_cross_summary.csv',"audit":directory/'continuation_contract_audit.csv'}
 if not all(x.is_file() for x in files.values()):raise FileNotFoundError("A3.18 requires a complete A3.17 output directory")
 m=json.loads(files['manifest'].read_text())
 if m.get('schema_version')!='kvzap-route-a317-contract-policy-sweep-1.0':raise ValueError('unsupported gate schema')
 return m,read(files['per']),read(files['cross']),read(files['audit']),files
def key(r,workload=False):return (r['workload'],r['required_minimum_continuation_calls'],r['deferred_decode_steps'],r['admission_flush_token_budget'],*(r[x] for x in HARDWARE)) if workload else (r['required_minimum_continuation_calls'],r['deferred_decode_steps'],r['admission_flush_token_budget'],*(r[x] for x in HARDWARE))
def run(args):
 hm,hp,hc,ha,hf=load(args.honest_gate_dir); bm,bp,bc,ba,bf=load(args.breach_gate_dir)
 if set(hm['workloads'])!=set(bm['workloads']) or args.breach_workload not in hm['workloads']:raise ValueError('workload sets must match and include breach workload')
 for w in hm['workloads']:
  for field in ('request_id','lifecycle_dir','deferred_memory_dir','lifecycle_manifest_sha256','memory_manifest_sha256','memory_summary_sha256'):
   if hm['workloads'][w].get(field)!=bm['workloads'][w].get(field):raise ValueError(f'inputs differ in source provenance for {w}:{field}')
 hpa={key(r,True):r for r in hp}; bpa={key(r,True):r for r in bp}; hca={key(r):r for r in hc}; bca={key(r):r for r in bc}
 if set(hpa)!=set(bpa) or set(hca)!=set(bca):raise ValueError('A3.17 grids disagree')
 audit_h={r['workload']:r for r in ha};audit_b={r['workload']:r for r in ba}
 if set(audit_h)!=set(hm['workloads']) or set(audit_b)!=set(hm['workloads']):raise ValueError('A3.17 audit coverage disagrees')
 if audit_h[args.breach_workload]['contract_held_by_observed_trace']!='True' or audit_b[args.breach_workload]['contract_held_by_observed_trace']!='False':raise ValueError('named breach workload must be held in honest input and violated in breach input')
 per=[]
 for k,h in sorted(hpa.items()):
  b=bpa[k]; per.append({"workload":h['workload'],"request_id":h['request_id'],"required_minimum_continuation_calls":h['required_minimum_continuation_calls'],"deferred_decode_steps":h['deferred_decode_steps'],"admission_flush_token_budget":h['admission_flush_token_budget'],**{x:h[x] for x in HARDWARE},"honest_gate_path":h['gate_path'],"breach_gate_path":b['gate_path'],"honest_contract_held":audit_h[h['workload']]['contract_held_by_observed_trace'],"breach_contract_held":audit_b[h['workload']]['contract_held_by_observed_trace'],"honest_net_cycle_proxy_saved_fraction":float(h['net_cycle_proxy_saved_fraction']),"breach_net_cycle_proxy_saved_fraction":float(b['net_cycle_proxy_saved_fraction']),"breach_minus_honest_cycle_fraction":float(b['net_cycle_proxy_saved_fraction'])-float(h['net_cycle_proxy_saved_fraction']),"honest_net_bytes_saved_fraction":float(h['net_bytes_saved_fraction']),"breach_net_bytes_saved_fraction":float(b['net_bytes_saved_fraction']),"breach_minus_honest_bytes_fraction":float(b['net_bytes_saved_fraction'])-float(h['net_bytes_saved_fraction'])})
 violations=sum(r['contract_held_by_observed_trace']=='False' for r in ba)
 cross=[]
 for k,h in sorted(hca.items()):
  b=bca[k]; cross.append({"required_minimum_continuation_calls":h['required_minimum_continuation_calls'],"deferred_decode_steps":h['deferred_decode_steps'],"admission_flush_token_budget":h['admission_flush_token_budget'],**{x:h[x] for x in HARDWARE},"honest_all_workloads_nonnegative_cycle":h['all_workloads_nonnegative_cycle'],"breach_all_workloads_nonnegative_cycle":b['all_workloads_nonnegative_cycle'],"honest_active_workload_count":h['active_workload_count'],"breach_active_workload_count":b['active_workload_count'],"breach_contract_violation_count":violations,"honest_min_net_cycle_proxy_saved_fraction":float(h['min_net_cycle_proxy_saved_fraction']),"breach_min_net_cycle_proxy_saved_fraction":float(b['min_net_cycle_proxy_saved_fraction']),"breach_minus_honest_min_cycle_fraction":float(b['min_net_cycle_proxy_saved_fraction'])-float(h['min_net_cycle_proxy_saved_fraction']),"honest_mean_net_cycle_proxy_saved_fraction":float(h['mean_net_cycle_proxy_saved_fraction']),"breach_mean_net_cycle_proxy_saved_fraction":float(b['mean_net_cycle_proxy_saved_fraction']),"breach_minus_honest_mean_cycle_fraction":float(b['mean_net_cycle_proxy_saved_fraction'])-float(h['mean_net_cycle_proxy_saved_fraction']),"interpretation":"Counterfactual contract-breach composition of A3.17 modeled results; not an online-controller or hardware measurement."})
 provenance={"honest_manifest_sha256":sha256(hf['manifest']),"honest_per_sha256":sha256(hf['per']),"honest_cross_sha256":sha256(hf['cross']),"breach_manifest_sha256":sha256(bf['manifest']),"breach_per_sha256":sha256(bf['per']),"breach_cross_sha256":sha256(bf['cross'])}
 return per,cross,provenance
def main():
 a=parse_args()
 if a.output_dir.exists():raise FileExistsError(f'Output directory already exists: {a.output_dir}')
 per,cross,provenance=run(a);a.output_dir.mkdir(parents=True,exist_ok=False)
 write(a.output_dir/'contract_breach_per_workload.csv',per,PER);write(a.output_dir/'contract_breach_cross_summary.csv',cross,CROSS)
 (a.output_dir/'contract_breach_manifest.json').write_text(json.dumps({"schema_version":"kvzap-route-a318-contract-breach-1.0","git_commit":get_git_commit(),"honest_gate_dir":str(a.honest_gate_dir),"breach_gate_dir":str(a.breach_gate_dir),"breach_workload":a.breach_workload,"source_sha256":provenance,"boundaries":["This compares offline A3.17 modeled gate compositions.","A breach declaration is an explicit counterfactual; observed trace length never selects a gate.","No field is an HBM/DRAM, allocator, latency, throughput, or sparse-attention execution measurement."]},indent=2,sort_keys=True)+'\n')
 print(f'Route-A3.18 compared {len(cross)} aligned hardware/policy points: {a.output_dir}')
if __name__=='__main__':main()
