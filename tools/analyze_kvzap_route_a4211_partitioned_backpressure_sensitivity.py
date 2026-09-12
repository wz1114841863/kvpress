"""A4.2.11 partition and arrival-contract sensitivity; virtual work only."""
from __future__ import annotations
import argparse,gzip,hashlib,json,heapq,math
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from tools.export_kvzap_predictor_trace import get_git_commit,stable_hash
SCHEMA="kvzap-route-a4211-partitioned-backpressure-sensitivity-2.0"; A428="kvzap-route-a428-matched-horizon-workload-stability-1.0"; A429="kvzap-route-a429-matched-interface-demand-1.0"; A4212="kvzap-route-a4212-dispatch-epoch-evidence-1.0"
def args():
 p=argparse.ArgumentParser(description="A4.2.11 modeled partitioned scheduler/backpressure sensitivity; no timing measurement.");p.add_argument("--a428-report",type=Path,required=True);p.add_argument("--a429-report",type=Path,required=True);p.add_argument("--a4212-report",type=Path,help="Optional A4.2.12 dependency-preserving dispatch-epoch evidence.");p.add_argument("--output-dir",type=Path,required=True,help="New output directory only.");return p.parse_args()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p,s):
 d=json.loads(p.read_text());
 if d.get("schema_version")!=s or d.get("status")!="complete":raise ValueError(f"invalid input {p}")
 return d
def stream(p):
 with gzip.open(p,"rt") as h:return [json.loads(x) for x in h]
def key(e,placement):return (0,) if placement=="global" else (e["layer"],) if placement=="per_layer" else (e["layer"],e["kv_head"])
def simulate(es,placement,arrival,hierarchy,parallel,cap,epoch_by_sequence=None):
 if cap<parallel:return None
 groups=defaultdict(list)
 for i,e in enumerate(es):
  active=[d["source"] for d in e["source_decisions"] if d["outcome"]=="partial"];fan=len(active)
  if arrival=="sequential":base=i
  elif arrival=="cache_position_burst":base=int(e["cache_position"])
  elif arrival=="trace_dispatch_epoch":
   if epoch_by_sequence is None:raise ValueError("trace_dispatch_epoch requires A4.2.12 evidence")
   base=epoch_by_sequence[int(e.get("logical_event_sequence", i))]
  else:raise ValueError(f"unknown arrival contract: {arrival}")
  ready=base+(2 if "pending" in active else 1); work=(fan if hierarchy=="flat" else max(1,math.ceil(math.log2(fan))))
  groups[key(e,placement)].append((ready,work))
 blocked=wait=finish=0;peak=0
 for tasks in groups.values():
  busy=[]
  for ready,work in sorted(tasks):
   nominal=ready
   while busy and busy[0]<=ready:heapq.heappop(busy)
   if len(busy)>=cap:
    blocked+=1;ready=busy[0];wait+=ready-nominal
    while busy and busy[0]<=ready:heapq.heappop(busy)
   if len(busy)>=parallel:
    ready=busy[0]
    while busy and busy[0]<=ready:heapq.heappop(busy)
   done=ready+work;heapq.heappush(busy,done);finish=max(finish,done);peak=max(peak,len(busy))
 return {"modeled_merge_tasks":len(es),"modeled_peak_inflight_tasks":peak,"modeled_backpressured_tasks":blocked,"modeled_backpressure_wait_work":wait,"modeled_finish_work":finish}
def load_epochs(report_path, report, workload, event_sha):
 row=report["per_workload"].get(workload)
 if row is None or row.get("ordered_event_sha256")!=event_sha:raise ValueError(f"A4.2.12 event binding mismatch: {workload}")
 artifact=row.get("dispatch_epoch_artifact",{});p=report_path.parent/artifact.get("path","")
 if not p.is_file() or sha(p)!=artifact.get("sha256"):raise ValueError(f"A4.2.12 epoch artifact hash mismatch: {workload}")
 rows=stream(p)
 if len(rows)!=artifact.get("row_count") or any(int(x["logical_event_sequence"])!=i for i,x in enumerate(rows)):raise ValueError(f"invalid A4.2.12 epoch sequence: {workload}")
 return {int(x["logical_event_sequence"]):int(x["source_ready_epoch"]) for x in rows}
