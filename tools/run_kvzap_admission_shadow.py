"""Run Route-A3.5 read-only admission shadow calibration for one small request."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from huggingface_hub import snapshot_download
from transformers import pipeline

from kvpress import KVzapPress
from kvpress.admission_shadow import CalibratedAdmissionShadow, LayerBatchAdmissionShadow, PackedKVAdmissionShadow
from kvpress.lifecycle import ReadOnlyKVzapLifecycleObserver, language_model_layers
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, file_sha256, get_git_commit, stable_hash, validate_gate_a_evidence
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route-A3.5 read-only real-K/V admission shadow calibration; Full KV remains authoritative.")
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--expected-a2-lifecycle-dir", type=Path, help="Optional frozen A2 directory. Verify request content/config before running and Full-KV answer hash after running.")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--model-name", default=DEFAULT_MODEL)
    parser.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR)
    parser.add_argument("--predictor-revision", default=GATE_A_PREDICTOR_REVISION)
    parser.add_argument("--gate-a-evidence", type=Path, default=Path("traces/hardware_predictor_gate_a_01"))
    parser.add_argument("--threshold", type=float, default=-4.0)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--page-tokens", type=int, default=64)
    parser.add_argument("--kv-bytes-per-token", type=int, default=512)
    parser.add_argument("--metadata-bytes-per-page", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-new-tokens", type=int, default=8, help="Small probe only: this runs normal, silent shadow, and recorded shadow passes.")
    parser.add_argument("--submission-mode", choices=("per_head", "per_layer_batch", "per_head_v2", "per_layer_batch_v2"), default="per_head", help="A3.5b-V2 modes use a common planning/submit timing boundary; batch modes do not claim fused gather kernels.")
    parser.add_argument("--deferred-admission-decode-steps", type=int, default=0, help="A3.5b-V2 only: queue retained mature positions and flush at observed decode step N+1.")
    parser.add_argument("--admission-flush-token-budget", type=int, help="A3.5c only: maximum retained tokens physically packed per (model_call, layer); oldest positions drain first.")
    parser.add_argument("--record-hybrid-head-progress", action="store_true", help="A3.6 collection: emit untimed per-layer/head FIFO progress for offline hybrid dense+packed read DSE. Requires budgeted per_layer_batch_v2 mode.")
    parser.add_argument("--record-deferred-replay-positions", action="store_true", help="A3.10 collection: additionally emit every retained mature token position for exact branch-dependent oldest-first FIFO replay. Requires --record-hybrid-head-progress; output can be large.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory only; existing directories are never overwritten.")
    return parser.parse_args()


def answer_hash(output: dict[str, Any]) -> str:
    return hashlib.sha256(str(output["answer"]).encode("utf-8")).hexdigest()


def run_request(pipe, context: str, question: str, seed: int, max_new_tokens: int) -> dict[str, Any]:
    seed_everything(seed)
    return pipe(context, question=question, max_new_tokens=max_new_tokens, enable_thinking=False)


def run_shadow(pipe, observer: ReadOnlyKVzapLifecycleObserver, shadow: PackedKVAdmissionShadow, context: str, question: str, seed: int, max_new_tokens: int) -> dict[str, Any]:
    seed_everything(seed)
    with torch.no_grad(), observer:
        output = pipe(context, question=question, max_new_tokens=max_new_tokens, enable_thinking=False)
    shadow.finalize()
    assert_no_runtime_mask_state(pipe.model)
    return output


def validate_expected_a2(path: Path, args: argparse.Namespace, request: dict[str, Any]) -> str:
    manifest_path = path / "lifecycle_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("expected A2 directory lacks lifecycle_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a2-readonly-lifecycle-1.0":
        raise ValueError("expected A2 manifest schema is unsupported")
    expected_hash = stable_hash({"context": request["context"], "question": request["question"]})
    config = manifest.get("config", {})
    if config.get("request_content_hash") != expected_hash:
        raise ValueError("input request content does not match expected frozen A2 lifecycle")
    checks = {
        "request_id": str(request["request_id"]) == str(manifest.get("request_id")),
        "model": args.model_name == manifest.get("model"),
        "model_revision": args.model_revision == manifest.get("model_revision"),
        "predictor": args.predictor_name == manifest.get("predictor_checkpoint"),
        "predictor_revision": args.predictor_revision == manifest.get("predictor_revision"),
        "threshold": args.threshold == float(manifest.get("threshold")),
        "window": args.window_size == int(manifest.get("sliding_window")),
        "page_tokens": args.page_tokens == int(manifest.get("page_tokens")),
        "kv_bytes": args.kv_bytes_per_token == int(manifest.get("kv_bytes_per_layer_head_token")),
        "max_new_tokens": args.max_new_tokens == int(manifest.get("max_new_tokens")),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"A3.5 request/config differs from expected frozen A2 fields: {failed}")
    answer = manifest.get("trace_equivalence", {}).get("normal_observer_record_answer_sha256")
    if not answer:
        raise ValueError("expected A2 manifest lacks normal Full-KV answer hash")
    return str(answer)


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.kv_bytes_per_token, args.max_new_tokens) <= 0 or args.window_size < 0 or args.metadata_bytes_per_page < 0:
        raise ValueError("invalid A3.5 shadow dimensions")
    if args.model_name != DEFAULT_MODEL or args.predictor_name != DEFAULT_PREDICTOR or args.model_revision != GATE_B_MODEL_REVISION or args.predictor_revision != GATE_A_PREDICTOR_REVISION:
        raise ValueError("A3.5 is currently bounded to the frozen Qwen3-8B official MLP predictor revisions")
    gate = validate_gate_a_evidence(args.gate_a_evidence, model_name=args.model_name, predictor_name=args.predictor_name, threshold=args.threshold, window_size=args.window_size)
    if not gate["passed"]:
        raise ValueError("Frozen Gate-A evidence failed validation")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    expected_a2_answer = validate_expected_a2(args.expected_a2_lifecycle_dir, args, request) if args.expected_a2_lifecycle_dir else None
    predictor_snapshot = Path(snapshot_download(repo_id=args.predictor_name, revision=args.predictor_revision))
    if predictor_snapshot.name != args.predictor_revision:
        raise ValueError("Resolved predictor snapshot does not match the frozen revision")
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    model_revision = getattr(pipe.model.config, "_commit_hash", None)
    if model_revision != args.model_revision:
        raise ValueError("Loaded model revision differs from frozen request")
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    if int(tokenized["context_ids"].shape[1]) <= args.window_size:
        raise ValueError("Context does not exceed protected hot window")
    layers = len(language_model_layers(pipe.model))
    common = dict(request_id=str(request["request_id"]), threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, kv_bytes_per_token=args.kv_bytes_per_token, metadata_bytes_per_page=args.metadata_bytes_per_page)
    shadow_args = dict(request_id=str(request["request_id"]), layers=layers, heads=int(pipe.model.config.num_key_value_heads), window=args.window_size, page_tokens=args.page_tokens, expected_kv_bytes_per_token=args.kv_bytes_per_token)
    if args.deferred_admission_decode_steps < 0 or args.admission_flush_token_budget is not None and args.admission_flush_token_budget <= 0:
        raise ValueError("deferred steps and admission flush budget must be non-negative/positive")
    if args.submission_mode in {"per_head", "per_layer_batch"} and (args.deferred_admission_decode_steps or args.admission_flush_token_budget is not None):
        raise ValueError("deferred steps and admission flush budget require an A3.5b-V2 submission mode")
    if args.record_hybrid_head_progress and (args.submission_mode != "per_layer_batch_v2" or args.admission_flush_token_budget is None):
        raise ValueError("--record-hybrid-head-progress requires budgeted --submission-mode per_layer_batch_v2")
    if args.record_deferred_replay_positions and not args.record_hybrid_head_progress:
        raise ValueError("--record-deferred-replay-positions requires --record-hybrid-head-progress")
    shadow_class = PackedKVAdmissionShadow if args.submission_mode == "per_head" else LayerBatchAdmissionShadow if args.submission_mode == "per_layer_batch" else CalibratedAdmissionShadow
    if shadow_class is CalibratedAdmissionShadow:
        shadow_args.update(submission_mode=args.submission_mode, deferred_decode_steps=args.deferred_admission_decode_steps, admission_flush_token_budget=args.admission_flush_token_budget, record_hybrid_head_progress=args.record_hybrid_head_progress, record_deferred_replay_positions=args.record_deferred_replay_positions)
    print("Pass 1/3: normal Full-KV generation without observer...")
    normal = run_request(pipe, str(request["context"]), str(request["question"]), args.seed, args.max_new_tokens)
    if expected_a2_answer is not None and answer_hash(normal) != expected_a2_answer:
        raise AssertionError("normal Full-KV answer differs from the expected frozen A2 lifecycle; no shadow run was written")
    print("Pass 2/3: silent read-only lifecycle plus shadow packing...")
    silent_shadow = shadow_class(record_tasks=False, **shadow_args)
    silent_observer = ReadOnlyKVzapLifecycleObserver(pipe.model, KVzapPress(model_type="mlp", predictor_revision=args.predictor_revision), record_events=False, admission_sink=silent_shadow, **common)
    silent = run_shadow(pipe, silent_observer, silent_shadow, str(request["context"]), str(request["question"]), args.seed, args.max_new_tokens)
    print("Pass 3/3: recorded read-only lifecycle plus shadow packing...")
    recorded_shadow = shadow_class(record_tasks=True, **shadow_args)
    recorded_observer = ReadOnlyKVzapLifecycleObserver(pipe.model, KVzapPress(model_type="mlp", predictor_revision=args.predictor_revision), record_events=True, admission_sink=recorded_shadow, **common)
    recorded = run_shadow(pipe, recorded_observer, recorded_shadow, str(request["context"]), str(request["question"]), args.seed, args.max_new_tokens)
    hashes = [answer_hash(item) for item in (normal, silent, recorded)]
    if len(set(hashes)) != 1 or silent_observer.lifecycle_digest != recorded_observer.lifecycle_digest or silent_shadow.semantic_digest != recorded_shadow.semantic_digest:
        raise AssertionError("A3.5 equivalence failed; no output was written")
    # Keep the A2 writer's non-overwrite contract: it atomically establishes
    # the fresh output directory only after all three equivalence gates pass.
    # Creating it here would make recorded_observer.write() reject its own
    # output directory.
    lifecycle_paths = recorded_observer.write(args.output_dir)
    shadow_paths = recorded_shadow.write(args.output_dir)
    config = {"model": args.model_name, "model_revision": model_revision, "predictor": args.predictor_name, "predictor_revision": args.predictor_revision, "threshold": args.threshold, "sliding_window": args.window_size, "page_tokens": args.page_tokens, "kv_bytes_per_layer_head_token": args.kv_bytes_per_token, "metadata_bytes_per_cold_page": args.metadata_bytes_per_page, "seed": args.seed, "max_new_tokens": args.max_new_tokens, "request_id": request["request_id"]}
    schema = "kvzap-route-a35-admission-shadow-1.5" if args.record_deferred_replay_positions else "kvzap-route-a35-admission-shadow-1.4" if args.record_hybrid_head_progress else "kvzap-route-a35-admission-shadow-1.3" if args.admission_flush_token_budget is not None else "kvzap-route-a35-admission-shadow-1.2" if args.submission_mode.endswith("_v2") else "kvzap-route-a35-admission-shadow-1.1"
    manifest = {"schema_version": schema, "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config_hash": stable_hash(config), "config": config, "submission_mode": args.submission_mode, "deferred_admission_decode_steps": args.deferred_admission_decode_steps, "admission_flush_token_budget": args.admission_flush_token_budget if args.admission_flush_token_budget is not None else "unbounded", "record_hybrid_head_progress": args.record_hybrid_head_progress, "record_deferred_replay_positions": args.record_deferred_replay_positions, "expected_a2_lifecycle_dir": str(args.expected_a2_lifecycle_dir) if args.expected_a2_lifecycle_dir else None, "model": args.model_name, "model_revision": model_revision, "predictor_checkpoint": args.predictor_name, "predictor_revision": args.predictor_revision, "request_id": request["request_id"], "gate_a_evidence": gate, "source_artifact_sha256": {"gate_a_manifest": file_sha256(args.gate_a_evidence / "manifest.json"), "gate_a_score_mask": file_sha256(args.gate_a_evidence / "score_mask.npz")}, "trace_equivalence": {"answers_identical": True, "answer_sha256": hashes[0], "expected_a2_answer_sha256": expected_a2_answer, "expected_a2_answer_matches": expected_a2_answer is None or hashes[0] == expected_a2_answer, "lifecycle_digests_identical": True, "shadow_semantic_digests_identical": True, "shadow_semantic_digest": recorded_shadow.semantic_digest}, "shadow_summary": recorded_shadow.summary(), "observational_guards": {"full_kv_remains_authoritative": True, "dms_press_used": False, "model_cache_mutated_by_shadow": False, "sparse_attention_used": False}, "measurement_boundary": ["planning_host_us, submit_host_us, and gpu_envelope_ms measure this reference implementation only, not end-to-end decode latency.", "A budgeted flush limits retained tokens per layer/call but does not execute sparse attention or establish policy-on generation equivalence.", "Per-head FIFO progress is trace evidence only; it does not execute hybrid sparse attention or establish its generation equivalence.", "Deferred-replay positions preserve retained token order for an offline branch-dependent FIFO model; they do not execute sparse attention or establish its generation equivalence.", "No field is an HBM/DRAM counter, allocator measurement, throughput result, or edge-hardware calibration."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    manifest_path = args.output_dir / "admission_shadow_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("A3.5 equivalence passed: Full-KV answers, lifecycle digest, and shadow semantic digest match.")
    for name, path in {**lifecycle_paths, **shadow_paths, "manifest": manifest_path}.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
