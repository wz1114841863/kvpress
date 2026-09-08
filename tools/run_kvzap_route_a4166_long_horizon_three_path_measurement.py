"""A4.1.7.15 provenance-bound wrapper around A4162 at a long horizon."""
from __future__ import annotations
import argparse, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

A4166_SCHEMA="kvzap-route-a4166-long-horizon-three-path-measurement-1.0"
def parse_args():
 p=argparse.ArgumentParser(description="A4.1.7.15 long-horizon three-path Python-reference measurement; not an HBM or hardware benchmark.")
 p.add_argument("--long-horizon-semantic-pipeline",type=Path,required=True);p.add_argument("--warmup-repetitions",type=int,default=2);p.add_argument("--measured-repetitions",type=int,default=10);p.add_argument("--device",default="cuda");p.add_argument("--output-dir",type=Path,required=True);return p.parse_args()
def load(path):
 d=json.loads(path.read_text(encoding="utf-8"))
 if d.get("schema_version")!="kvzap-route-a4165-long-horizon-semantic-pipeline-1.0" or d.get("status")!="complete":raise ValueError("not a completed A4165 long-horizon semantic pipeline")
 required=("fresh_online_dense_source_collected","execution_only_semantics_certified","empty_source_elision_semantics_certified","long_horizon_execution_elision_token_digests_equal","source_partial_or_skip_accounting_matches_merge")
 if any(d.get("observational_guards",{}).get(x) is not True for x in required):raise ValueError("A4165 prerequisite guards missing")
 return d
def main():
 a=parse_args()
 if a.output_dir.exists():raise FileExistsError(f"output directory already exists: {a.output_dir}")
 if min(a.warmup_repetitions,a.measured_repetitions)<=0:raise ValueError("repetitions must be positive")
 pipe=load(a.long_horizon_semantic_pipeline);c=pipe["config"]
 if c.get("max_new_tokens",0)<32 or c.get("admission_budget")!=512 or c.get("target_layers")!=["all"] or c.get("target_kv_head")!="all":raise ValueError("A4165 configuration is not the required all-layer budget-512 long horizon")
 a.output_dir.mkdir(parents=True);root=a.long_horizon_semantic_pipeline.parent; source=root/"source"; execution=root/"execution_semantic"/"a4151_guard_elided_execution_manifest.json"; elision=root/"elision_semantic"/"a4154_empty_source_elision_manifest.json"; child=a.output_dir/"three_path_measurement"
 command=[sys.executable,"tools/run_kvzap_route_a4162_cross_workload_three_path_measurement.py","--preset",str(c["preset"]),"--context-repetitions",str(c["context_repetitions"]),"--max-new-tokens",str(c["max_new_tokens"]),"--target-layers","all","--target-kv-head","all","--admission-budget","512","--require-cross-workload-source-coverage","--warmup-repetitions",str(a.warmup_repetitions),"--measured-repetitions",str(a.measured_repetitions),"--device",a.device,"--replay-source-dir",str(source),"--route-a-execution-certification",str(execution),"--empty-source-elision-certification",str(elision),"--output-dir",str(child)]
 print("Running A4162 child at long horizon...",flush=True);subprocess.run(command,check=True)
 mpath=child/"a4162_cross_workload_three_path_measurement_manifest.json";m=json.loads(mpath.read_text(encoding="utf-8"))
 if m.get("status")!="complete" or m.get("replay_source",{}).get("event_file_sha256")!=pipe["summary"]["replay_event_file_sha256"]:raise AssertionError("A4162 child did not bind A4165 source")
 config={"long_horizon_semantic_pipeline":str(a.long_horizon_semantic_pipeline),"warmup_repetitions":a.warmup_repetitions,"measured_repetitions":a.measured_repetitions,"device":a.device,"replay_event_file_sha256":pipe["summary"]["replay_event_file_sha256"]}
 out={"schema_version":A4166_SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"config":config,"config_hash":stable_hash(config),"a4165_pipeline_sha256":__import__("hashlib").sha256(a.long_horizon_semantic_pipeline.read_bytes()).hexdigest(),"a4162_child_manifest":"three_path_measurement/a4162_cross_workload_three_path_measurement_manifest.json","observational_guards":{"a4165_long_horizon_semantics_verified":True,"a4162_child_complete":True,"child_source_sha_matches_a4165":True,"three_path_timing_is_separate_from_semantic_pipeline":True},"boundaries":["This is a fixed-request repeated Python-reference software measurement after A4165 semantics, not a packed kernel benchmark.","Timing and allocator values are not HBM traffic, throughput, energy, hardware acceleration, or RTL evidence."]}
 (a.output_dir/"a4166_long_horizon_three_path_measurement_manifest.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(f"A4.1.7.15 long-horizon three-path measurement completed: {a.output_dir/'a4166_long_horizon_three_path_measurement_manifest.json'}")
if __name__=="__main__":main()
