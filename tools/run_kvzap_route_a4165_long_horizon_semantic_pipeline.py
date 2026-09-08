"""A4.1.7.14 fresh-source long-horizon semantic pipeline; no timing claim."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

A4165_SCHEMA = "kvzap-route-a4165-long-horizon-semantic-pipeline-1.0"

def parse_args():
    p=argparse.ArgumentParser(description="A4.1.7.14 fresh-source long-horizon source/A4151/A4154 semantic pipeline; no timing benchmark.")
    p.add_argument("--preset", choices=("summarization",), default="summarization"); p.add_argument("--context-repetitions",type=int,default=12); p.add_argument("--max-new-tokens",type=int,required=True); p.add_argument("--admission-budget",type=int,required=True); p.add_argument("--target-layers",nargs="+",default=["all"]); p.add_argument("--target-kv-head",choices=("all",),default="all"); p.add_argument("--seed",type=int,default=42); p.add_argument("--device",default="cuda"); p.add_argument("--output-dir",type=Path,required=True)
    return p.parse_args()

def child(script: str, args: list[str]):
    print("Running:", script, flush=True)
    subprocess.run([sys.executable, script, *args], check=True)

def complete(path: Path, schema: str):
    d=json.loads(path.read_text(encoding="utf-8"))
    if d.get("schema_version")!=schema or d.get("status")!="complete": raise ValueError(f"incomplete child artifact: {path}")
    return d

def main():
    a=parse_args()
    if a.output_dir.exists(): raise FileExistsError(f"output directory already exists: {a.output_dir}")
    if a.target_layers != ["all"] or a.target_kv_head!="all" or a.admission_budget!=512 or a.max_new_tokens<32: raise ValueError("A4.1.7.14 requires all layers/heads, budget 512, and --max-new-tokens >=32")
    a.output_dir.mkdir(parents=True)
    source_common=["--preset",a.preset,"--context-repetitions",str(a.context_repetitions),"--max-new-tokens",str(a.max_new_tokens),"--admission-budget",str(a.admission_budget),"--target-layers","all","--seed",str(a.seed)]
    common=[*source_common,"--target-kv-head","all"]
    source=a.output_dir/"source"; execution=a.output_dir/"execution_semantic"; elision=a.output_dir/"elision_semantic"
    child("tools/collect_kvzap_route_a41_replay_source.py",[ *source_common,"--require-all-kv-heads","--output-dir",str(source)])
    child("tools/run_kvzap_route_a4151_guard_elided_execution_semantic_gate.py",[ *common,"--require-replay-event-coverage","--device",a.device,"--replay-source-dir",str(source),"--output-dir",str(execution)])
    child("tools/run_kvzap_route_a4154_empty_source_elision_semantic_gate.py",[ *common,"--require-cross-workload-source-coverage","--device",a.device,"--replay-source-dir",str(source),"--route-a-execution-certification",str(execution/"a4151_guard_elided_execution_manifest.json"),"--output-dir",str(elision)])
    s=complete(source/"a41_replay_mask_source_manifest.json","kvzap-route-a41-replay-mask-source-1.0"); e=complete(execution/"a4151_guard_elided_execution_manifest.json","kvzap-route-a4151-guard-elided-execution-semantic-gate-1.0"); x=complete(elision/"a4154_empty_source_elision_manifest.json","kvzap-route-a4154-empty-source-elision-semantic-gate-1.0")
    config={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items() if k!="output_dir"}
    summary={"replay_event_file_sha256":s["event_file_sha256"],"event_count":s["event_count"],"replay_event_coverage":s["replay_event_coverage"],"route_a_execution_token_ids_sha256":e["diagnostic"]["execution_only_independent"]["generated_token_ids_sha256"],"elision_token_ids_sha256":x["diagnostic"]["elided_independent"]["generated_token_ids_sha256"],"source_accounting":x["diagnostic"]["candidate_source_accounting"],"route_page_guard":x["diagnostic"]["elided_independent"]["guard"]["external_storage_guard"]}
    if summary["route_a_execution_token_ids_sha256"]!=summary["elision_token_ids_sha256"]: raise AssertionError("long-horizon execution and elision token digests differ")
    out={"schema_version":A4165_SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"config":config,"config_hash":stable_hash(config),"children":{"source":"source/a41_replay_mask_source_manifest.json","execution":"execution_semantic/a4151_guard_elided_execution_manifest.json","elision":"elision_semantic/a4154_empty_source_elision_manifest.json"},"summary":summary,"observational_guards":{"fresh_online_dense_source_collected":True,"all_layers_all_kv_heads_source_coverage":True,"execution_only_semantics_certified":True,"empty_source_elision_semantics_certified":True,"long_horizon_execution_elision_token_digests_equal":True,"source_partial_or_skip_accounting_matches_merge":True,"nonempty_hot_and_packed_attention_observed":True},"boundaries":["This is an untimed fixed-request semantic/state pipeline, not a runtime, allocator, HBM, throughput, hardware, or RTL experiment.","The source is newly collected online dense KVzap; Route-A replays it for paired semantics only."]}
    (a.output_dir/"a4165_long_horizon_semantic_pipeline_manifest.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(f"A4.1.7.14 long-horizon semantic pipeline completed: {a.output_dir/'a4165_long_horizon_semantic_pipeline_manifest.json'}")
if __name__=="__main__": main()
