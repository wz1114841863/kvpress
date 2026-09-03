"""A4.1.1 single-layer/head component measurement under a replayed mask."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import pipeline

from kvpress.route_a_measurement import CudaComponentRecorder, initialize_output_directory, require_cuda_device, summarize_reported_repetitions, write_completed_manifest, write_raw_repetitions
from kvpress import KVzapPress
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet, RouteAPolicyAttentionBackendSet
from kvpress.route_a_replay import REPLAY_SOURCE_SCHEMA, load_replay_events, sha256_file
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, file_sha256, get_git_commit, stable_hash
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.1 replayed-mask one-layer/head component measurement; no end-to-end performance claim.")
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
    parser.add_argument("--target-layer", type=int, default=0)
    parser.add_argument("--target-kv-head", type=int, default=0)
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--warmup-repetitions", type=int, default=3)
    parser.add_argument("--measured-repetitions", type=int, default=10)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--include-online-predictor-control", action="store_true", help="Also measure an unpaired online dense predictor-score/mask control. It is not included in the same-mask paired comparison.")
    parser.add_argument("--replay-source-dir", type=Path, required=True, help="Completed A4.1 replay-mask source directory.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def answer_hash(output: dict[str, Any]) -> str:
    return hashlib.sha256(str(output["answer"]).encode("utf-8")).hexdigest()


def read_source(source_dir: Path, *, args: argparse.Namespace) -> tuple[dict[int, dict[tuple[int, int], tuple[bool, float]]], dict[str, Any], str]:
    manifest_path = source_dir / "a41_replay_mask_source_manifest.json"
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    if source.get("schema_version") != REPLAY_SOURCE_SCHEMA or source.get("status") != "complete":
        raise ValueError("replay source manifest is not a completed A4.1 replay source")
    config = source["config"]
    required = {
        "model_name": args.model_name,
        "model_revision": args.model_revision,
        "predictor_name": args.predictor_name,
        "predictor_revision": args.predictor_revision,
        "threshold": args.threshold,
        "window_size": args.window_size,
        "page_tokens": args.page_tokens,
        "context_repetitions": args.context_repetitions,
        "max_new_tokens": args.max_new_tokens,
        "seed": args.seed,
    }
    if any(config.get(key) != value for key, value in required.items()):
        raise ValueError("replay source configuration differs from component gate configuration")
    if config.get("resolved_target_layers") != [args.target_layer]:
        raise ValueError("A4.1.1 source must contain exactly the selected target layer")
    event_path = source_dir / source["event_file"]
    digest = sha256_file(event_path)
    if digest != source["event_file_sha256"]:
        raise ValueError("replay event source SHA-256 mismatch")
    events = load_replay_events(event_path)
    if set(events) != {args.target_layer}:
        raise ValueError("replay event layers differ from target layer")
    if sum(len(layer) for layer in events.values()) != source["event_count"]:
        raise ValueError("replay event count differs from source manifest")
    return events, source, digest


def schedule_runs(*, warmups: int, measured: int, seed: int, include_online_predictor_control: bool) -> list[tuple[str, int, bool]]:
    rng = random.Random(seed)
    schedule = []
    for warmup in (True, False):
        count = warmups if warmup else measured
        for repetition in range(count):
            paths = ["same_mask_dense_replay", "same_mask_route_a_replay"]
            if include_online_predictor_control:
                paths.append("online_dense_predictor_control")
            rng.shuffle(paths)
            schedule.extend((path, repetition, warmup) for path in paths)
    return schedule


def manifest_config(args: argparse.Namespace) -> dict[str, Any]:
    """Return an explicitly JSON-safe configuration without the output target."""
    return {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
        if key != "output_dir"
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens, args.max_executed_dtype_ulps, args.warmup_repetitions, args.measured_repetitions) <= 0 or args.target_layer < 0 or args.target_kv_head < 0 or args.window_size < 0:
        raise ValueError("invalid A4.1.1 component-gate dimensions")
    require_cuda_device(args.device)
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("component gate is currently bounded to frozen Qwen3-8B and official MLP revisions")
    events, source, event_sha256 = read_source(args.replay_source_dir, args=args)
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    config = manifest_config(args)
    config["replay_event_file_sha256"] = event_sha256
    initialize_output_directory(args.output_dir, config=config, git_commit=get_git_commit())
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    if args.target_layer >= len(language_model.layers):
        raise ValueError("target layer is outside the model")
    schedule = schedule_runs(warmups=args.warmup_repetitions, measured=args.measured_repetitions, seed=args.seed, include_online_predictor_control=args.include_online_predictor_control)
    raw_records: list[dict[str, Any]] = []
    outcomes = []
    for execution_order, (path, repetition, warmup) in enumerate(schedule):
        backend_type = DenseSameMaskAttentionBackendSet if path in {"same_mask_dense_replay", "online_dense_predictor_control"} else RouteAPolicyAttentionBackendSet
        recorder = CudaComponentRecorder(device=args.device, path=path, repetition=repetition, execution_order=execution_order, warmup=warmup, metadata={"target_layer": args.target_layer, "target_kv_head": args.target_kv_head, "admission_budget": args.admission_budget, "replay_event_file_sha256": event_sha256})
        online_control = path == "online_dense_predictor_control"
        backend = backend_type(pipe.model, KVzapPress(model_type="mlp", predictor_revision=args.predictor_revision) if online_control else None, layers=(args.target_layer,), kv_head=args.target_kv_head, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps, replay_mask_events=None if online_control else events, component_measure=recorder.measure)
        seed_everything(args.seed)
        with torch.no_grad(), backend:
            output = pipe(str(request["context"]), question=str(request["question"]), max_new_tokens=args.max_new_tokens, enable_thinking=False)
        assert_no_runtime_mask_state(pipe.model)
        backend.assert_replay_complete()
        if not backend.comparisons or backend.policy_decode_calls.get(args.target_layer, 0) <= 0:
            raise AssertionError(f"{path}: no complete target-layer component observation")
        if path == "same_mask_route_a_replay" and not any(int(row["pending_tokens"]) > 0 for row in backend.comparisons):
            raise AssertionError("Route-A component gate did not observe pending staging")
        raw_records.extend(recorder.records)
        outcomes.append({"path": path, "repetition": repetition, "execution_order": execution_order, "warmup": warmup, "answer_sha256": answer_hash(output), "policy_decode_calls": backend.policy_decode_calls, "policy_coverage": backend.coverage(), "component_record_count": len(recorder.records)})
    raw_path = write_raw_repetitions(args.output_dir, raw_records)
    summary = summarize_reported_repetitions(raw_records)
    summary.update({"raw_path": raw_path.name, "raw_record_count": len(raw_records), "run_outcomes": outcomes})
    manifest = {
        "schema_version": "kvzap-route-a411-component-gate-1.0",
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "request_id": request["request_id"],
        "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "replay_source": {"directory": str(args.replay_source_dir), "event_file_sha256": event_sha256, "source_manifest_sha256": sha256_file(args.replay_source_dir / "a41_replay_mask_source_manifest.json"), "event_count": source["event_count"], "source_answer_sha256": source["answer_sha256"]},
        "summary": summary,
        "source_artifact_sha256": source["source_artifact_sha256"],
        "observational_guards": {"paired_mask_mode": "replayed_dense_mask", "route_a_predictor_scored_online": False, "online_predictor_control_included": args.include_online_predictor_control, "replay_mask_consumption_complete": True, "fp32_same_mask_guard": {"rtol": args.rtol, "atol": args.atol}, "component_timer_synchronizes_each_component": True, "component_timer_not_end_to_end": True},
        "boundaries": ["This is an A4.1.1 single-layer/head component measurement. It excludes Full-KV and end-to-end decode timing; those belong to later gates.", "The two measured paths replay the exact same dense-source mask. Predictor scoring was intentionally excluded from this paired replay timing and must be measured separately as an online control.", "Allocator fields are PyTorch allocator observations, not HBM traffic. No result is throughput, energy, area, frequency, hardware acceleration, or RTL evidence."],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    path = args.output_dir / "a411_component_gate_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.1 component gate completed: {path}")


if __name__ == "__main__":
    main()
