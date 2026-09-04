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

A4124_SCHEMA = "kvzap-route-a4124-multitoken-bridge-gate-1.3"


def parse_target_kv_head(value: str) -> int | None:
    if value == "all":
        return None
    try:
        head = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--target-kv-head must be a nonnegative integer or 'all'") from error
    if head < 0:
        raise argparse.ArgumentTypeError("--target-kv-head must be nonnegative or 'all'")
    return head


def assert_complete_selected_head_bridge_coverage(
    coverage: dict,
    *,
    expected_selected_kv_heads: tuple[int, ...],
    question_token_count: int,
    label: str,
) -> None:
    """Verify that every selected KV head was replaced for every question token."""
    heads = coverage.get("heads", [])
    observed = tuple(int(head["kv_head"]) for head in heads)
    if observed != expected_selected_kv_heads:
        raise AssertionError(f"{label} selected KV-head coverage mismatch: observed={observed}, expected={expected_selected_kv_heads}")
    incomplete = [
        {"kv_head": int(head["kv_head"]), "comparison_count": int(head.get("comparison_count", 0))}
        for head in heads
        if int(head.get("comparison_count", 0)) != question_token_count
    ]
    if incomplete:
        raise AssertionError(f"{label} did not replace every selected head for every question token: {incomplete}")


def assert_any_head_coverage(coverage: dict, *, field: str, label: str) -> None:
    heads = coverage.get("heads", [])
    if not any(bool(head.get(field, 0)) for head in heads):
        observed = [{"kv_head": head.get("kv_head"), field: head.get(field, 0)} for head in heads]
        raise AssertionError(f"required any-head {label} was not observed: {observed}")


def assert_required_packed_page_coverage(
    coverage: dict,
    *,
    require_multi_page_packed: bool,
    require_full_packed_page: bool,
    require_tail_packed_page: bool,
) -> None:
    """Require observed Route-A page states without inferring them from budget.

    A large admission budget is only a candidate configuration.  The manifest
    must prove that the replayed request actually exercised the requested page
    states during a selected-head multi-token bridge.
    """
    heads = coverage.get("heads", [])
    if not heads:
        raise AssertionError("Route-A bridge produced no selected-head coverage")
    checks = (
        (require_multi_page_packed, "ever_multi_page_packed", "multi-page packed coverage"),
        (require_full_packed_page, "ever_sealed_packed_page", "sealed full packed-page coverage"),
        (require_tail_packed_page, "max_packed_tail_tokens", "nonempty packed-tail coverage"),
    )
    for required, field, label in checks:
        if required and not all(bool(head.get(field, 0)) for head in heads):
            observed = [{"kv_head": head.get("kv_head"), field: head.get(field, 0)} for head in heads]
            raise AssertionError(f"required {label} was not observed: {observed}")