def main():
 a=args()
 if a.output_dir.exists():raise FileExistsError(f"output directory already exists: {a.output_dir}")
 r428,r429=load(a.a428_report,A428),load(a.a429_report,A429);r4212=None if a.a4212_report is None else load(a.a4212_report,A4212)
 if not r428.get("observational_guards",{}).get("shared_actual_policy_decode_calls") or not r429.get("observational_guards",{}).get("split_exports_counted_as_modeled_interface_units"):raise ValueError("required guards absent")
 out={}
 for name,row in r428["per_workload"].items():
  p=a.a428_report.parent/name/"ordered_events/a424_ordered_logical_attention_events.jsonl.gz"
  if sha(p)!=row["logical_event_sha256"]:raise ValueError(f"hash mismatch {name}")
  es=stream(p); epoch_by_sequence=None if r4212 is None else load_epochs(a.a4212_report,r4212,name,sha(p)); rows=[]
  arrivals=("sequential","cache_position_burst") if epoch_by_sequence is None else ("sequential","cache_position_burst","trace_dispatch_epoch")
  for placement in ("global","per_layer","per_layer_kv_head"):
   for arrival in arrivals:
    for hierarchy in ("flat","tree_depth"):
     for parallel in (1,2):
      for cap in (1,2,4,8,16):
       x=simulate(es,placement,arrival,hierarchy,parallel,cap,epoch_by_sequence)
       rows.append({"placement":placement,"arrival_contract":arrival,"fan_in_merge_contract":hierarchy,"reducer_parallelism_axis":parallel,"merge_task_capacity_axis":cap,"status":"infeasible_capacity_below_parallelism" if x is None else "modeled",**({} if x is None else x)})
  out[name]={"event_sha256":sha(p),"event_count":len(es),"rows":rows}
 c={"a428_report":str(a.a428_report),"a428_sha256":sha(a.a428_report),"a429_report":str(a.a429_report),"a429_sha256":sha(a.a429_report),"a4212_report":None if a.a4212_report is None else str(a.a4212_report),"a4212_sha256":None if a.a4212_report is None else sha(a.a4212_report),"placements":["global","per_layer","per_layer_kv_head"],"arrival_contracts":["sequential","cache_position_burst"] if r4212 is None else ["sequential","cache_position_burst","trace_dispatch_epoch"],"hierarchies":{"flat":"work=fan-in","tree_depth":"work=max(1,ceil(log2(fan-in)))"},"parallelism_axes":[1,2],"capacity_axes":[1,2,4,8,16]}
 d={"schema_version":SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"config":c,"config_hash":stable_hash(c),"per_workload":out,"observational_guards":{"a428_hashes_verified":True,"a429_interface_guard_verified":True,"a4212_dispatch_epoch_binding_verified":r4212 is not None,"partition_and_burst_contracts_explicit":True,"no_hardware_parameter_selected":True},"boundaries":["Placement, arrival, hierarchy, parallelism, capacity, backpressure and finish work are declared virtual-work assumptions and outputs, not observed timing, queue/FIFO occupancy, cycles, latency, throughput, HBM, hardware, or RTL evidence.","The cache-position burst contract is a logical grouping, not a source completion timestamp.","trace_dispatch_epoch is an A4.2.12 dependency-preserving constructed arrival label, not a source completion, concurrent execution, or hardware dispatch timestamp."]}
 a.output_dir.mkdir(parents=True);p=a.output_dir/"a4211_partitioned_backpressure_sensitivity_report.json";p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n");print(f"A4.2.11 completed: {p}")
if __name__=="__main__":main()
