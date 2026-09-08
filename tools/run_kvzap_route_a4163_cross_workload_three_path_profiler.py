"""A4.1.7.12 profiler-only attribution for the A4162 three-path measurement."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from torch.profiler import ProfilerActivity, profile
from transformers import pipeline

from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a412_profiler import operator_rows
from tools.run_kvzap_route_a412_whole_decode_gate import answer_hash, read_source, token_ids_hash
from tools.run_kvzap_route_a4147_qwen_external_storage_whole_decode_measurement import EXTERNAL_STORAGE_PATH
from tools.run_kvzap_route_a4148_qwen_external_storage_profiler import make_backend_and_cache, run_decode
from tools.run_kvzap_route_a4149_qwen_external_storage_phase_profiler import PHASE_PREFIX, PhaseRecorder, coalesced_phase_rows, phase_coverage
from tools.run_kvzap_route_a4152_certified_execution_mode_whole_decode_measurement import certify_dense_execution_only, validate_route_certificate, verify_backend
from tools.run_kvzap_route_a4155_empty_source_elision_paired_measurement import validate_a4154_certificate
from tools.run_kvzap_route_a4156_empty_source_elision_phase_profiler import source_phase_accounting
from tools.run_kvzap_route_a4162_cross_workload_three_path_measurement import PATHS, ROUTE_ELIDED_PATH
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request


A4163_SCHEMA = "kvzap-route-a4163-cross-workload-three-path-profiler-1.0"
REQUIRED_A4162_GUARDS = frozenset({"full_kv_bypass_zero_route_a_admission_each_reset_run", "route_a_execution_only_certification_verified", "a4154_empty_source_elision_semantics_certified", "same_mask_dense_guarded_vs_execution_only_certified", "execution_only_per_query_same_mask_numerical_guards_absent", "replay_mask_consumption_complete_each_reset_run", "all_layers_all_kv_heads_external_storage_substituted_each_route_a_reset_run", "persistent_selected_native_cold_absent_each_route_a_reset_run", "required_any_full_multi_tail_packed_coverage_each_route_a_reset_run", "execution_only_timed_token_digests_match_certificates", "fresh_reset_run_token_digests_stable"})


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.1.7.12 cross-workload three-path phase profiler; diagnostic only, not a timing benchmark.")
    request = p.add_mutually_exclusive_group(); request.add_argument("--preset", choices=PRESETS, default="summarization"); request.add_argument("--input-jsonl", type=Path)
    p.add_argument("--request-id"); p.add_argument("--context-repetitions", type=int, default=12)
    p.add_argument("--model-name", default=DEFAULT_MODEL); p.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    p.add_argument("--predictor-name", default=DEFAULT_PREDICTOR); p.add_argument("--predictor-revision", default=GATE_A_PREDICTOR_REVISION)
    p.add_argument("--threshold", type=float, default=-4.0); p.add_argument("--window-size", type=int, default=128); p.add_argument("--page-tokens", type=int, default=64); p.add_argument("--admission-budget", type=int, required=True)
    p.add_argument("--target-layers", nargs="+", default=["all"]); p.add_argument("--target-kv-head", choices=("all",), default="all"); p.add_argument("--max-new-tokens", type=int, default=16); p.add_argument("--seed", type=int, default=42)
    p.add_argument("--rtol", type=float, default=1e-4); p.add_argument("--atol", type=float, default=1e-5); p.add_argument("--max-executed-dtype-ulps", type=float, default=16.0); p.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    p.add_argument("--warmup-repetitions", type=int, default=1); p.add_argument("--top-operators", type=int, default=30); p.add_argument("--device", default="cuda")
    p.add_argument("--replay-source-dir", type=Path, required=True); p.add_argument("--route-a-execution-certification", type=Path, required=True); p.add_argument("--empty-source-elision-certification", type=Path, required=True); p.add_argument("--three-path-measurement-manifest", type=Path, required=True); p.add_argument("--require-cross-workload-source-coverage", action="store_true"); p.add_argument("--output-dir", type=Path, required=True)
    return p.parse_args()


def validate_a4162_manifest(*, path: Path, args: argparse.Namespace, event_sha256: str) -> dict[str, Any]:
    if not path.is_file(): raise FileNotFoundError(f"A4162 measurement manifest is missing: {path}")
    d = json.loads(path.read_text(encoding="utf-8"))
    if d.get("schema_version") != "kvzap-route-a4162-cross-workload-three-path-measurement-1.0" or d.get("status") != "complete": raise ValueError("three-path measurement is not a completed A4162 artifact")
    missing = sorted(x for x in REQUIRED_A4162_GUARDS if d.get("observational_guards", {}).get(x) is not True)
    if missing: raise ValueError(f"three-path measurement lacks guards: {missing}")
    if args.require_cross_workload_source_coverage and d["observational_guards"].get("required_cross_workload_source_coverage_verified") is not True: raise ValueError("three-path measurement did not require cross-workload coverage")
    if d.get("config", {}).get("replay_event_file_sha256") != event_sha256: raise ValueError("three-path measurement source SHA-256 differs from profiler source")
    if d.get("reported_token_digests", {}).get("same_mask_dense_replay") != d.get("reported_token_digests", {}).get(ROUTE_ELIDED_PATH): raise ValueError("A4162 did not establish matching same-mask dense/Route-A token digests")
    return {"manifest": str(path), "sha256": sha256_file(path), "token_ids_sha256": d["reported_token_digests"][ROUTE_ELIDED_PATH]}


def route_profile_guard(*, backend, cache, expected_heads, language_model, recorder, args):
    guard = verify_backend(path=EXTERNAL_STORAGE_PATH, backend=backend, cache=cache, expected_heads=expected_heads, args=args)
    decode = sum(int(x.policy_decode_calls) for x in backend.backends.values()); multi = sum(int(getattr(x, "policy_multi_token_tokens", 0)) for x in backend.backends.values())
    accounting = source_phase_accounting(calls=recorder.calls, expected_attention_evaluations=(decode + multi) * int(language_model.config.num_attention_heads), elide_empty_sources=True)
    return {**guard, "source_phase_accounting": accounting}


def make(path, *, pipe, layers, expected_heads, events, args, recorder):
    if path == "full_kv_bypass": return make_backend_and_cache(path=path, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, same_mask_numerical_guard_mode="execution_only")
    return make_backend_and_cache(path=EXTERNAL_STORAGE_PATH if path == ROUTE_ELIDED_PATH else path, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, component_measure=recorder.measure, same_mask_numerical_guard_mode="execution_only", elide_empty_sources=path == ROUTE_ELIDED_PATH)


def main() -> None:
    a = parse_args()
    if a.output_dir.exists(): raise FileExistsError(f"output directory already exists: {a.output_dir}")
    if a.request_id and not a.input_jsonl: raise ValueError("--request-id requires --input-jsonl")
    if a.target_layers != ["all"] or a.target_kv_head != "all" or a.admission_budget != 512: raise ValueError("A4.1.7.12 requires all layers/heads and budget 512")
    if min(a.context_repetitions, a.page_tokens, a.max_new_tokens, a.max_executed_dtype_ulps, a.ulp_breach_sample_limit, a.warmup_repetitions, a.top_operators) <= 0 or a.window_size < 0: raise ValueError("invalid A4.1.7.12 dimensions")
    require_cuda_device(a.device)
    if (a.model_name, a.predictor_name, a.model_revision, a.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION): raise ValueError("A4.1.7.12 is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(a.input_jsonl, a.request_id) if a.input_jsonl else build_builtin_request(a.preset, a.context_repetitions)
    print(f"Loading base model: {a.model_name}"); pipe = pipeline("kv-press-text-generation", model=a.model_name, revision=a.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != a.model_revision: raise ValueError("loaded model revision differs from frozen revision")
    lm = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model; layers = tuple(range(len(lm.layers))); heads = {x: tuple(range(int(lm.layers[x].self_attn.config.num_key_value_heads))) for x in layers}
    a.resolved_target_layers=list(layers); a.resolved_target_kv_heads_by_layer={str(x):list(y) for x,y in heads.items()}; a.require_any_pending=False; a.require_any_full_multi_tail_packed=True
    events, source, event_sha = read_source(a.replay_source_dir, args=a, layers=layers)
    if source["config"].get("admission_budget") != a.admission_budget: raise ValueError("replay source admission budget differs")
    route_cert = validate_route_certificate(path=a.route_a_execution_certification, args=a, event_sha256=event_sha); elision_cert = validate_a4154_certificate(path=a.empty_source_elision_certification, args=a, event_sha256=event_sha); measurement = validate_a4162_manifest(path=a.three_path_measurement_manifest, args=a, event_sha256=event_sha)
    tokenized=pipe.preprocess(str(request["context"]),[str(request["question"])],answer_prefix="",max_context_length=pipe.tokenizer.model_max_length,enable_thinking=False); context_ids,question_ids=tokenized["context_ids"].to(pipe.model.device),tokenized["questions_ids"][0].to(pipe.model.device)
    config={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items() if k!="output_dir"}; config.update({"replay_event_file_sha256":event_sha,"same_mask_numerical_guard_mode":"execution_only","phase_prefix":PHASE_PREFIX,"profiler_scope":"question_forward_plus_greedy_decode_after_untimed_context_prefill","profiler_paths":list(PATHS)})
    initialize_output_directory(a.output_dir,config=config,git_commit=get_git_commit(),record_name="a4163_cross_workload_three_path_profiler_started.json",schema_version=A4163_SCHEMA,boundaries=["A4.1.7.12 is one profiler diagnostic per path, separate from A4162 timing repetitions.","Full-KV bypass, same-mask dense replay, and empty-source-elided Route-A are distinct paths; profiler ranges are nested diagnostics, not latency.","Profiler time/memory is not HBM traffic, throughput, energy, hardware acceleration, or RTL evidence."])
    dense_cert=certify_dense_execution_only(pipe=pipe,context_ids=context_ids,question_ids=question_ids,layers=layers,expected_heads=heads,events=events,args=a); expected={"full_kv_bypass":None,"same_mask_dense_replay":dense_cert["execution_only_token_ids_sha256"],ROUTE_ELIDED_PATH:elision_cert["token_ids_sha256"]}
    results=[]
    for path in PATHS:
        for n in range(a.warmup_repetitions):
            print(f"Unprofiled warm-up {n+1}/{a.warmup_repetitions}: {path}"); rec=PhaseRecorder(); backend,cache=make(path,pipe=pipe,layers=layers,expected_heads=heads,events=events,args=a,recorder=rec); _ans,tokens,_b,_af=run_decode(pipe=pipe,context_ids=context_ids,question_ids=question_ids,backend=backend,cache=cache,args=a); assert_no_runtime_mask_state(pipe.model)
            if expected[path] and token_ids_hash(tokens)!=expected[path]: raise AssertionError(f"{path} warm-up digest differs from certificate")
            if backend is not None: backend.assert_replay_complete()
        print(f"Three-path phase-profiled diagnostic: {path}"); rec=PhaseRecorder(); backend,cache=make(path,pipe=pipe,layers=layers,expected_heads=heads,events=events,args=a,recorder=rec); prof=profile(activities=[ProfilerActivity.CPU,ProfilerActivity.CUDA],record_shapes=True,profile_memory=True,with_stack=False); answer,tokens,before,after=run_decode(pipe=pipe,context_ids=context_ids,question_ids=question_ids,backend=backend,cache=cache,args=a,profiler=prof); torch.cuda.synchronize(require_cuda_device(a.device)); assert_no_runtime_mask_state(pipe.model)
        if expected[path] and token_ids_hash(tokens)!=expected[path]: raise AssertionError(f"{path} profiler digest differs from certificate")
        result={"path":path,"answer_sha256":answer_hash(answer),"generated_token_count":len(tokens),"generated_token_ids_sha256":token_ids_hash(tokens),"memory_before":before,"memory_after":after,"phase_operators":coalesced_phase_rows(prof.key_averages()),"generic_top_operators":operator_rows(prof.key_averages(),top_operators=a.top_operators),"phase_operator_row_mode":"coalesced_cpu_cuda_views"}
        if backend is None: result["full_kv_bypass_zero_route_a_admission"]=True
        else:
            backend.assert_replay_complete(); result.update(route_profile_guard(backend=backend,cache=cache,expected_heads=heads,language_model=lm,recorder=rec,args=a) if path==ROUTE_ELIDED_PATH else {**verify_backend(path=path,backend=backend,cache=cache,expected_heads=heads,args=a),"phase_label_coverage":phase_coverage(backend=backend,language_model=lm,recorder=rec,path=path)})
        results.append(result)
    summary=a.output_dir/"a4163_cross_workload_three_path_profiler_summary.json"; summary.write_text(json.dumps({"schema_version":A4163_SCHEMA,"phase_prefix":PHASE_PREFIX,"results":results},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    manifest={"schema_version":A4163_SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"config":config,"config_hash":stable_hash(config),"request_id":request["request_id"],"request_content_hash":stable_hash({"context":request["context"],"question":request["question"]}),"replay_source":{"directory":str(a.replay_source_dir),"event_file_sha256":event_sha,"source_manifest_sha256":sha256_file(a.replay_source_dir/"a41_replay_mask_source_manifest.json"),"event_count":source["event_count"]},"route_a_execution_certificate":route_cert,"empty_source_elision_certificate":elision_cert,"three_path_measurement":measurement,"same_mask_dense_execution_certificate":dense_cert,"phase_summary":summary.name,"phase_summary_units":{"device_time_total_us":"nested/coalesced profiler diagnostic only","device_memory_usage_bytes":"profiler accounting, not allocator peak or HBM traffic"},"observational_guards":{"a4162_three_path_measurement_verified":True,"route_a_execution_only_certification_verified":True,"a4154_empty_source_elision_semantics_certified":True,"required_cross_workload_source_coverage_verified":bool(a.require_cross_workload_source_coverage),"same_mask_dense_guarded_vs_execution_only_certified":True,"execution_only_per_query_same_mask_numerical_guards_absent":True,"replay_mask_consumption_complete":True,"all_layers_all_kv_heads_external_storage_substituted":True,"persistent_selected_native_cold_absent":True,"required_any_full_multi_tail_packed_coverage":True,"profiler_token_digests_match_certificates":True,"route_a_source_partial_or_skip_accounting_matches_merge":True,"route_a_elided_pending_skip_observed":True,"phase_rows_coalesced":True,"profiler_is_separate_from_timing_repetitions":True,"context_prefill_profiled":False},"boundaries":["Nested profiler ranges must not be summed or read as latency/throughput.","This is a Python-reference diagnostic after untimed context prefill, not a packed-attention kernel profile.","Profiler time/memory is not HBM traffic, energy, area, frequency, hardware acceleration, or RTL evidence."],"torch_version":str(torch.__version__),"transformers_version":str(transformers.__version__)}
    out=a.output_dir/"a4163_cross_workload_three_path_profiler_manifest.json"; out.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(f"A4.1.7.12 cross-workload three-path profiler completed: {out}")


if __name__ == "__main__": main()