def parse_args():
    p=argparse.ArgumentParser(description="A4.1.2.4 untimed causal multi-token Route-A bridge gate; not a benchmark.")
    r=p.add_mutually_exclusive_group(); r.add_argument("--preset",choices=PRESETS,default="retrieval"); r.add_argument("--input-jsonl",type=Path)
    p.add_argument("--request-id"); p.add_argument("--context-repetitions",type=int,default=12)
    p.add_argument("--model-name",default=DEFAULT_MODEL); p.add_argument("--model-revision",default=GATE_B_MODEL_REVISION)
    p.add_argument("--predictor-name",default=DEFAULT_PREDICTOR); p.add_argument("--predictor-revision",default=GATE_A_PREDICTOR_REVISION)
    p.add_argument("--threshold",type=float,default=-4.0); p.add_argument("--window-size",type=int,default=128); p.add_argument("--page-tokens",type=int,default=64); p.add_argument("--admission-budget",type=int,required=True)
    p.add_argument("--target-layer",type=int,required=True); p.add_argument("--target-kv-head",type=parse_target_kv_head,required=True,help="One KV-head index, or 'all' for simultaneous layer-wide ownership."); p.add_argument("--max-new-tokens",type=int,default=8); p.add_argument("--top-k",type=int,default=8)
    p.add_argument("--seed",type=int,default=42); p.add_argument("--rtol",type=float,default=1e-4); p.add_argument("--atol",type=float,default=1e-5); p.add_argument("--max-executed-dtype-ulps",type=float,default=16.0); p.add_argument("--device",default="cuda")
    p.add_argument("--require-multi-page-packed",action="store_true",help="Require every selected KV head to observe at least two packed pages.")
    p.add_argument("--require-full-packed-page",action="store_true",help="Require every selected KV head to observe at least one sealed full packed page.")
    p.add_argument("--require-tail-packed-page",action="store_true",help="Require every selected KV head to observe a nonempty packed tail page.")
    p.add_argument("--require-any-pending",action="store_true",help="Require at least one selected KV head to observe pending staging.")
    p.add_argument("--require-any-multi-page-packed",action="store_true",help="Require at least one selected KV head to observe at least two packed pages.")
    p.add_argument("--require-any-full-packed-page",action="store_true",help="Require at least one selected KV head to observe a sealed full packed page.")
    p.add_argument("--require-any-tail-packed-page",action="store_true",help="Require at least one selected KV head to observe a nonempty packed tail page.")
    p.add_argument("--replay-source-dir",type=Path,required=True); p.add_argument("--output-dir",type=Path,required=True); return p.parse_args()

