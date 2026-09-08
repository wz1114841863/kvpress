"""Collect one untimed online dense-KVzap mask source for A4.1 replay."""

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
from kvpress.route_a_policy_backend import DenseSameMaskAttentionBackendSet
from kvpress.route_a_replay import REPLAY_SOURCE_SCHEMA, write_replay_events
from tools.export_kvzap_predictor_trace import GATE_A_PREDICTOR_REVISION, GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, file_sha256, get_git_commit, stable_hash, validate_gate_a_evidence
from tools.run_kvzap_trace import DEFAULT_MODEL, DEFAULT_PREDICTOR, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1 replay-mask collector: one untimed online dense KVzap pass; no performance claim.")
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
    parser.add_argument("--admission-budget", type=int, default=512, help="Recorded for paired Route-A compatibility; dense source has no admission service.")
    parser.add_argument("--target-layers", nargs="+", default=["0"], help="One or more layer indices, or exactly 'all'.")
    parser.add_argument("--require-all-kv-heads", action="store_true", help="Reject the source unless every selected layer records exactly its configured KV-head IDs.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--max-executed-dtype-ulps", type=float, default=16.0)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def answer_hash(output: dict[str, Any]) -> str:
    return hashlib.sha256(str(output["answer"]).encode("utf-8")).hexdigest()


def resolve_layers(values: list[str], layer_count: int) -> tuple[int, ...]:
    if values == ["all"]:
        return tuple(range(layer_count))
    if "all" in values:
        raise ValueError("--target-layers all cannot be combined with explicit layers")
    try:
        layers = tuple(int(value) for value in values)
    except ValueError as error:
        raise ValueError("--target-layers must contain non-negative integers or exactly 'all'") from error
    if not layers or len(set(layers)) != len(layers) or any(not 0 <= layer < layer_count for layer in layers):
        raise ValueError(f"--target-layers must be unique indices in [0,{layer_count})")
    return layers


def replay_event_coverage(*, events: dict[int, dict[tuple[int, int], tuple[bool, float]]], expected_heads: dict[int, tuple[int, ...]], window_size: int) -> dict[str, Any]:
    """Summarize score/mask event coverage without treating it as Route-A state."""
    if window_size < 0:
        raise ValueError("window_size must be non-negative")
    rows = []
    for layer, heads in sorted(expected_heads.items()):
        layer_events = events.get(layer)
        if layer_events is None:
            raise AssertionError(f"replay source lacks selected layer {layer}")
        observed_heads = tuple(sorted({int(head) for head, _position in layer_events}))
        unexpected = sorted(set(observed_heads) - set(heads))
        missing = sorted(set(heads) - set(observed_heads))
        per_head = []
        for head in heads:
            head_events = [(int(position), bool(keep)) for (event_head, position), (keep, _score) in layer_events.items() if event_head == head]
            per_head.append({
                "kv_head": int(head),
                "event_count": len(head_events),
                "keep_count": sum(keep for _position, keep in head_events),
                "keep_at_or_after_hot_window_count": sum(keep and position >= window_size for position, keep in head_events),
                "max_cache_position": max((position for position, _keep in head_events), default=None),
            })
        rows.append({"layer": int(layer), "expected_kv_heads": list(heads), "observed_kv_heads": list(observed_heads), "missing_kv_heads": missing, "unexpected_kv_heads": unexpected, "event_count": len(layer_events), "per_head": per_head})
    return {"layer_count": len(rows), "layers": rows}


