"""Collect a read-only Route-A2 KVzap decode-lifecycle trace for one request."""

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
from kvpress.lifecycle import ReadOnlyKVzapLifecycleObserver
from tools.export_kvzap_predictor_trace import (
    GATE_A_PREDICTOR_REVISION,
    GATE_B_MODEL_REVISION,
    assert_no_runtime_mask_state,
    file_sha256,
    get_git_commit,
    stable_hash,
    validate_gate_a_evidence,
)
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route-A2 read-only KVzap decode-lifecycle collector; no DMS or cache mutation.")
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
    parser.add_argument("--max-new-tokens", type=int, default=32, help="Use a small first probe; this collector runs three equivalent passes.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; existing directories are never overwritten.")
    return parser.parse_args()


def answer_hash(output: dict[str, Any]) -> str:
    return hashlib.sha256(str(output["answer"]).encode("utf-8")).hexdigest()


def answer_retokenized_length(pipe, output: dict[str, Any]) -> int:
    """Diagnostic only: token count after decoding then re-tokenizing text."""
    return len(pipe.tokenizer.encode(str(output["answer"]), add_special_tokens=False))


def run_request(pipe, context: str, question: str, seed: int, max_new_tokens: int) -> dict[str, Any]:
    seed_everything(seed)
    return pipe(context, question=question, max_new_tokens=max_new_tokens, enable_thinking=False)


