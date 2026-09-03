"""A4.1.2 whole-decode measurement gate under a frozen replayed KVzap mask.

Context prefill constructs a fresh cache and Route-A state outside the timed
region.  The one timed region is the question forward plus greedy decode loop,
which is KVPress's decode-stage contract.  This is a Python-reference software
measurement, not a packed-attention kernel or hardware benchmark.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import DynamicCache, pipeline

from kvpress.route_a_measurement import A412_RAW_SCHEMA, cuda_memory_snapshot, initialize_output_directory, raw_record, require_cuda_device, reset_cuda_peak_memory, summarize_reported_repetitions, summarize_values, time_cuda_region, write_raw_repetitions
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAPolicyAttentionBackendSet
from kvpress.route_a_replay import REPLAY_SOURCE_SCHEMA, load_replay_events, sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, get_git_commit, stable_hash
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


WHOLE_DECODE_COMPONENT = "whole_decode_question_and_generation"
A412_SCHEMA = "kvzap-route-a412-whole-decode-gate-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.2 replayed-mask whole-decode measurement: one synchronized decode region per reset run.")
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--model-name", default=DEFAULT_MODEL)
    parser.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR)
    parser.add_argument("--predictor-revision", default=GATE_A_PREDICTOR_REVISION)
    parser.add_argument("--threshold", type=float, default=-4.0)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--page-tokens", type=int, default=64)
    parser.add_argument("--admission-budget", type=int, required=True)
    parser.add_argument("--target-layers", nargs="+", default=["0", "18", "35"], help="One or more layer indices. The first A4.1.2 gate is 0 18 35.")
    parser.add_argument("--target-kv-head", default="all", choices=["all"], help="A4.1.2 initially substitutes every KV head in each target layer.")
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--warmup-repetitions", type=int, default=3)
    parser.add_argument("--measured-repetitions", type=int, default=10)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--replay-source-dir", type=Path, required=True, help="Completed replay source covering exactly --target-layers.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def resolve_target_layers(values: list[str], layer_count: int) -> tuple[int, ...]:
    try:
        layers = tuple(int(value) for value in values)
    except ValueError as error:
        raise ValueError("--target-layers must contain non-negative integer indices") from error
    if not layers or len(set(layers)) != len(layers) or any(not 0 <= layer < layer_count for layer in layers):
        raise ValueError(f"--target-layers must be unique indices in [0,{layer_count})")
    return layers


def schedule_runs(*, warmups: int, measured: int, seed: int) -> list[tuple[str, int, bool]]:
    rng = random.Random(seed)
    schedule: list[tuple[str, int, bool]] = []
    for warmup in (True, False):
        for repetition in range(warmups if warmup else measured):
            paths = ["full_kv_bypass", "same_mask_dense_replay", "same_mask_route_a_replay"]
            rng.shuffle(paths)
            schedule.extend((path, repetition, warmup) for path in paths)
    return schedule


def manifest_config(args: argparse.Namespace) -> dict[str, Any]:
    return {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}


def answer_hash(answer: str) -> str:
    return hashlib.sha256(answer.encode("utf-8")).hexdigest()


def token_ids_hash(token_ids: list[int]) -> str:
    return hashlib.sha256(json.dumps(token_ids, separators=(",", ":")).encode("utf-8")).hexdigest()


def read_source(source_dir: Path, *, args: argparse.Namespace, layers: tuple[int, ...]) -> tuple[dict[int, dict[tuple[int, int], tuple[bool, float]]], dict[str, Any], str]:
    manifest_path = source_dir / "a41_replay_mask_source_manifest.json"
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    if source.get("schema_version") != REPLAY_SOURCE_SCHEMA or source.get("status") != "complete":
        raise ValueError("replay source manifest is not a completed A4.1 replay source")
    required = {
        "model_name": args.model_name, "model_revision": args.model_revision,
        "predictor_name": args.predictor_name, "predictor_revision": args.predictor_revision,
        "threshold": args.threshold, "window_size": args.window_size,
        "page_tokens": args.page_tokens, "context_repetitions": args.context_repetitions,
        "max_new_tokens": args.max_new_tokens, "seed": args.seed,
    }
    if any(source["config"].get(key) != value for key, value in required.items()):
        raise ValueError("replay source configuration differs from whole-decode configuration")
    if source["config"].get("resolved_target_layers") != list(layers):
        raise ValueError("replay source layers differ from --target-layers")
    event_path = source_dir / source["event_file"]
    digest = sha256_file(event_path)
    if digest != source["event_file_sha256"]:
        raise ValueError("replay event source SHA-256 mismatch")
    events = load_replay_events(event_path)
    if set(events) != set(layers) or sum(len(layer_events) for layer_events in events.values()) != source["event_count"]:
        raise ValueError("replay source events differ from its manifest")
    return events, source, digest


def whole_decode_summary(records: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    summary = summarize_reported_repetitions(records)
    reported = [row for row in records if not row["warmup"]]
    paths = sorted({row["path"] for row in reported})
    summary["whole_decode_generated_tokens"] = [
        {
            "path": path,
            "reported_reset_runs": sum(row["path"] == path for row in reported),
            "generated_token_count": summarize_values([float(row["generated_token_count"]) for row in reported if row["path"] == path]),
            "answer_sha256_values": sorted({str(row["answer_sha256"]) for row in reported if row["path"] == path}),
            "generated_token_ids_sha256_values": sorted({str(row["generated_token_ids_sha256"]) for row in reported if row["path"] == path}),
        }
        for path in paths
    ]
    summary.update({"raw_record_count": len(records), "run_outcomes": outcomes})
    return summary


def run_one_path(*, pipe, context_ids: torch.Tensor, question_ids: torch.Tensor, path: str, backend, args: argparse.Namespace, repetition: int, execution_order: int, warmup: bool, event_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    seed_everything(args.seed)
    cache = DynamicCache()
    context = backend if backend is not None else contextlib.nullcontext()
    with torch.no_grad(), context:
        pipe.model.model(input_ids=context_ids, past_key_values=cache)
        memory_before = reset_cuda_peak_memory(args.device)
        result, timing = time_cuda_region(
            lambda: pipe.generate_answer(question_ids=question_ids, cache=cache, context_length=int(context_ids.shape[1]), max_new_tokens=args.max_new_tokens, return_token_ids=True),
            device=args.device,
        )
        memory_after = cuda_memory_snapshot(args.device)
    if not isinstance(result, tuple) or len(result) != 2:
        raise AssertionError("whole-decode pipeline did not return answer plus generated token IDs")
    answer, token_ids = result
    if not isinstance(answer, str) or not isinstance(token_ids, list) or not token_ids:
        raise AssertionError("whole-decode result is missing generated answer/token IDs")
    record = raw_record(path=path, component=WHOLE_DECODE_COMPONENT, repetition=repetition, execution_order=execution_order, warmup=warmup, timing=timing, memory_before=memory_before, memory_after=memory_after, schema_version=A412_RAW_SCHEMA)
    record.update({"generated_token_count": len(token_ids), "generated_token_ids_sha256": token_ids_hash(token_ids), "answer_sha256": answer_hash(answer), "timed_region": "question_forward_plus_greedy_decode", "replay_event_file_sha256": event_sha256})
    outcome = {"path": path, "repetition": repetition, "execution_order": execution_order, "warmup": warmup, "answer_sha256": record["answer_sha256"], "generated_token_count": len(token_ids), "generated_token_ids_sha256": record["generated_token_ids_sha256"]}
    return record, outcome


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens, args.max_executed_dtype_ulps, args.warmup_repetitions, args.measured_repetitions) <= 0 or args.window_size < 0:
        raise ValueError("invalid A4.1.2 dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("whole-decode gate is bounded to frozen Qwen3-8B and official MLP revisions")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    layers = resolve_target_layers(args.target_layers, len(language_model.layers))
    args.resolved_target_layers = list(layers)
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args, layers=layers)
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_ids = tokenized["context_ids"].to(pipe.model.device)
    question_ids = tokenized["questions_ids"][0].to(pipe.model.device)
    if int(context_ids.shape[1]) <= args.window_size or args.max_new_tokens < 2:
        raise ValueError("request does not exercise protected hot-window decode state")
    config = manifest_config(args)
    config["replay_event_file_sha256"] = event_sha256
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit(), record_name="a412_whole_decode_started.json", schema_version=A412_SCHEMA, boundaries=["A4.1.2 measures the question-forward plus greedy-decode region after untimed context prefill.", "Each reset run has one synchronized CUDA timing region; no component callback timer is installed.", "Allocator counters are PyTorch allocator bytes, not HBM traffic."])
    schedule = schedule_runs(warmups=args.warmup_repetitions, measured=args.measured_repetitions, seed=args.seed)
    records: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for execution_order, (path, repetition, warmup) in enumerate(schedule):
        backend = None
        if path == "same_mask_dense_replay":
            backend = DenseSameMaskAttentionBackendSet(pipe.model, None, layers=layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=events)
        elif path == "same_mask_route_a_replay":
            backend = RouteAPolicyAttentionBackendSet(pipe.model, None, layers=layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=events)
        print(f"{('Warmup' if warmup else 'Measured')} {repetition + 1}: {path} (execution_order={execution_order})")
        record, outcome = run_one_path(pipe=pipe, context_ids=context_ids, question_ids=question_ids, path=path, backend=backend, args=args, repetition=repetition, execution_order=execution_order, warmup=warmup, event_sha256=event_sha256)
        assert_no_runtime_mask_state(pipe.model)
        if backend is not None:
            backend.assert_replay_complete()
            if not backend.comparisons or not all(backend.policy_decode_calls.get(layer, 0) > 0 for layer in layers):
                raise AssertionError(f"{path}: no complete policy decode observation in every selected layer")
            outcome["policy_decode_call_count_by_layer"] = backend.policy_decode_calls
            outcome["policy_coverage"] = backend.coverage()
        else:
            outcome["full_kv_bypass_zero_route_a_admission"] = True
        records.append(record)
        outcomes.append(outcome)
    raw_path = write_raw_repetitions(args.output_dir, records)
    summary = whole_decode_summary(records, outcomes)
    summary["raw_path"] = raw_path.name
    manifest = {
        "schema_version": A412_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"], "source_answer_sha256": source["answer_sha256"]},
        "summary": summary, "source_artifact_sha256": source["source_artifact_sha256"],
        "observational_guards": {"paired_mask_mode": "replayed_dense_mask", "full_kv_bypass_zero_route_a_admission": True, "route_a_predictor_scored_online": False, "replay_mask_consumption_complete": True, "fp32_same_mask_guard": {"rtol": args.rtol, "atol": args.atol}, "one_timed_region_per_reset_run": True, "component_timer_installed": False, "timed_region": "question_forward_plus_greedy_decode"},
        "boundaries": ["This is an A4.1.2 Python-reference software measurement after untimed context prefill, not a packed-attention kernel benchmark.", "Full-KV bypass is distinct from the replayed dense/Route-A pair. Full-KV answer equivalence is recorded, not required.", "Allocator counters are PyTorch allocator observations, not HBM traffic. This is not throughput, energy, area, frequency, hardware acceleration, or RTL evidence."],
        "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__),
    }
    path = args.output_dir / "a412_whole_decode_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.2 whole-decode gate completed: {path}")


if __name__ == "__main__":
    main()
