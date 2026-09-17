#!/usr/bin/env python3
"""A4.6.0 long-horizon Route-A-active steady-state functional gate."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
import transformers
from transformers import pipeline

from kvpress.route_a_attention import RouteALifecycleTransitionRecorder
from kvpress.route_a_policy_backend import DeferredActivationRouteAPolicyAttentionBackendSet
from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_llama31_m1_semantic_gate import EXPECTED_STRUCTURE, validate_runtime_structure
from tools.run_kvzap_route_a40_policy_gate import cuda_environment, write_lifecycle_transitions
from tools.run_kvzap_route_a451_capacity_protection_semantic_gate import qwen_kv_head_counts, token_ids_digest
from tools.run_kvzap_route_a453_global_next_epoch_protection_gate import build_predictor, continuation_for
from tools.run_kvzap_trace import DEFAULT_MODEL as QWEN_MODEL, build_builtin_request
from tools.validate_kvzap_llama31_m0_provenance import DEFAULT_MODEL_REPO as LLAMA_MODEL, DEFAULT_MODEL_REVISION as LLAMA_REVISION, OFFICIAL_PREDICTOR_REPO

SCHEMA = "kvzap-route-a460-route-a-active-steady-state-gate-1.0"
A442_SCHEMA = "kvzap-route-a442-cross-anchor-activation-contract-1.0"
WORKLOADS = ("retrieval", "summarization", "reasoning")
HORIZON = 64
TAIL_EVENTS = 32


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.6.0 long-horizon Route-A-active steady-state functional gate; no timing, FIFO, or hardware measurement.")
    p.add_argument("--anchor", choices=("qwen3_8b", "llama31_8b_instruct"), required=True)
    p.add_argument("--a442-report", type=Path, required=True)
    p.add_argument("--predictor-repo-id-override", default=None, help="Required only for the reviewed Llama predictor repository.")
    p.add_argument("--context-repetitions", type=int, default=12)
    p.add_argument("--fixed-new-tokens", type=int, default=HORIZON)
    p.add_argument("--deferred-decode-steps", type=int, default=1)
    p.add_argument("--page-tokens", type=int, default=64, help="Functional reference input only; not a hardware choice.")
    p.add_argument("--admission-budget", type=int, default=512, help="One reference append action only; not a service-rate claim.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--rtol", type=float, default=1e-4); p.add_argument("--atol", type=float, default=1e-5)
    p.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    p.add_argument("--execution-dtype-ulp-mode", choices=("record_only",), default="record_only")
    p.add_argument("--preflight-only", action="store_true", help="Validate A4.4.2 provenance and fixed inputs without CUDA/model load or output creation.")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def read_a442(path: Path, anchor: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not path.is_file(): raise FileNotFoundError(f"A4.4.2 report absent: {path}")
    r = json.loads(path.read_text(encoding="utf-8"))
    if r.get("schema_version") != A442_SCHEMA or r.get("status") != "complete": raise ValueError("A4.6.0 requires completed A4.4.2")
    source = r.get("input_artifacts", {}).get(anchor, {})
    source_path = Path(str(source.get("report_path", "")))
    if not source_path.is_file() or sha256_file(source_path) != source.get("report_sha256"): raise ValueError("A4.4.2 anchor source missing or hash-mismatched")
    rows = {x.get("workload"): x for x in r.get("anchor_rows", []) if x.get("anchor") == anchor}
    if set(rows) != set(WORKLOADS): raise ValueError("A4.4.2 lacks three anchor workload rows")
    matrix = [x for x in r.get("cross_anchor_semantic_invariant_matrix", []) if x.get("anchor") == anchor]
    if len(matrix) != 3 or any(not all(x.get(k) is True for k in ("activation_commit_once", "post_commit_route_a_active", "post_commit_trace_timestamp_free")) for x in matrix):
        raise ValueError("A4.4.2 source does not retain required activation semantics")
    return r, rows


def analyze_tail(events: list[dict[str, Any]], *, layers: tuple[int, ...], tail_events: int = TAIL_EVENTS) -> dict[str, Any]:
    """Untimed logical tail analysis; detects only a sustained finite-horizon witness."""
    per = defaultdict(list)
    for e in events:
        if e.get("phase") != "decode": continue
        for h in e["heads"]: per[(int(e["layer"]), int(h["kv_head"]))].append(h)
    expected = {(layer, head) for layer in layers for head in range(len(events[0]["heads"]))}
    if set(per) != expected or any(len(rows) < tail_events for rows in per.values()): raise AssertionError("insufficient post-commit decode tail coverage")
    witnesses, finals = [], []
    for key, rows in sorted(per.items()):
        tail = rows[-tail_events:]; pending = [int(x["pending_tokens_after_service"]) for x in tail]
        sustained = pending[-1] > pending[0] and all(b >= a for a, b in zip(pending, pending[1:]))
        if sustained: witnesses.append({"layer": key[0], "kv_head": key[1], "tail_start_pending": pending[0], "tail_end_pending": pending[-1]})
        finals.append(pending[-1])
    return {"tail_decode_events_per_layer": tail_events, "layer_kv_head_stream_count": len(per), "sustained_non_decreasing_pending_growth_witnesses": witnesses, "sustained_non_decreasing_pending_growth_witness_count": len(witnesses), "tail_pending_after_service_max": max(finals), "interpretation": "finite logical append-opportunity tail only; no arrival/service time, FIFO occupancy, or hardware stability claim"}


def validate_active(summary: dict[str, Any], layers: tuple[int, ...]) -> None:
    rows = summary.get("layers", [])
    if {r.get("layer") for r in rows} != set(layers): raise AssertionError("incomplete active layer coverage")
    for r in rows:
        e = r.get("activation_event")
        if not r.get("activation_committed") or r.get("mode_at_trace_end") != "route_a_active" or not isinstance(e, dict): raise AssertionError("Route-A did not remain active")
        if (e.get("mode_before_commit"), e.get("mode_after_commit")) != ("full_kv_bypass", "route_a_active") or r.get("native_cache_mutated_or_freed"):
            raise AssertionError("activation contract changed or native cache was mutated")


def run_workload(*, workload: str, pipe, args, layers: tuple[int, ...], heads: dict[int, int], predictor_revision: str, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    req = build_builtin_request(workload, args.context_repetitions)
    tokens = pipe.preprocess(str(req["context"]), [str(req["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids, question_ids = tokens["context_ids"].to(pipe.model.device), tokens["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= 128: raise ValueError("context does not cross hot window")
    continuation = continuation_for(args.anchor)
    print(f"A4.6.0 {args.anchor}/{workload}: Full-KV fixed-input reference...", flush=True)
    full = continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args)
    assert_no_runtime_mask_state(pipe.model)
    recorder = RouteALifecycleTransitionRecorder()
    backend = DeferredActivationRouteAPolicyAttentionBackendSet(pipe.model, build_predictor(args, predictor_revision=predictor_revision), layers=layers, kv_head=None, threshold=-4.0 if args.anchor == "qwen3_8b" else -7.0, window=128, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, execution_dtype_ulp_mode=args.execution_dtype_ulp_mode, execution_dtype_close_mode="quantization_aware_enforce" if args.anchor == "qwen3_8b" else "off", deferred_decode_steps=args.deferred_decode_steps, lifecycle_transition_recorder=recorder)
    print(f"A4.6.0 {args.anchor}/{workload}: activation then Route-A-active 64-step horizon...", flush=True)
    active = continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, backend=backend, forced_token_ids=full["generated_token_ids"])
    assert_no_runtime_mask_state(pipe.model)
    if active["generated_token_ids"] != full["generated_token_ids"]: raise AssertionError("Route-A did not consume fixed Full-KV token inputs")
    validate_active(backend.deferred_activation_summary(), layers)
    if set(backend.policy_decode_calls.values()) != {args.fixed_new_tokens - 2}: raise AssertionError("unexpected post-commit Route-A decode-call count")
    if any(r["work_count"] <= 0 for r in backend.same_mask_numerical_guard_work_summary()["layers"]): raise AssertionError("missing post-commit same-mask guard work")
    if not recorder.events or recorder.summary()["observed_layers"] != list(layers): raise AssertionError("missing lifecycle trace")
    tail = analyze_tail(recorder.events, layers=layers)
    trace = output_dir / "a460_post_commit_logical_lifecycle_events.jsonl.gz"; trace_hash = write_lifecycle_transitions(trace, recorder)
    return {"request": {"request_id": req["request_id"], "content_sha256": stable_hash({"context": req["context"], "question": req["question"]}), "context_tokens": int(context_ids.shape[1])}, "full_kv_reference": {"generated_token_ids_sha256": token_ids_digest(full["generated_token_ids"]), "generated_token_count": len(full["generated_token_ids"])}, "route_a_active_contract": {"forced_reference_token_ids_sha256": token_ids_digest(full["generated_token_ids"]), "forced_token_inputs_equal_full_kv": True, "deferred_activation_summary": backend.deferred_activation_summary(), "post_commit_policy_decode_call_count_by_layer": backend.policy_decode_calls, "same_mask_numerical_guard_work": backend.same_mask_numerical_guard_work_summary(), "full_kv_fallback_or_protection_entered": False}, "post_commit_logical_trace": {"schema_version": RouteALifecycleTransitionRecorder.SCHEMA, "path": str(trace.relative_to(output_dir.parents[1])), "sha256": trace_hash, "event_count": len(recorder.events), "summary": recorder.summary()}, "finite_horizon_tail_analysis": tail}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists(): raise FileExistsError(f"output directory already exists: {args.output_dir}")
    fixed = (12, HORIZON, 1, 64, 512, 42, "record_only")
    if (args.context_repetitions, args.fixed_new_tokens, args.deferred_decode_steps, args.page_tokens, args.admission_budget, args.seed, args.execution_dtype_ulp_mode) != fixed or min(args.rtol, args.atol) <= 0: raise ValueError("A4.6.0 is fixed to the 64-step, D=1, Q=1 functional-control inputs")
    a442, source_rows = read_a442(args.a442_report, args.anchor)
    if args.anchor == "qwen3_8b":
        model, revision, predictor_revision = QWEN_MODEL, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION
        if args.predictor_repo_id_override is not None: raise ValueError("Qwen must retain default predictor derivation")
    else:
        model, revision = LLAMA_MODEL, LLAMA_REVISION
        predictor_revision = str(json.loads(Path(a442["input_artifacts"][args.anchor]["report_path"]).read_text())["provenance"]["predictor_revision"])
        if args.predictor_repo_id_override != OFFICIAL_PREDICTOR_REPO or not predictor_revision: raise ValueError("Llama requires reviewed predictor override")
    if args.preflight_only:
        print(f"A4.6.0 preflight passed: {args.anchor}, A4.4.2 hash-bound normal-path source; no model loaded."); return
    cuda = cuda_environment(require_single_visible_device=True); args.output_dir.mkdir(parents=True)
    config={k:(str(v) if isinstance(v,Path) else v) for k,v in vars(args).items() if k!="output_dir"}
    (args.output_dir/"a460_steady_state_started.json").write_text(json.dumps({"schema_version":SCHEMA,"status":"started","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"config":config,"config_hash":stable_hash(config)},indent=2,sort_keys=True)+"\n")
    print(f"Loading A4.6.0 {args.anchor} base model: {model}", flush=True)
    pipe=pipeline("kv-press-text-generation",model=model,revision=revision,device_map="auto",dtype="auto")
    if getattr(pipe.model.config,"_commit_hash",None)!=revision: raise AssertionError("model revision mismatch")
    if args.anchor=="qwen3_8b":
        lm=pipe.model.model.language_model if hasattr(pipe.model.model,"language_model") else pipe.model.model; layers=tuple(range(len(lm.layers))); heads=qwen_kv_head_counts(lm)
    else:
        count,h=validate_runtime_structure(pipe.model)
        if (count,h)!=(EXPECTED_STRUCTURE["layer_count"],EXPECTED_STRUCTURE["kv_head_count"]): raise AssertionError("Llama structure mismatch")
        layers=tuple(range(count)); heads={x:h for x in layers}
    rows={w:run_workload(workload=w,pipe=pipe,args=args,layers=layers,heads=heads,predictor_revision=predictor_revision,output_dir=args.output_dir/w) for w in WORKLOADS}
    report={"schema_version":SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"config":config,"config_hash":stable_hash(config),"execution_classification":"model-on Route-A-active functional lifecycle trace plus untimed finite-horizon logical tail analysis; no measured or modeled hardware result","provenance":{"a442_report_path":str(args.a442_report),"a442_report_sha256":sha256_file(args.a442_report),"predictor_revision":predictor_revision},"cuda_environment":cuda,"model_structure":{"layer_count":len(layers),"kv_head_count_by_layer":{str(k):heads[k] for k in layers}},"per_workload":rows,"observational_guards":{"single_visible_cuda_device":True,"a442_hash_bound_activation_source":True,"activation_then_route_a_active_without_fallback_each_workload":True,"fixed_full_kv_token_inputs_equal_each_workload":True,"all_layer_all_kv_head_lifecycle_trace_each_workload":True,"tail_analysis_untimed_logical_only":True,"no_hardware_parameter_selected":True},"boundaries":["A4.6.0 tests only a bounded 64-step Route-A-active functional continuation after a D=1 activation. Full-KV is used only as a fixed-token reference, never as Route-A runtime fallback/backing in the active branch.","Tail analysis is an untimed logical append-opportunity check. It does not establish indefinite stability, arrival/service rate, FIFO occupancy/capacity, overflow, controller timing, physical traffic, burst, latency, throughput, energy, area, architecture specification, or RTL.","Qwen and Llama rows remain separate; no common resource envelope or parameter is derived."],"torch_version":str(torch.__version__),"transformers_version":str(transformers.__version__)}
    out=args.output_dir/"a460_route_a_active_steady_state_gate_report.json"; out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n"); print(f"A4.6.0 {args.anchor} steady-state gate completed: {out}")

if __name__=="__main__": main()