def assert_all_kv_heads_covered(coverage: dict[str, Any]) -> None:
    failures = [{"layer": row["layer"], "missing": row["missing_kv_heads"], "unexpected": row["unexpected_kv_heads"]} for row in coverage["layers"] if row["missing_kv_heads"] or row["unexpected_kv_heads"]]
    if failures:
        raise AssertionError(f"replay source KV-head coverage differs from selected model configuration: {failures}")


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if min(args.context_repetitions, args.page_tokens, args.admission_budget, args.max_new_tokens, args.max_executed_dtype_ulps) <= 0 or args.window_size < 0:
        raise ValueError("invalid replay-source dimensions")
    if args.max_new_tokens < 2:
        raise ValueError("max-new-tokens must be at least 2")
    if (args.model_name, args.predictor_name, args.model_revision, args.predictor_revision) != (DEFAULT_MODEL, DEFAULT_PREDICTOR, GATE_B_MODEL_REVISION, GATE_A_PREDICTOR_REVISION):
        raise ValueError("replay collector is currently bounded to frozen Qwen3-8B and official MLP revisions")
    gate_a = validate_gate_a_evidence(args.gate_a_evidence, model_name=args.model_name, predictor_name=args.predictor_name, threshold=args.threshold, window_size=args.window_size)
    if not gate_a["passed"]:
        raise ValueError("frozen Gate-A evidence validation failed")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    predictor_snapshot = Path(snapshot_download(repo_id=args.predictor_name, revision=args.predictor_revision))
    if predictor_snapshot.name != args.predictor_revision:
        raise ValueError("resolved predictor snapshot differs from frozen revision")
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from frozen revision")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    layers = resolve_layers(args.target_layers, len(language_model.layers))
    args.resolved_target_layers = list(layers)
    expected_heads = {layer: tuple(range(int(language_model.layers[layer].self_attn.config.num_key_value_heads))) for layer in layers}
    args.resolved_target_kv_heads_by_layer = {str(layer): list(heads) for layer, heads in expected_heads.items()}
    print(f"Collecting untimed online dense KVzap replay source in layers {list(layers)}...")
    backend = DenseSameMaskAttentionBackendSet(pipe.model, KVzapPress(model_type="mlp", predictor_revision=args.predictor_revision), layers=layers, kv_head=None, threshold=args.threshold, window=args.window_size, page_tokens=args.page_tokens, admission_budget=args.admission_budget, rtol=args.rtol, atol=args.atol, max_executed_dtype_ulps=args.max_executed_dtype_ulps)
    seed_everything(args.seed)
    with torch.no_grad(), backend:
        output = pipe(str(request["context"]), question=str(request["question"]), max_new_tokens=args.max_new_tokens, enable_thinking=False)
    assert_no_runtime_mask_state(pipe.model)
    if not backend.comparisons or not all(count > 0 for count in backend.policy_decode_calls.values()):
        raise AssertionError("no complete dense replay-source comparison was observed")
    coverage = backend.coverage()
    if set(backend.mask_events()) != set(layers):
        raise AssertionError("collector did not record every selected layer")
    event_coverage = replay_event_coverage(events=backend.mask_events(), expected_heads=expected_heads, window_size=args.window_size)
    if args.require_all_kv_heads:
        assert_all_kv_heads_covered(event_coverage)
    config = {key: value for key, value in vars(args).items() if key not in {"output_dir", "gate_a_evidence"}}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    event_path = args.output_dir / "replay_mask_events.npz"
    event_sha256 = write_replay_events(event_path, backend.mask_events())
    manifest = {
        "schema_version": REPLAY_SOURCE_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "request_id": request["request_id"],
        "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "answer_sha256": answer_hash(output),
        "policy_decode_call_count_by_layer": backend.policy_decode_calls,
        "policy_coverage": coverage,
        "replay_event_coverage": event_coverage,
        "event_file": event_path.name,
        "event_file_sha256": event_sha256,
        "event_count": sum(len(events) for events in backend.mask_events().values()),
        "source_artifact_sha256": {"gate_a_manifest": file_sha256(args.gate_a_evidence / "manifest.json"), "gate_a_score_mask": file_sha256(args.gate_a_evidence / "score_mask.npz")},
        "boundaries": ["This is one untimed online dense-KVzap replay-mask collection, not a paired runtime measurement.", "The NPZ contains layer, KV-head, cache position, score, and keep events only; no token text or K/V tensors.", "Event coverage reports predictor-mask events only; it does not establish Route-A pending/packed state, physical memory, or performance.", "It is not timing, allocator, HBM, throughput, energy, area, frequency, or RTL evidence."],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    path = args.output_dir / "a41_replay_mask_source_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1 replay-mask source collected: {path}")


if __name__ == "__main__":
    main()
