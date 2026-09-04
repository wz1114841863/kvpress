"""A4.1.2.4 untimed causal multi-token question-forward bridge gate."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
import torch, transformers
from transformers import pipeline
from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackend, RouteAColdOwnershipAttentionBackend
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a4123_first_decode_logits_diagnostic import first_question_forward, logit_summary, paired_logit_relation
from tools.run_kvzap_route_a412_whole_decode_gate import read_source
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request

A4124_SCHEMA = "kvzap-route-a4124-multitoken-bridge-gate-1.1"

def parse_args():
    p=argparse.ArgumentParser(description="A4.1.2.4 untimed causal multi-token Route-A bridge gate; not a benchmark.")
    r=p.add_mutually_exclusive_group(); r.add_argument("--preset",choices=PRESETS,default="retrieval"); r.add_argument("--input-jsonl",type=Path)
    p.add_argument("--request-id"); p.add_argument("--context-repetitions",type=int,default=12)
    p.add_argument("--model-name",default=DEFAULT_MODEL); p.add_argument("--model-revision",default=GATE_B_MODEL_REVISION)
    p.add_argument("--predictor-name",default=DEFAULT_PREDICTOR); p.add_argument("--predictor-revision",default=GATE_A_PREDICTOR_REVISION)
    p.add_argument("--threshold",type=float,default=-4.0); p.add_argument("--window-size",type=int,default=128); p.add_argument("--page-tokens",type=int,default=64); p.add_argument("--admission-budget",type=int,required=True)
    p.add_argument("--target-layer",type=int,required=True); p.add_argument("--target-kv-head",type=int,required=True); p.add_argument("--max-new-tokens",type=int,default=8); p.add_argument("--top-k",type=int,default=8)
    p.add_argument("--seed",type=int,default=42); p.add_argument("--rtol",type=float,default=1e-4); p.add_argument("--atol",type=float,default=1e-5); p.add_argument("--max-executed-dtype-ulps",type=float,default=16.0); p.add_argument("--device",default="cuda")
    p.add_argument("--replay-source-dir",type=Path,required=True); p.add_argument("--output-dir",type=Path,required=True); return p.parse_args()

def main():
    a=parse_args()
    if a.output_dir.exists(): raise FileExistsError(f"output directory already exists: {a.output_dir}")
    if a.request_id and not a.input_jsonl: raise ValueError("--request-id requires --input-jsonl")
    if min(a.context_repetitions,a.page_tokens,a.admission_budget,a.max_new_tokens,a.max_executed_dtype_ulps,a.top_k)<=0 or min(a.target_layer,a.target_kv_head)<0 or a.window_size<0: raise ValueError("invalid bridge dimensions")
    require_cuda_device(a.device)
    if (a.model_name,a.predictor_name,a.model_revision,a.predictor_revision)!=(DEFAULT_MODEL,DEFAULT_PREDICTOR,GATE_B_MODEL_REVISION,GATE_A_PREDICTOR_REVISION): raise ValueError("gate is bounded to frozen Qwen3-8B and official MLP revisions")
    req=load_jsonl_request(a.input_jsonl,a.request_id) if a.input_jsonl else build_builtin_request(a.preset,a.context_repetitions)
    print(f"Loading base model: {a.model_name}"); pipe=pipeline("kv-press-text-generation",model=a.model_name,revision=a.model_revision,device_map="auto",dtype="auto")
    if getattr(pipe.model.config,"_commit_hash",None)!=a.model_revision: raise ValueError("loaded model revision differs from frozen revision")
    lm=pipe.model.model.language_model if hasattr(pipe.model.model,"language_model") else pipe.model.model
    if a.target_layer>=len(lm.layers) or a.target_kv_head>=int(lm.layers[a.target_layer].self_attn.config.num_key_value_heads): raise ValueError("target layer or KV head is outside the loaded model")
    layers=(a.target_layer,); a.resolved_target_layers=list(layers); events,source,digest=read_source(a.replay_source_dir,args=a,layers=layers)
    tokenized=pipe.preprocess(str(req["context"]),[str(req["question"])],answer_prefix="",max_context_length=pipe.tokenizer.model_max_length,enable_thinking=False)
    context_ids,question_ids=tokenized["context_ids"].to(pipe.model.device),tokenized["questions_ids"][0].to(pipe.model.device)
    if context_ids.shape[1]<=a.window_size or question_ids.shape[1]<=1: raise ValueError("requires protected context and multi-token question")
    config={k:(str(v) if isinstance(v,Path) else v) for k,v in vars(a).items() if k!="output_dir"}; config["replay_event_file_sha256"]=digest
    initialize_output_directory(a.output_dir,config=config,git_commit=get_git_commit(),record_name="a4124_multitoken_bridge_started.json",schema_version=A4124_SCHEMA,boundaries=["Untimed context-prefill plus one causal multi-token question-forward gate; no greedy generation.","Selected heads use Route-A token-by-token causal state; native attention receives zero placeholders only for selected heads.","Prefix-only replay; no timing, allocator, HBM, physical-memory, or hardware claim."])
    print("Pass 1/3: Full-KV logits..."); full=first_question_forward(pipe=pipe,context_ids=context_ids,question_ids=question_ids,backend=None,args=a); assert_no_runtime_mask_state(pipe.model)
    print("Pass 2/3: causal same-mask dense bridge logits..."); dense_backend=DenseSameMaskAttentionBackend(pipe.model,None,layer=a.target_layer,kv_head=a.target_kv_head,threshold=a.threshold,window=a.window_size,page_tokens=a.page_tokens,admission_budget=a.admission_budget,rtol=a.rtol,atol=a.atol,max_executed_dtype_ulps=a.max_executed_dtype_ulps,replay_mask_events=events[a.target_layer]); dense=first_question_forward(pipe=pipe,context_ids=context_ids,question_ids=question_ids,backend=dense_backend,args=a); assert_no_runtime_mask_state(pipe.model)
    print("Pass 3/3: Route-A causal multi-token bridge logits..."); route_backend=RouteAColdOwnershipAttentionBackend(pipe.model,None,layer=a.target_layer,kv_head=a.target_kv_head,threshold=a.threshold,window=a.window_size,page_tokens=a.page_tokens,admission_budget=a.admission_budget,rtol=a.rtol,atol=a.atol,max_executed_dtype_ulps=a.max_executed_dtype_ulps,replay_mask_events=events[a.target_layer]); route=first_question_forward(pipe=pipe,context_ids=context_ids,question_ids=question_ids,backend=route_backend,args=a); assert_no_runtime_mask_state(pipe.model)
    relation=paired_logit_relation(dense,route); route_backend.assert_ownership_guard_complete()
    if dense_backend.policy_multi_token_calls!=1 or dense_backend.policy_multi_token_tokens!=question_ids.shape[1] or dense_backend.policy_decode_calls!=0: raise AssertionError("same-mask dense control did not bridge every question token causally")
    if route_backend.policy_multi_token_calls!=1 or route_backend.policy_multi_token_tokens!=question_ids.shape[1] or route_backend.policy_decode_calls!=0: raise AssertionError("Route-A did not bridge every question token causally")
    if not relation["both_all_finite"] or not relation["argmax_token_id_equal"]: raise AssertionError("multi-token bridge produced nonfinite logits or changed first argmax")
    diagnostic={"context_token_count":int(context_ids.shape[1]),"question_token_count":int(question_ids.shape[1]),"full_kv_bypass":logit_summary(full,top_k=a.top_k),"same_mask_dense_replay":{"control_path":"causal_multi_token_same_mask_dense_bridge","logits":logit_summary(dense,top_k=a.top_k),"policy_decode_calls":dense_backend.policy_decode_calls,"policy_multi_token_calls":dense_backend.policy_multi_token_calls,"policy_multi_token_tokens":dense_backend.policy_multi_token_tokens,"multi_token_attention_comparison":dense_backend.multi_token_comparison_summary(),"replay_consumption":dense_backend.replay_consumption_summary()},"same_mask_route_a_owned_cold_replay":{"logits":logit_summary(route,top_k=a.top_k),"policy_decode_calls":route_backend.policy_decode_calls,"policy_multi_token_calls":route_backend.policy_multi_token_calls,"policy_multi_token_tokens":route_backend.policy_multi_token_tokens,"multi_token_attention_comparison":route_backend.multi_token_comparison_summary(),"replay_consumption":route_backend.replay_consumption_summary(),"coverage":route_backend.coverage(),"native_cold_ownership":route_backend.ownership_summary()},"full_vs_dense":paired_logit_relation(full,dense),"dense_vs_route":relation}
    m={"schema_version":A4124_SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"config":config,"config_hash":stable_hash(config),"request_id":req["request_id"],"request_content_hash":stable_hash({"context":req["context"],"question":req["question"]}),"replay_source":{"directory":str(a.replay_source_dir),"event_file_sha256":digest,"source_manifest_sha256":sha256_file(a.replay_source_dir/"a41_replay_mask_source_manifest.json"),"event_count":source["event_count"]},"diagnostic":diagnostic,"observational_guards":{"prefix_replay_only":True,"causal_multitoken_same_mask_dense_bridge_complete":True,"causal_multitoken_route_a_bridge_complete":True,"finite_same_mask_dense_and_route_logits":True,"same_mask_dense_route_first_argmax_equal":True,"native_dense_cold_slots_physically_freed":False},"boundaries":["Semantic prefix gate only; not timing or physical storage evidence.","The dense control and Route-A both replace selected heads causally from the same replayed original mask.","Safe native placeholders protect selected head values only while native attention computes unselected heads.","No greedy decode or complete replay claim."],"torch_version":str(torch.__version__),"transformers_version":str(transformers.__version__)}
    path=a.output_dir/"a4124_multitoken_bridge_manifest.json"; path.write_text(json.dumps(m,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(f"A4.1.2.4 multi-token bridge gate passed: {path}")
if __name__=="__main__": main()
