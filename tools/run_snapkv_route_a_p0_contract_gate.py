#!/usr/bin/env python3
"""Collect a read-only SnapKV prefill terminal-decision source for Route-A P0."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import DynamicCache, pipeline

from kvpress import SnapKVPress
from kvpress.route_a_frontend_contract import (
    FRONTEND_DECISION_STREAM_SCHEMA,
    SnapKVPrefillDecisionObserver,
    sha256_file,
    validate_snapkv_p0_contract,
    write_frontend_decision_stream,
)
from tools.export_kvzap_predictor_trace import GATE_B_MODEL_REVISION, get_git_commit, stable_hash
from tools.run_kvzap_trace import DEFAULT_MODEL, PRESETS, build_builtin_request, load_jsonl_request, seed_everything


P0_SCHEMA = "route-a-snapkv-p0-contract-gate-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only SnapKV P0 terminal-decision collector; no cache replacement, timing, or hardware claim."
    )
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="summarization")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--model-name", default=DEFAULT_MODEL)
    parser.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    parser.add_argument("--compression-ratio", type=float, default=0.5)
    parser.add_argument("--window-size", type=int, default=64)
    parser.add_argument("--kernel-size", type=int, default=5)
    parser.add_argument("--target-layers", nargs="+", default=["all"], help="Layer indices, or exactly 'all'.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-new-tokens", type=int, default=1, help="Only drives the normal pipeline prefill; P0 records prefill terminal decisions only.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def resolve_layers(values: list[str], layer_count: int) -> tuple[int, ...]:
    if values == ["all"]:
        return tuple(range(layer_count))
    if "all" in values:
        raise ValueError("--target-layers all cannot be combined with explicit layers")
    try:
        layers = tuple(int(value) for value in values)
    except ValueError as error:
        raise ValueError("--target-layers must contain non-negative indices or exactly 'all'") from error
    if not layers or len(set(layers)) != len(layers) or any(not 0 <= layer < layer_count for layer in layers):
        raise ValueError(f"--target-layers must be unique indices in [0,{layer_count})")
    return layers


def answer_hash(output: dict[str, Any]) -> str:
    return hashlib.sha256(str(output["answer"]).encode("utf-8")).hexdigest()


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if not 0.0 <= args.compression_ratio < 1.0 or min(args.window_size, args.kernel_size, args.context_repetitions, args.max_new_tokens) <= 0:
        raise ValueError("invalid SnapKV P0 dimensions")
    if (args.model_name, args.model_revision) != (DEFAULT_MODEL, GATE_B_MODEL_REVISION):
        raise ValueError("SnapKV P0 is initially bounded to the frozen Qwen3-8B model revision")
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    if getattr(pipe.model.config, "_commit_hash", None) != args.model_revision:
        raise ValueError("loaded model revision differs from the declared revision")
    language_model = pipe.model.model.language_model if hasattr(pipe.model.model, "language_model") else pipe.model.model
    layers = resolve_layers(args.target_layers, len(language_model.layers))
    press = SnapKVPress(
        compression_ratio=args.compression_ratio,
        window_size=args.window_size,
        kernel_size=args.kernel_size,
    )
    print("Pass 1/2: dense trace-off prefill/generation control...")
    seed_everything(args.seed)
    trace_off_output = pipe(
        str(request["context"]),
        question=str(request["question"]),
        cache=DynamicCache(),
        max_new_tokens=args.max_new_tokens,
        enable_thinking=False,
    )
    print(f"Pass 2/2: dense prefill with read-only SnapKV terminal-decision observer in layers {list(layers)}...")
    seed_everything(args.seed)
    cache = DynamicCache()
    with torch.no_grad(), SnapKVPrefillDecisionObserver(
        pipe.model,
        press,
        request_id=str(request["request_id"]),
        target_layers=layers,
    ) as observer:
        output = pipe(
            str(request["context"]),
            question=str(request["question"]),
            cache=cache,
            max_new_tokens=args.max_new_tokens,
            enable_thinking=False,
        )
    if answer_hash(trace_off_output) != answer_hash(output):
        raise AssertionError("SnapKV P0 trace-on answer differs from the trace-off dense control")
    decisions = observer.decisions()
    contract = validate_snapkv_p0_contract(
        decisions,
        window_size=args.window_size,
        compression_ratio=args.compression_ratio,
    )
    config = {key: value for key, value in vars(args).items() if key != "output_dir"}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    stream_path = args.output_dir / "snapkv_prefill_terminal_decisions.npz"
    stream_sha256 = write_frontend_decision_stream(stream_path, decisions)
    manifest = {
        "schema_version": P0_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "request_id": request["request_id"],
        "request_content_hash": stable_hash({"context": request["context"], "question": request["question"]}),
        "trace_off_answer_sha256": answer_hash(trace_off_output),
        "trace_on_answer_sha256": answer_hash(output),
        "trace_off_on_answer_match": True,
        "decision_stream_schema": FRONTEND_DECISION_STREAM_SCHEMA,
        "decision_stream_file": stream_path.name,
        "decision_stream_sha256": stream_sha256,
        "decision_stream_event_count": len(decisions),
        "contract": contract,
        "source_sha256": {
            "snapkv_press": sha256_file(Path("kvpress/presses/snapkv_press.py")),
            "scorer_press": sha256_file(Path("kvpress/presses/scorer_press.py")),
            "frontend_contract": sha256_file(Path("kvpress/route_a_frontend_contract.py")),
        },
        "boundaries": [
            "P0 observes one dense Qwen3-8B prefill and never installs SnapKV's cache-replacing compression hook.",
            "The decision stream records terminal layer/KV-head/original-position keep/drop actions and scalar scores only; it contains no token text, K/V tensors, pending queue, or packed-page state.",
            "SnapKV's score-ranked native gather order is not reused as Route-A identity order; this artifact stores the same selected set canonically by original position.",
            "This is functional/trace-derived frontend evidence, not HBM traffic, allocator behavior, latency, throughput, energy, area, hardware, architecture specification, or RTL evidence.",
        ],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    (args.output_dir / "snapkv_p0_contract_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"SnapKV P0 terminal-decision source collected: {args.output_dir}")


if __name__ == "__main__":
    main()
