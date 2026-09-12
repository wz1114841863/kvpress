"""A4.2.10 abstract, timestamp-free split-source backpressure sensitivity."""
from __future__ import annotations
import argparse, gzip, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

A428="kvzap-route-a428-matched-horizon-workload-stability-1.0"; A429="kvzap-route-a429-matched-interface-demand-1.0"; A425="kvzap-route-a425-ordered-logical-schedule-1.0"; A4210="kvzap-route-a4210-modeled-backpressure-envelope-2.0"
SOURCES=("hot","pending","packed")
PROFILES={"balanced":{"hot":1,"pending":1,"packed":1,"reducer":1},"reducer_slow":{"hot":1,"pending":1,"packed":1,"reducer":2},"pending_heavy":{"hot":1,"pending":2,"packed":1,"reducer":2}}

def parse_args():
 p=argparse.ArgumentParser(description="A4.2.10 abstract modeled split-source backpressure envelope; no timing measurement.")
 p.add_argument("--a428-report",type=Path,required=True);p.add_argument("--a429-report",type=Path,required=True);p.add_argument("--a425-report",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True,help="New output directory only.");return p.parse_args()
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p:Path,schema:str)->dict[str,Any]:
 d=json.loads(p.read_text());
 if d.get("schema_version")!=schema or d.get("status")!="complete":raise ValueError(f"incomplete or wrong schema: {p}")
 return d
def events(p:Path)->list[dict[str,Any]]:
 with gzip.open(p,"rt") as h:return [json.loads(x) for x in h]

def simulate(events:list[dict[str,Any]], profile:dict[str,int], cap:int)->dict[str,int|float]:
 """One virtual reducer consumes one fan-in merge task, not one partial state."""
 if cap<1:raise ValueError("merge-task capacity must be positive")
 arrivals=[]; exports=0
 for index,event in enumerate(events):
  active=[d["source"] for d in event["source_decisions"] if d["outcome"]=="partial"]
  if not active:raise ValueError("logical event has no active source")
  exports+=len(active); arrivals.append((max(index+profile[source] for source in active),len(active)))
 arrivals.sort(); completions=[]; reducer_free=0; peak=blocked=0; wait=0
 for nominal,_fan_in in arrivals:
  arrival=nominal
  while completions and completions[0]<=arrival: completions.pop(0)
  if len(completions)>=cap:
   blocked+=1; arrival=completions[0]; wait+=arrival-nominal
   while completions and completions[0]<=arrival: completions.pop(0)
  finish=max(arrival,reducer_free)+profile["reducer"]; reducer_free=finish; completions.append(finish); completions.sort(); peak=max(peak,len(completions))
 return {"modeled_split_state_exports":exports,"modeled_fan_in_merge_tasks":len(arrivals),"modeled_peak_inflight_merge_tasks":peak,"modeled_backpressured_merge_tasks":blocked,"modeled_total_backpressure_wait_work":wait,"modeled_reducer_finish_work":reducer_free,"co_located_cross_engine_exports":0}

def main():
 a=parse_args()
 if a.output_dir.exists():raise FileExistsError(f"output directory already exists: {a.output_dir}")
 r428,r429,r425=read(a.a428_report,A428),read(a.a429_report,A429),read(a.a425_report,A425)
 if not r428.get("observational_guards",{}).get("shared_actual_policy_decode_calls") or not r429.get("observational_guards",{}).get("split_exports_counted_as_modeled_interface_units") or not r425.get("observational_guards",{}).get("declared_work_axes_explicit"):raise ValueError("required input guards missing")
 outputs={}
 for name,row in r428["per_workload"].items():
  path=a.a428_report.parent/name/"ordered_events/a424_ordered_logical_attention_events.jsonl.gz"
  if sha(path)!=row["logical_event_sha256"]:raise ValueError(f"A428 event hash mismatch: {name}")
  stream=events(path); outputs[name]={"logical_event_sha256":sha(path),"event_count":len(stream),"rows":[{"profile":n,"merge_task_capacity_axis":cap,**simulate(stream,p,cap)} for n,p in PROFILES.items() for cap in (1,2,4,8,16,32)]}
 config={"a428_report":str(a.a428_report),"a428_report_sha256":sha(a.a428_report),"a429_report":str(a.a429_report),"a429_report_sha256":sha(a.a429_report),"a425_report":str(a.a425_report),"a425_report_sha256":sha(a.a425_report),"profiles":PROFILES,"merge_task_capacity_axes":[1,2,4,8,16,32],"revised_contract":"one fan-in merge task becomes ready after all active source partials finish declared source work; the reducer consumes merge tasks, not individual partial states"}
 result={"schema_version":A4210,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"config":config,"config_hash":stable_hash(config),"per_workload":outputs,"observational_guards":{"a428_matched_horizon_verified":True,"a429_split_interface_accounting_verified":True,"a425_declared_work_contract_verified":True,"a424_event_hashes_verified":True,"fan_in_partials_aggregate_to_one_merge_task":True,"co_located_has_zero_cross_engine_exports":True,"no_hardware_parameter_selected":True},"boundaries":["Arrival, reducer completion, merge-task capacity, waits, and backpressure are declared virtual-work model outputs, not observed source completion, timestamps, queue occupancy, FIFO depth, cycles, latency, throughput, HBM traffic, energy, area, hardware, or RTL evidence.","A4.2.4 event order supplies only submission order and source decisions; this sweep does not validate a physical scheduler or controller."]}
 a.output_dir.mkdir(parents=True);p=a.output_dir/"a4210_modeled_backpressure_envelope_report.json";p.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n");print(f"A4.2.10 completed: {p}")
if __name__=="__main__":main()
