"""A4.2.4 ordered logical source/merge event gate; untimed semantic evidence."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import pipeline

from kvpress.route_a_attention import RouteALogicalEventRecorder
from kvpress.route_a_measurement import initialize_output_directory, require_cuda_device
from kvpress.route_a_replay import sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_route_a4123_first_decode_logits_diagnostic import paired_logit_relation
from tools.run_kvzap_route_a4128_allhead_continuation_diagnostic import token_ids_digest
from tools.run_kvzap_route_a412_whole_decode_gate import read_source
from tools.run_kvzap_route_a4148_qwen_external_storage_profiler import EXTERNAL_STORAGE_PATH, make_backend_and_cache
from tools.run_kvzap_route_a4151_guard_elided_execution_semantic_gate import continuation, validate_replay_event_coverage, verify_backend
from tools.run_kvzap_route_a4152_certified_execution_mode_whole_decode_measurement import validate_route_certificate
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request


A424_SCHEMA = "kvzap-route-a424-ordered-logical-event-gate-1.0"
EVENT_SCHEMA = RouteALogicalEventRecorder.SCHEMA


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.2.4 untimed ordered Route-A logical-event gate; no profiler, runtime, or hardware measurement.")
    request = parser.add_mutually_exclusive_group(); request.add_argument("--preset", choices=PRESETS, default="summarization"); request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id"); parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--model-name", default=DEFAULT_MODEL); parser.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR); parser.add_argument("--predictor-revision", default=GATE_A_PREDICTOR_REVISION)
    parser.add_argument("--threshold", type=float, default=-4.0); parser.add_argument("--window-size", type=int, default=128); parser.add_argument("--page-tokens", type=int, default=64)
    parser.add_argument("--admission-budget", type=int, required=True); parser.add_argument("--target-layers", nargs="+", default=["all"]); parser.add_argument("--target-kv-head", choices=("all",), default="all")
    parser.add_argument("--max-new-tokens", type=int, required=True); parser.add_argument("--seed", type=int, default=42); parser.add_argument("--rtol", type=float, default=1e-4); parser.add_argument("--atol", type=float, default=1e-5); parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0); parser.add_argument("--ulp-breach-sample-limit", type=int, default=32)
    parser.add_argument("--device", default="cuda"); parser.add_argument("--replay-source-dir", type=Path, required=True); parser.add_argument("--route-a-execution-certification", type=Path, required=True); parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def write_events(path: Path, events: list[dict[str, Any]]) -> str:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_event_summary(*, summary: dict[str, Any], expected_heads: dict[int, tuple[int, ...]]) -> None:
    merges = int(summary.get("merge_event_count", -1))
    if merges <= 0 or int(summary.get("event_count", -1)) != merges or summary.get("timestamps_recorded") is not False:
        raise ValueError("logical event summary has invalid merge count or timestamp field")
    for source in ("hot", "pending", "packed"):
        row = summary.get("by_source", {}).get(source, {})
        if int(row.get("partial_attention_events", -1)) + int(row.get("empty_source_skip_events", -1)) != merges:
            raise ValueError(f"{source} logical source decisions do not partition merges")
    actual = {int(row["layer"]): tuple(int(head) for head in row["kv_heads"]) for row in summary.get("observed_layer_kv_heads", [])}
    if actual != expected_heads:
        raise ValueError("logical events do not cover every expected layer/KV head")


def run_route(*, pipe, context_ids, question_ids, layers, expected_heads, events, args, forced_token_ids: list[int] | None, recorder: RouteALogicalEventRecorder | None) -> dict[str, Any]:
    backend, cache = make_backend_and_cache(path=EXTERNAL_STORAGE_PATH, pipe=pipe, layers=layers, expected_heads=expected_heads, events=events, args=args, same_mask_numerical_guard_mode="execution_only", elide_empty_sources=True, logical_event_recorder=recorder)
    run = continuation(pipe=pipe, context_ids=context_ids, question_ids=question_ids, backend=backend, cache=cache, args=args, forced_token_ids=forced_token_ids)
    assert_no_runtime_mask_state(pipe.model)
    guard = verify_backend(backend=backend, cache=cache, expected_heads=expected_heads, args=args, guard_mode="execution_only")
    return {**run, "guard": guard, "logical_event_summary": None if recorder is None else recorder.summary()}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists(): raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None: raise ValueError("--request-id requires --input-jsonl")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512 or args.max_new_tokens < 2: raise ValueError("A4.2.4 requires all layers/heads, budget 512, and at least two output tokens")
    if min(args.context_repetitions, args.page_tokens, args.max_executed_dtype_ulps, args.ulp_breach_sample_limit) <= 0 or args.window_size < 0: raise ValueError("invalid A4.2.4 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION): raise ValueError("A4.2.4 is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"
    print(f"Loading base model: {args.model_name}"); pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision: raise ValueError("loaded model revision differs from frozen revision")
    lm = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model; layers = tuple(range(len(lm.layers))); expected_heads = {layer: tuple(range(int(lm.layers[layer].self_attn.config.num_key_value_heads))) for layer in layers}
    args.resolved_target_layers = list(layers); args.resolved_target_kv_heads_by_layer = {str(layer): list(heads) for layer, heads in expected_heads.items()}; args.require_any_pending = False; args.require_any_full_multi_tail_packed = True
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=layers)
    if source["config"].get("admission_budget") != args.admission_budget: raise ValueError("replay source admission budget differs")
    source_coverage = validate_replay_event_coverage(source=source, expected_heads=expected_heads)
    certificate = validate_route_certificate(path=args.route_a_execution_certification, args=args, event_sha256=event_sha256)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False); context_ids = tokenized["context_ids"].to(pipe.model.device); question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}; config.update({"replay_event_file_sha256": event_sha256, "same_mask_numerical_guard_mode": "execution_only", "logical_event_schema": EVENT_SCHEMA, "logical_event_has_no_timestamps": True})
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a424_ordered_logical_event_started.json", schema_version=A424_SCHEMA, boundaries=["A4.2.4 is an untimed logical event/semantic gate; it does not collect Python, CUDA, or hardware service timestamps.", "The ordered event artifact records Route-A source decisions and merge order only; it is not a queue, FIFO, latency, HBM, throughput, energy, area, or RTL measurement.", "Trace-off/on comparison is fixed-request same-mask semantic evidence, not a quality benchmark."])
    print("Pass 1/3: execution-only Route-A trace-off baseline..."); baseline = run_route(pipe=pipe, context_ids=context_ids, question_ids=question_ids, layers=layers, expected_heads=expected_heads, events=events, args=args, forced_token_ids=None, recorder=None)
    print("Pass 2/3: ordered logical-event forced-token pair..."); forced_recorder = RouteALogicalEventRecorder(); forced = run_route(pipe=pipe, context_ids=context_ids, question_ids=question_ids, layers=layers, expected_heads=expected_heads, events=events, args=args, forced_token_ids=baseline["generated_token_ids"], recorder=forced_recorder)
    print("Pass 3/3: ordered logical-event independent greedy run..."); independent_recorder = RouteALogicalEventRecorder(); independent = run_route(pipe=pipe, context_ids=context_ids, question_ids=question_ids, layers=layers, expected_heads=expected_heads, events=events, args=args, forced_token_ids=None, recorder=independent_recorder)
    for left, right in zip(baseline["logits"], forced["logits"], strict=True): torch.testing.assert_close(left, right, rtol=args.rtol, atol=args.atol)
    if baseline["generated_token_ids"] != independent["generated_token_ids"]: raise AssertionError("trace-on independent tokens differ from trace-off baseline")
    validate_event_summary(summary=forced["logical_event_summary"], expected_heads=expected_heads); validate_event_summary(summary=independent["logical_event_summary"], expected_heads=expected_heads)
    if forced["logical_event_summary"] != independent["logical_event_summary"]: raise AssertionError("forced and independent logical event summaries differ")
    event_path = args.output_dir / "a424_ordered_logical_attention_events.jsonl.gz"; event_sha256 = write_events(event_path, independent_recorder.events)
    manifest = {"schema_version": A424_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}), "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": source["event_file_sha256"], "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"], "event_coverage": source_coverage}, "route_a_execution_certificate": certificate, "logical_event_artifact": {"schema_version": EVENT_SCHEMA, "path": event_path.name, "sha256": event_sha256, "event_count": independent["logical_event_summary"]["event_count"], "recording_semantics": "global logical attention invocation order; no source completion, reduction arrival, Python timestamp, CUDA timestamp, or hardware time"}, "diagnostic": {"trace_off": {key: value for key, value in baseline.items() if key != "logits"} | {"generated_token_ids_sha256": token_ids_digest(baseline["generated_token_ids"])}, "trace_on_forced": {key: value for key, value in forced.items() if key != "logits"} | {"generated_token_ids_sha256": token_ids_digest(forced["generated_token_ids"])}, "trace_on_independent": {key: value for key, value in independent.items() if key != "logits"} | {"generated_token_ids_sha256": token_ids_digest(independent["generated_token_ids"])}, "trace_off_vs_on_forced_logit_steps": [paired_logit_relation(left, right) for left, right in zip(baseline["logits"], forced["logits"], strict=True)]}, "observational_guards": {"trace_off_execution_only_verified": True, "trace_on_forced_logits_close": True, "trace_on_independent_tokens_equal_trace_off": True, "replay_consumption_complete_each_run": True, "all_layers_all_kv_heads_external_storage_substituted_each_run": True, "persistent_selected_native_cold_absent_each_run": True, "ordered_event_source_decisions_partition_merges": True, "ordered_event_all_layer_all_kv_head_coverage": True, "logical_event_has_no_timestamps": True}, "boundaries": ["This is fixed-request functional/logical-order evidence. It is not an execution-time trace, quality benchmark, runtime measurement, queue measurement, HBM traffic, throughput, energy, area, hardware acceleration, or RTL evidence.", "A later modeled scheduler may use the artifact's invocation order with separately declared service assumptions; it must not treat these events as source completion or reduction arrival times."]}
    path = args.output_dir / "a424_ordered_logical_event_manifest.json"; path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(f"A4.2.4 ordered logical event gate completed: {path}")


if __name__ == "__main__": main()