def run_observer(pipe, observer: ReadOnlyKVzapLifecycleObserver, context: str, question: str, seed: int, max_new_tokens: int) -> dict[str, Any]:
    seed_everything(seed)
    with torch.no_grad(), observer:
        output = pipe(context, question=question, max_new_tokens=max_new_tokens, enable_thinking=False)
    assert_no_runtime_mask_state(pipe.model)
    return output


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.kv_bytes_per_token, args.max_new_tokens) <= 0 or args.window_size < 0 or args.metadata_bytes_per_page < 0:
        raise ValueError("invalid lifecycle collection dimensions or byte assumptions")
    if args.model_name != DEFAULT_MODEL or args.predictor_name != DEFAULT_PREDICTOR:
        raise ValueError("Route-A2 is currently bounded to the frozen Qwen3-8B official MLP predictor")
    if args.model_revision != GATE_B_MODEL_REVISION or args.predictor_revision != GATE_A_PREDICTOR_REVISION:
        raise ValueError("Route-A2 requires the frozen model and predictor revisions")
    gate = validate_gate_a_evidence(args.gate_a_evidence, model_name=args.model_name, predictor_name=args.predictor_name, threshold=args.threshold, window_size=args.window_size)
    if not gate["passed"]:
        failed = [key for key, passed in gate["checks"].items() if not passed]
        raise ValueError(f"Frozen Gate-A evidence failed validation: {failed}")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    predictor_snapshot = Path(snapshot_download(repo_id=args.predictor_name, revision=args.predictor_revision))
    if predictor_snapshot.name != args.predictor_revision:
        raise ValueError("Resolved predictor snapshot does not match the frozen predictor revision")
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    model_revision = getattr(pipe.model.config, "_commit_hash", None)
    if model_revision != args.model_revision:
        raise ValueError(f"Loaded model revision {model_revision!r} differs from requested {args.model_revision!r}")
    tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
    context_tokens = int(tokenized["context_ids"].shape[1])
    if context_tokens <= args.window_size:
        raise ValueError("Context does not exceed the protected hot window")
    common = dict(request_id=str(request["request_id"]), threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, kv_bytes_per_token=args.kv_bytes_per_token, metadata_bytes_per_page=args.metadata_bytes_per_page)
    print("Pass 1/3: normal generation with no press and no observer...")
    normal = run_request(pipe, str(request["context"]), str(request["question"]), args.seed, args.max_new_tokens)
    assert_no_runtime_mask_state(pipe.model)
    print("Pass 2/3: read-only lifecycle observer without event serialization...")
    silent = ReadOnlyKVzapLifecycleObserver(
        pipe.model, KVzapPress(model_type="mlp", predictor_revision=args.predictor_revision), record_events=False, **common
    )
    silent_output = run_observer(pipe, silent, str(request["context"]), str(request["question"]), args.seed, args.max_new_tokens)
    print("Pass 3/3: read-only lifecycle observer with event serialization...")
    recorded = ReadOnlyKVzapLifecycleObserver(
        pipe.model, KVzapPress(model_type="mlp", predictor_revision=args.predictor_revision), record_events=True, **common
    )
    recorded_output = run_observer(pipe, recorded, str(request["context"]), str(request["question"]), args.seed, args.max_new_tokens)
    hashes = [answer_hash(output) for output in (normal, silent_output, recorded_output)]
    if len(set(hashes)) != 1:
        raise AssertionError("Answer changed across normal, observer-no-record, and observer-record runs; no trace was written")
    if silent.lifecycle_digest != recorded.lifecycle_digest:
        raise AssertionError("Lifecycle mask/event digest changed when serialization was enabled; no trace was written")
    silent_summary, recorded_summary = silent.summary(), recorded.summary()
    if silent_summary != recorded_summary:
        raise AssertionError("Lifecycle summary changed when serialization was enabled; no trace was written")
    paths = recorded.write(args.output_dir)
    config = {"model": args.model_name, "model_revision": model_revision, "predictor": args.predictor_name, "predictor_revision": args.predictor_revision, "threshold": args.threshold, "sliding_window": args.window_size, "page_tokens": args.page_tokens, "kv_bytes_per_token": args.kv_bytes_per_token, "metadata_bytes_per_page": args.metadata_bytes_per_page, "seed": args.seed, "max_new_tokens": args.max_new_tokens, "request_id": request["request_id"], "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]})}
    manifest = {"schema_version": "kvzap-route-a2-readonly-lifecycle-1.0", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config_hash": stable_hash(config), "model": args.model_name, "model_revision": model_revision, "predictor_checkpoint": args.predictor_name, "predictor_revision": args.predictor_revision, "threshold": args.threshold, "sliding_window": args.window_size, "page_tokens": args.page_tokens, "kv_bytes_per_layer_head_token": args.kv_bytes_per_token, "metadata_bytes_per_cold_page": args.metadata_bytes_per_page, "request_id": request["request_id"], "dataset": request["dataset"], "subset": request["subset"], "context_tokens": context_tokens, "max_new_tokens": args.max_new_tokens, "decode_lifecycle_observation": {**recorded_summary, "answer_retokenized_token_count": answer_retokenized_length(pipe, recorded_output), "answer_retokenized_token_count_definition": "tokenizer.encode(decoded answer text, add_special_tokens=False); this can differ from generated token ids", "pipeline_generated_token_ids_observed_definition": "1 + observed q_len=1 decode calls under KVPress greedy generation; the first prompt/question forward produces the first generated token"}, "trace_equivalence": {"normal_observer_record_answer_sha256": hashes[0], "answers_identical": True, "observer_no_record_lifecycle_digest": silent.lifecycle_digest, "observer_record_lifecycle_digest": recorded.lifecycle_digest, "lifecycle_digests_identical": True, "observer_no_record_summary": silent_summary, "observer_record_summary": recorded_summary, "lifecycle_summaries_identical": True}, "gate_a_evidence": gate, "observational_guards": {"dms_press_used": False, "masked_key_indices_created": False, "fake_key_attention_used": False, "model_cache_mutated_by_collector": False}, "source_artifact_sha256": {"gate_a_manifest": file_sha256(args.gate_a_evidence / "manifest.json"), "gate_a_score_mask": file_sha256(args.gate_a_evidence / "score_mask.npz")}, "notes": ["This is a read-only predictor observation during normal dense-KV generation; it does not apply KVzap/DMS pruning to attention.", "Lifecycle page/admission fields are declared Route-A accounting events, not allocator or HBM-counter measurements.", "No output in this directory establishes accuracy beyond trace-off/on equality, physical memory, HBM traffic, latency, throughput, or admission break-even."], "config": config, "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    manifest_path = args.output_dir / "lifecycle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("A2 equivalence passed: normal/observer answers and no-record/record lifecycle digests match.")
    for name, path in {**paths, "manifest": manifest_path}.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
