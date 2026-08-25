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
from kvpress.admission_shadow import LayerBatchAdmissionShadow, PackedKVAdmissionShadow
from kvpress.lifecycle import ReadOnlyKVzapLifecycleObserver, language_model_layers
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, file_sha256, get_git_commit, stable_hash, validate_gate_a_evidence
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route-A3.5 read-only real-K/V admission shadow calibration; Full KV remains authoritative.")
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
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
    parser.add_argument("--submission-mode", choices=("per_head", "per_layer_batch"), default="per_head", help="A3.5b per_layer_batch times one layer/call envelope but does not claim a fused gather kernel.")
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
    shadow_class = PackedKVAdmissionShadow if args.submission_mode == "per_head" else LayerBatchAdmissionShadow
    print("Pass 1/3: normal Full-KV generation without observer...")
    normal = run_request(pipe, str(request["context"]), str(request["question"]), args.seed, args.max_new_tokens)
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
    manifest = {"schema_version": "kvzap-route-a35-admission-shadow-1.1", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config_hash": stable_hash(config), "config": config, "submission_mode": args.submission_mode, "model": args.model_name, "model_revision": model_revision, "predictor_checkpoint": args.predictor_name, "predictor_revision": args.predictor_revision, "request_id": request["request_id"], "gate_a_evidence": gate, "source_artifact_sha256": {"gate_a_manifest": file_sha256(args.gate_a_evidence / "manifest.json"), "gate_a_score_mask": file_sha256(args.gate_a_evidence / "score_mask.npz")}, "trace_equivalence": {"answers_identical": True, "answer_sha256": hashes[0], "lifecycle_digests_identical": True, "shadow_semantic_digests_identical": True, "shadow_semantic_digest": recorded_shadow.semantic_digest}, "shadow_summary": recorded_shadow.summary(), "observational_guards": {"full_kv_remains_authoritative": True, "dms_press_used": False, "model_cache_mutated_by_shadow": False, "sparse_attention_used": False}, "measurement_boundary": ["host_submit_us and CUDA event timing measure this reference implementation only, not end-to-end decode latency.", "per_layer_batch is a grouped reference submission envelope; its inner per-head gather/page writes are not a fused kernel.", "No field is an HBM/DRAM counter, allocator measurement, throughput result, or edge-hardware calibration."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    manifest_path = args.output_dir / "admission_shadow_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("A3.5 equivalence passed: Full-KV answers, lifecycle digest, and shadow semantic digest match.")
    for name, path in {**lifecycle_paths, **shadow_paths, "manifest": manifest_path}.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