def main():
    a=parse_args()
    if a.output_dir.exists(): raise FileExistsError(f"output directory already exists: {a.output_dir}")
    if a.request_id and not a.input_jsonl: raise ValueError("--request-id requires --input-jsonl")
    if min(a.context_repetitions,a.page_tokens,a.admission_budget,a.max_new_tokens,a.max_executed_dtype_ulps,a.top_k)<=0 or a.target_layer<0 or a.window_size<0: raise ValueError("invalid bridge dimensions")
    require_cuda_device(a.device)
    if (a.model_name,a.predictor_name,a.model_revision,a.predictor_revision)!=(DEFAULT_MODEL,DEFAULT_PREDICTOR,GATE_B_MODEL_REVISION,GATE_A_PREDICTOR_REVISION): raise ValueError("gate is bounded to frozen Qwen3-8B and official MLP revisions")
    req=load_jsonl_request(a.input_jsonl,a.request_id) if a.input_jsonl else build_builtin_request(a.preset,a.context_repetitions)
    print(f"Loading base model: {a.model_name}"); pipe=pipeline("kv-press-text-generation",model=a.model_name,revision=a.model_revision,device_map="auto",dtype="auto")
    if getattr(pipe.model.config,"_commit_hash",None)!=a.model_revision: raise ValueError("loaded model revision differs from frozen revision")
    lm=pipe.model.model.language_model if hasattr(pipe.model.model,"language_model") else pipe.model.model
    if a.target_layer>=len(lm.layers): raise ValueError("target layer is outside the loaded model")
    kv_head_count=int(lm.layers[a.target_layer].self_attn.config.num_key_value_heads)
    if a.target_kv_head is not None and a.target_kv_head>=kv_head_count: raise ValueError("target KV head is outside the loaded model")
    expected_selected_kv_heads=tuple(range(kv_head_count)) if a.target_kv_head is None else (a.target_kv_head,)
    a.resolved_target_kv_heads=list(expected_selected_kv_heads)
    layers=(a.target_layer,); a.resolved_target_layers=list(layers); events,source,digest=read_source(a.replay_source_dir,args=a,layers=layers)
    tokenized=pipe.preprocess(str(req["context"]),[str(req["question"])],answer_prefix="",max_context_length=pipe.tokenizer.model_max_length,enable_thinking=False)
    context_ids,question_ids=tokenized["context_ids"].to(pipe.model.device),tokenized["questions_ids"][0].to(pipe.model.device)
    if context_ids.shape[1]<=a.window_size or question_ids.shape[1]<=1: raise ValueError("requires protected context and multi-token question")
    config={k:(str(v) if isinstance(v,Path) else v) for k,v in vars(a).items() if k!="output_dir"}; config["replay_event_file_sha256"]=digest
    initialize_output_directory(a.output_dir,config=config,git_commit=get_git_commit(),record_name="a4124_multitoken_bridge_started.json",schema_version=A4124_SCHEMA,boundaries=["Untimed context-prefill plus one causal multi-token question-forward gate; no greedy generation.","Selected heads use Route-A token-by-token causal state; native attention receives zero placeholders only for selected heads.","Prefix-only replay; no timing, allocator, HBM, physical-memory, or hardware claim."])
    print("Pass 1/3: Full-KV logits..."); full=first_question_forward(pipe=pipe,context_ids=context_ids,question_ids=question_ids,backend=None,args=a); assert_no_runtime_mask_state(pipe.model)
    print("Pass 2/3: causal same-mask dense bridge logits..."); dense_backend=DenseSameMaskAttentionBackend(pipe.model,None,layer=a.target_layer,kv_head=a.target_kv_head,threshold=a.threshold,window=a.window_size,page_tokens=a.page_tokens,admission_budget=a.admission_budget,rtol=a.rtol,atol=a.atol,max_executed_dtype_ulps=a.max_executed_dtype_ulps,replay_mask_events=events[a.target_layer]); dense=first_question_forward(pipe=pipe,context_ids=context_ids,question_ids=question_ids,backend=dense_backend,args=a); assert_no_runtime_mask_state(pipe.model)
    print("Pass 3/3: Route-A causal multi-token bridge logits..."); route_backend=RouteAColdOwnershipAttentionBackend(pipe.model,None,layer=a.target_layer,kv_head=a.target_kv_head,threshold=a.threshold,window=a.window_size,page_tokens=a.page_tokens,admission_budget=a.admission_budget,rtol=a.rtol,atol=a.atol,max_executed_dtype_ulps=a.max_executed_dtype_ulps,replay_mask_events=events[a.target_layer]); route=first_question_forward(pipe=pipe,context_ids=context_ids,question_ids=question_ids,backend=route_backend,args=a); assert_no_runtime_mask_state(pipe.model)
    relation=paired_logit_relation(dense,route); route_backend.assert_ownership_guard_complete(); dense_coverage=dense_backend.coverage(); route_coverage=route_backend.coverage()
    if dense_backend.policy_multi_token_calls!=1 or dense_backend.policy_multi_token_tokens!=question_ids.shape[1] or dense_backend.policy_decode_calls!=0: raise AssertionError("same-mask dense control did not bridge every question token causally")
    if route_backend.policy_multi_token_calls!=1 or route_backend.policy_multi_token_tokens!=question_ids.shape[1] or route_backend.policy_decode_calls!=0: raise AssertionError("Route-A did not bridge every question token causally")
    assert_complete_selected_head_bridge_coverage(dense_coverage,expected_selected_kv_heads=expected_selected_kv_heads,question_token_count=int(question_ids.shape[1]),label="same-mask dense")
    assert_complete_selected_head_bridge_coverage(route_coverage,expected_selected_kv_heads=expected_selected_kv_heads,question_token_count=int(question_ids.shape[1]),label="Route-A")
    assert_required_packed_page_coverage(route_coverage,require_multi_page_packed=a.require_multi_page_packed,require_full_packed_page=a.require_full_packed_page,require_tail_packed_page=a.require_tail_packed_page)
    if a.require_any_pending: assert_any_head_coverage(route_coverage,field="ever_pending",label="pending staging")
    if a.require_any_multi_page_packed: assert_any_head_coverage(route_coverage,field="ever_multi_page_packed",label="multi-page packed coverage")
    if a.require_any_full_packed_page: assert_any_head_coverage(route_coverage,field="ever_sealed_packed_page",label="sealed full packed-page coverage")
    if a.require_any_tail_packed_page: assert_any_head_coverage(route_coverage,field="max_packed_tail_tokens",label="nonempty packed-tail coverage")
    if not relation["both_all_finite"] or not relation["argmax_token_id_equal"]: raise AssertionError("multi-token bridge produced nonfinite logits or changed first argmax")
    diagnostic={"context_token_count":int(context_ids.shape[1]),"question_token_count":int(question_ids.shape[1]),"full_kv_bypass":logit_summary(full,top_k=a.top_k),"same_mask_dense_replay":{"control_path":"causal_multi_token_same_mask_dense_bridge","logits":logit_summary(dense,top_k=a.top_k),"policy_decode_calls":dense_backend.policy_decode_calls,"policy_multi_token_calls":dense_backend.policy_multi_token_calls,"policy_multi_token_tokens":dense_backend.policy_multi_token_tokens,"multi_token_attention_comparison":dense_backend.multi_token_comparison_summary(),"coverage":dense_coverage,"replay_consumption":dense_backend.replay_consumption_summary()},"same_mask_route_a_owned_cold_replay":{"logits":logit_summary(route,top_k=a.top_k),"policy_decode_calls":route_backend.policy_decode_calls,"policy_multi_token_calls":route_backend.policy_multi_token_calls,"policy_multi_token_tokens":route_backend.policy_multi_token_tokens,"multi_token_attention_comparison":route_backend.multi_token_comparison_summary(),"replay_consumption":route_backend.replay_consumption_summary(),"coverage":route_coverage,"native_cold_ownership":route_backend.ownership_summary()},"full_vs_dense":paired_logit_relation(full,dense),"dense_vs_route":relation}
    m={"schema_version":A4124_SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"config":config,"config_hash":stable_hash(config),"request_id":req["request_id"],"request_content_hash":stable_hash({"context":req["context"],"question":req["question"]}),"replay_source":{"directory":str(a.replay_source_dir),"event_file_sha256":digest,"source_manifest_sha256":sha256_file(a.replay_source_dir/"a41_replay_mask_source_manifest.json"),"event_count":source["event_count"]},"diagnostic":diagnostic,"observational_guards":{"prefix_replay_only":True,"causal_multitoken_same_mask_dense_bridge_complete":True,"causal_multitoken_route_a_bridge_complete":True,"all_selected_kv_heads_bridge_covered":True,"required_multi_page_packed_coverage":not a.require_multi_page_packed or all(bool(head["ever_multi_page_packed"]) for head in route_coverage["heads"]),"required_full_packed_page_coverage":not a.require_full_packed_page or all(bool(head["ever_sealed_packed_page"]) for head in route_coverage["heads"]),"required_tail_packed_page_coverage":not a.require_tail_packed_page or all(bool(head["max_packed_tail_tokens"]) for head in route_coverage["heads"]),"required_any_pending_coverage":not a.require_any_pending or any(bool(head["ever_pending"]) for head in route_coverage["heads"]),"required_any_multi_page_packed_coverage":not a.require_any_multi_page_packed or any(bool(head["ever_multi_page_packed"]) for head in route_coverage["heads"]),"required_any_full_packed_page_coverage":not a.require_any_full_packed_page or any(bool(head["ever_sealed_packed_page"]) for head in route_coverage["heads"]),"required_any_tail_packed_page_coverage":not a.require_any_tail_packed_page or any(bool(head["max_packed_tail_tokens"]) for head in route_coverage["heads"]),"finite_same_mask_dense_and_route_logits":True,"same_mask_dense_route_first_argmax_equal":True,"native_dense_cold_slots_physically_freed":False},"boundaries":["Semantic prefix gate only; not timing or physical storage evidence.","The dense control and Route-A both replace every selected GQA group causally from the same replayed original mask.","Safe native placeholders protect selected head values only while native attention computes unselected heads.","No greedy decode or complete replay claim."],"torch_version":str(torch.__version__),"transformers_version":str(transformers.__version__)}
    path=a.output_dir/"a4124_multitoken_bridge_manifest.json"; path.write_text(json.dumps(m,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(f"A4.1.2.4 multi-token bridge gate passed: {path}")
if __name__=="__main__": main()
