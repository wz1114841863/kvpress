#!/usr/bin/env python3
"""M5.1 fixed-continuation Llama Route-A source/fan-in descriptor.

M5 preserved an observed natural-generation horizon mismatch (six versus seven
``q_len=1`` calls).  M5.1 intentionally does not treat an EOS-stoppable
pipeline cap as a matched horizon.  It uses a declared fixed continuation
length for Full-KV, online same-mask dense, and Route-A replay.  This is a
functional conditioning mechanism for descriptor alignment, not a claim about
natural generation length or quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from huggingface_hub import snapshot_download
from transformers import DynamicCache, pipeline

from kvpress.route_a_attention import RouteALogicalEventRecorder
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAPolicyAttentionBackendSet
from tools.export_kvzap_predictor_trace import assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_llama31_m1_semantic_gate import (
    EXPECTED_STRUCTURE,
    assert_all_layer_head_coverage,
    assert_numerical_guard_work,
    make_predictor,
    read_completed_m0,
    source_coverage,
    validate_runtime_structure,
)
from tools.run_kvzap_llama31_m2_lifecycle_gate import read_completed_m1
from tools.run_kvzap_llama31_m5_matched_horizon_workload_descriptor import (
    EVENT_SCHEMA,
    M5_SCHEMA,
    WORKLOADS,
    sha256_file,
    spread,
    summarize_events,
    validate_event_summary,
    validate_prior_contracts,
    write_events,
)
from tools.run_kvzap_trace import build_builtin_request, seed_everything
from tools.validate_kvzap_llama31_m0_provenance import (
    DEFAULT_MODEL_REPO,
    DEFAULT_MODEL_REVISION,
    OFFICIAL_PREDICTOR_REPO,
)


M51_SCHEMA = "kvzap-llama31-m51-fixed-horizon-workload-descriptor-1.1"
M51_PREVIOUS_SCHEMA = "kvzap-llama31-m51-fixed-horizon-workload-descriptor-1.0"


def token_ids_digest(token_ids: list[int]) -> str:
    payload = ",".join(str(token) for token in token_ids).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def expected_policy_decode_calls(max_new_tokens: int) -> int:
    """The question forward emits token zero; later fixed steps are q_len=1."""
    if max_new_tokens < 2:
        raise ValueError("fixed continuation requires at least two generated tokens")
    return max_new_tokens - 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M5.1 fixed-horizon Llama source/fan-in logical-event descriptor; no natural-length, timing, or hardware study."
    )
    parser.add_argument("--m0-manifest", type=Path, required=True)
    parser.add_argument("--m1-manifest", type=Path, required=True)
    parser.add_argument("--m4-report", type=Path, required=True)
    parser.add_argument("--m41-report", type=Path, required=True)
    parser.add_argument("--m5-failed-started-record", type=Path, required=True, help="Retained M5 started record used only to bind the observed natural-horizon mismatch.")
    parser.add_argument("--m51-failed-started-record", type=Path, required=True, help="Retained M5.1.0 started record used only to bind the rejected whole-logit gate.")
    parser.add_argument("--presets", nargs="+", choices=WORKLOADS, default=list(WORKLOADS))
    parser.add_argument("--model-name", default=DEFAULT_MODEL_REPO)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--predictor-repo-id-override", required=True)
    parser.add_argument("--threshold", type=float, default=-7.0)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--page-tokens", type=int, default=64, help="Functional reference input; not a hardware choice.")
    parser.add_argument("--admission-budget", type=int, default=512, help="Functional reference input; not a hardware choice.")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--fixed-new-tokens", type=int, default=8, help="Exact continuation length; EOS does not shorten this functional conditioning run.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--execution-dtype-ulp-mode", choices=("enforce", "record_only"), default="record_only")
    parser.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def load_failed_m5(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"retained M5 started record is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != M5_SCHEMA or value.get("status") != "started":
        raise ValueError("M5.1 requires the preserved started record from the failed M5 natural-horizon attempt")
    return value


def load_failed_m51(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"retained M5.1.0 started record is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != M51_PREVIOUS_SCHEMA or value.get("status") != "started":
        raise ValueError("M5.1 schema v1.1 requires the preserved M5.1.0 started record")
    return value


def fixed_continuation(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, args: argparse.Namespace, backend=None, forced_token_ids: list[int] | None = None) -> dict[str, Any]:
    """Run an exact number of continuation steps without EOS early stopping.

    ``forced_token_ids`` is used only for the Route-A replay to consume the
    dense path's exact token trajectory.  Dense and Full-KV choose greedy token
    IDs, but all paths execute the same declared number of model forwards.
    """
    if forced_token_ids is not None and len(forced_token_ids) != args.fixed_new_tokens:
        raise ValueError("forced fixed-continuation token count differs from the declared horizon")
    seed_everything(args.seed)
    cache = DynamicCache()
    logits: list[torch.Tensor] = []
    generated: list[int] = []
    context = backend if backend is not None else torch.no_grad()
    with torch.no_grad(), context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        position = torch.arange(
            int(context_ids.shape[1]), int(context_ids.shape[1]) + int(question_ids.shape[1]),
            device=pipe.model.device,
        ).unsqueeze(0)
        output = pipe.model(
            input_ids=question_ids,
            past_key_values=cache,
            position_ids=position,
            num_logits_to_keep=1,
        )
        logits.append(output.logits[0, -1].detach())
        for step in range(args.fixed_new_tokens):
            token = int(forced_token_ids[step]) if forced_token_ids is not None else int(logits[-1].argmax().item())
            generated.append(token)
            if step + 1 == args.fixed_new_tokens:
                break
            output = pipe.model(
                input_ids=torch.tensor([[token]], dtype=question_ids.dtype, device=pipe.model.device),
                past_key_values=cache,
                position_ids=torch.tensor([[int(context_ids.shape[1]) + int(question_ids.shape[1]) + step]], device=pipe.model.device),
                num_logits_to_keep=1,
            )
            logits.append(output.logits[0, -1].detach())
    if len(generated) != args.fixed_new_tokens or len(logits) != args.fixed_new_tokens:
        raise AssertionError("fixed continuation did not execute its declared horizon")
    return {"generated_token_ids": generated, "logits": logits}


def validate_forced_token_trajectory(*, dense: dict[str, Any], route: dict[str, Any], workload: str) -> None:
    """Verify fixed-token conditioning without asserting whole-model logits.

    The Route-A backend already executes FP32/executed-dtype same-mask guards
    at every selected attention evaluation.  Those are the M1/M2 numerical
    contract.  A whole-vocabulary logit equality assertion after deliberately
    continuing beyond EOS is neither required nor established by that contract.
    """
    if dense["generated_token_ids"] != route["generated_token_ids"]:
        raise AssertionError(f"M5.1 {workload}: forced Route-A token IDs differ from the dense source")


def run_workload(*, workload: str, pipe, args: argparse.Namespace, revision: str, layers: int, heads: int, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    request = build_builtin_request(workload, args.context_repetitions)
    tokens = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokens["context_ids"].to(pipe.model.device)
    question_ids = tokens["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size:
        raise ValueError(f"M5.1 {workload} request does not exceed the protected hot window")
    print(f"M5.1 {workload}: fixed-horizon Full-KV bypass...", flush=True)
    full = fixed_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args)
    assert_no_runtime_mask_state(pipe.model)
    selected_layers = tuple(range(layers))
    predictor = make_predictor(predictor_revision=revision, override=args.predictor_repo_id_override)
    dense_backend = DenseSameMaskAttentionBackendSet(
        pipe.model, predictor, layers=selected_layers, kv_head=None, threshold=args.threshold,
        window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget,
        rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps,
        execution_dtype_ulp_mode=args.execution_dtype_ulp_mode,
        ulp_breach_sample_limit=args.ulp_breach_sample_limit,
    )
    print(f"M5.1 {workload}: fixed-horizon online same-mask dense source...", flush=True)
    dense = fixed_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, backend=dense_backend)
    assert_no_runtime_mask_state(pipe.model)
    dense_coverage = dense_backend.coverage()
    assert_all_layer_head_coverage(dense_coverage, expected_layers=layers, expected_kv_heads=heads, label=f"M5.1 {workload} dense")
    assert_numerical_guard_work(dense_backend.same_mask_numerical_guard_work_summary(), layers, label=f"M5.1 {workload} dense")
    recorder = RouteALogicalEventRecorder()
    route_backend = RouteAPolicyAttentionBackendSet(
        pipe.model, None, layers=selected_layers, kv_head=None, threshold=args.threshold,
        window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget,
        rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps,
        execution_dtype_ulp_mode=args.execution_dtype_ulp_mode,
        ulp_breach_sample_limit=args.ulp_breach_sample_limit, replay_mask_events=dense_backend.mask_events(),
        elide_empty_sources=True, logical_event_recorder=recorder,
    )
    print(f"M5.1 {workload}: fixed-horizon Route-A exact-mask replay with untimed event recorder...", flush=True)
    route = fixed_continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, args=args, backend=route_backend, forced_token_ids=dense["generated_token_ids"])
    assert_no_runtime_mask_state(pipe.model)
    route_backend.assert_replay_complete()
    if dense_backend.mask_events() != route_backend.mask_events():
        raise AssertionError(f"M5.1 {workload}: Route-A replay events differ from online dense source")
    validate_forced_token_trajectory(dense=dense, route=route, workload=workload)
    route_coverage = route_backend.coverage()
    assert_all_layer_head_coverage(route_coverage, expected_layers=layers, expected_kv_heads=heads, label=f"M5.1 {workload} Route-A")
    assert_numerical_guard_work(route_backend.same_mask_numerical_guard_work_summary(), layers, label=f"M5.1 {workload} Route-A")
    sources = source_coverage(route_backend.comparisons)
    if not sources["hot_observed"] or not sources["packed_observed"]:
        raise AssertionError(f"M5.1 {workload}: required hot/packed source is absent")
    summary = recorder.summary()
    validate_event_summary(summary, layers=layers, heads=heads)
    event_path = output_dir / "llama31_m51_fixed_horizon_logical_attention_events.jsonl.gz"
    event_sha256 = write_events(event_path, recorder.events)
    calls = set(route_backend.policy_decode_calls.values())
    expected_calls = expected_policy_decode_calls(args.fixed_new_tokens)
    if calls != {expected_calls}:
        raise ValueError(f"M5.1 {workload}: expected {expected_calls} policy-decode calls in every layer, observed {sorted(calls)}")
    return {
        "request": {"request_id": request["request_id"], "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}), "context_tokens": int(context_ids.shape[1])},
        "full_kv_bypass": {"generated_token_ids_sha256": token_ids_digest(full["generated_token_ids"]), "generated_token_count": len(full["generated_token_ids"]), "zero_route_a_admission": True},
        "online_same_mask_dense": {"generated_token_ids_sha256": token_ids_digest(dense["generated_token_ids"]), "generated_token_count": len(dense["generated_token_ids"]), "policy_decode_call_count_by_layer": dense_backend.policy_decode_calls, "policy_coverage": dense_coverage, "same_mask_numerical_guard_work": dense_backend.same_mask_numerical_guard_work_summary(), "execution_dtype_ulp_breach_summary": dense_backend.execution_dtype_ulp_breach_summary()},
        "replayed_same_mask_route_a": {"generated_token_ids_sha256": token_ids_digest(route["generated_token_ids"]), "generated_token_count": len(route["generated_token_ids"]), "policy_decode_call_count_by_layer": route_backend.policy_decode_calls, "policy_coverage": route_coverage, "source_coverage": sources, "same_mask_numerical_guard_work": route_backend.same_mask_numerical_guard_work_summary(), "execution_dtype_ulp_breach_summary": route_backend.execution_dtype_ulp_breach_summary()},
        "same_mask_pairing": {"mode": "replayed_online_dense_mask_forced_fixed_continuation", "route_a_replay_consumption_complete": True, "forced_token_ids_sha256": token_ids_digest(dense["generated_token_ids"]), "forced_token_ids_equal_dense": True, "attention_same_mask_numerical_guards_executed": True},
        "logical_event_artifact": {"schema_version": EVENT_SCHEMA, "path": str(event_path.relative_to(output_dir.parents[1])), "sha256": event_sha256, "event_count": len(recorder.events), "recording_semantics": "global logical attention invocation order; no source completion, reduction arrival, Python timestamp, CUDA timestamp, or hardware time"},
        "logical_event_summary": summary,
        "actual_policy_decode_calls": expected_calls,
        "descriptor": summarize_events(recorder.events),
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if sorted(args.presets) != sorted(WORKLOADS) or len(set(args.presets)) != len(WORKLOADS):
        raise ValueError("M5.1 requires retrieval, summarization, and reasoning exactly once")
    fixed_contract = (DEFAULT_MODEL_REPO, DEFAULT_MODEL_REVISION, OFFICIAL_PREDICTOR_REPO, -7.0, 128, 64, 512, 12, 8, 16.0, "record_only", 32)
    observed = (args.model_name, args.model_revision, args.predictor_repo_id_override, args.threshold, args.window_size, args.page_tokens, args.admission_budget, args.context_repetitions, args.fixed_new_tokens, args.max_executed_dtype_ulps, args.execution_dtype_ulp_mode, args.ulp_breach_sample_limit)
    if observed != fixed_contract:
        raise ValueError("M5.1 is fixed to M4 inputs and an explicit eight-token fixed continuation")
    if min(args.rtol, args.atol, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit) <= 0 or args.device != "cuda":
        raise ValueError("invalid M5.1 numerical guard dimensions or non-CUDA device")
    m0_sha256 = sha256_file(args.m0_manifest)
    read_completed_m0(args.m0_manifest)
    m1 = read_completed_m1(args.m1_manifest, m0_sha256=m0_sha256)
    m1_sha256 = sha256_file(args.m1_manifest)
    m4, m41 = validate_prior_contracts(args=args, m0_sha256=m0_sha256, m1_sha256=m1_sha256)
    failed_m5 = load_failed_m5(args.m5_failed_started_record)
    failed_m51 = load_failed_m51(args.m51_failed_started_record)
    if failed_m5.get("config", {}).get("max_new_tokens") != args.fixed_new_tokens:
        raise ValueError("M5.1 fixed continuation must preserve the failed M5 declared cap")
    if failed_m51.get("config", {}).get("fixed_new_tokens") != args.fixed_new_tokens:
        raise ValueError("M5.1 schema v1.1 must preserve the failed M5.1.0 fixed horizon")
    revision = str(m1["config"]["predictor_revision"])
    args.output_dir.mkdir(parents=True)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    started = {"schema_version": M51_SCHEMA, "status": "started", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "boundaries": ["M5.1 conditions every path on an explicit fixed continuation; it is not an observed natural generation-length study.", "The M4.1 summarization record-only ULP context remains explicit and cannot select numerical hardware parameters."]}
    (args.output_dir / "llama31_m51_fixed_horizon_started.json").write_text(json.dumps(started, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"
    print(f"Loading M5.1 base model: {args.model_name}", flush=True)
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise AssertionError("loaded base model revision differs from M0/M1")
    layers, heads = validate_runtime_structure(pipe.model)
    if (layers, heads) != (EXPECTED_STRUCTURE["layer_count"], EXPECTED_STRUCTURE["kv_head_count"]):
        raise AssertionError("loaded model dimensions differ from fixed M5.1 structure")
    snapshot = Path(snapshot_download(repo_id=OFFICIAL_PREDICTOR_REPO, revision=revision))
    if snapshot.name != revision:
        raise AssertionError("resolved Linear predictor snapshot differs from M1")
    per_workload = {workload: run_workload(workload=workload, pipe=pipe, args=args, revision=revision, layers=layers, heads=heads, output_dir=args.output_dir / workload) for workload in args.presets}
    calls = {row["actual_policy_decode_calls"] for row in per_workload.values()}
    if calls != {expected_policy_decode_calls(args.fixed_new_tokens)}:
        raise ValueError("M5.1 did not retain a common fixed policy-decode-call count")
    summaries = {workload: row["descriptor"] for workload, row in per_workload.items()}
    report = {
        "schema_version": M51_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "fixed-request functional and timestamp-free logical-event evidence under an explicit fixed continuation; no modeled or measured hardware evidence",
        "provenance": {"m0_manifest_sha256": m0_sha256, "m1_manifest_sha256": m1_sha256, "m4_report_sha256": sha256_file(args.m4_report), "m41_report_sha256": sha256_file(args.m41_report), "failed_m5_started_record_sha256": sha256_file(args.m5_failed_started_record), "failed_m5_schema": failed_m5["schema_version"], "failed_m51_started_record_sha256": sha256_file(args.m51_failed_started_record), "failed_m51_schema": failed_m51["schema_version"], "predictor_revision": revision, "predictor_snapshot_path": str(snapshot), "m4_matched_functional_reference_inputs": m4["shared_provenance"]["matched_functional_reference_inputs"], "m41_strict_ulp_context": m41["m41_decision"]["strict_16_ulp_contract_for_summarization"]},
        "continuation_contract": {"mode": "fixed_non_eos_continuation", "fixed_new_tokens": args.fixed_new_tokens, "expected_q_len_one_policy_decode_calls": expected_policy_decode_calls(args.fixed_new_tokens), "dense_token_trajectory_replayed_by_route_a_per_workload": True, "natural_generation_length_claimed": False},
        "per_workload": per_workload,
        "cross_workload": {"workloads": list(args.presets), "shared_actual_policy_decode_calls": calls.pop(), "fan_in_fraction_spread": spread(summaries, "fan_in_fractions"), "source_combination_fraction_spread": spread(summaries, "source_combination_fractions"), "interpretation": "The three fixed Llama requests are conditioned on the same declared continuation length and q_len=1 call count. Their normalized descriptors align in field and horizon with Qwen A4.2.8, but neither set is a natural-generation distribution or common hardware envelope."},
        "observational_guards": {"m0_m1_m4_m41_hash_bound": True, "failed_m5_natural_horizon_record_bound": True, "failed_m51_whole_logit_gate_record_bound": True, "m41_non_strict_summarization_context_retained": True, "full_kv_bypass_zero_route_a_admission_each_workload": all(row["full_kv_bypass"]["zero_route_a_admission"] for row in per_workload.values()), "all_32_layers_all_8_kv_heads_covered_each_workload": True, "online_dense_mask_replayed_exactly_once_each_workload": True, "attention_same_mask_numerical_guard_work_executed_each_workload": True, "dense_token_trajectory_forced_in_route_a_each_workload": True, "whole_model_logits_not_used_as_gate": True, "all_workloads_hot_packed_observed": all(row["replayed_same_mask_route_a"]["source_coverage"]["hot_observed"] and row["replayed_same_mask_route_a"]["source_coverage"]["packed_observed"] for row in per_workload.values()), "event_source_decisions_partition_merges_each_workload": True, "event_all_layer_all_kv_head_coverage_each_workload": True, "logical_events_have_no_timestamps": True, "shared_actual_policy_decode_calls": True, "no_hardware_parameter_selected": True},
        "boundaries": ["M5.1 deliberately disables EOS-based early stopping inside its fixed continuation. It does not report or represent natural output lengths, quality, or an end-to-end serving behavior.", "The existing per-attention FP32/executed-dtype same-mask guards remain the numerical contract. M5.1 does not assert whole-vocabulary model-logit equality after an explicitly forced post-EOS continuation.", "M5.1 records logical invocation order and source partial-or-skip decisions only. It contains no source-ready or completion timestamps, queue/FIFO occupancy, backpressure, cycles, latency, throughput, HBM traffic, energy, area, hardware acceleration, architecture specification, or RTL evidence.", "The explicit record-only mode retains the completed M4.1 summarization strict-16-ULP non-pass; it does not weaken the default M2 guard or establish a merge precision.", "Cross-model field alignment is semantic/descriptor alignment, not proof that Qwen3-8B and Llama require identical hardware or that Route-A transfers to arbitrary models or pruning algorithms."],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    output = args.output_dir / "llama31_m51_fixed_horizon_workload_descriptor_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"M5.1 fixed-horizon Llama descriptor completed: {output}")


if __name__ == "__main__":
    main()
