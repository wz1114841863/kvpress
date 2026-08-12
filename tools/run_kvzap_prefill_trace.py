# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Export one KVzap predictor trace from a single prefill forward pass."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import transformers
from huggingface_hub import snapshot_download
from transformers import DynamicCache, pipeline

from kvpress import DMSPress, KVzapPress
from kvpress.trace import KVzapTraceRecorder
from tools.run_kvzap_trace import (
    DEFAULT_MODEL,
    DEFAULT_PREDICTOR,
    PRESETS,
    assert_trace_matches_indices,
    build_builtin_request,
    get_git_commit,
    load_jsonl_request,
    seed_everything,
    snapshot_masked_indices,
    stable_hash,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run exactly one context prefill with KVzap tracing enabled. This command does not generate tokens "
            "and therefore does not enter KVPress's decoding fake-key masking path."
        )
    )
    parser.add_argument("--model-name", default=DEFAULT_MODEL, help="Base model Hugging Face ID.")
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR, help="KVzap predictor Hugging Face ID.")
    parser.add_argument("--threshold", type=float, default=-4.0, help="Drop scores strictly below this threshold.")
    parser.add_argument("--window-size", type=int, default=128, help="Newest context tokens protected from pruning.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for the single prefill pass.")
    request_group = parser.add_mutually_exclusive_group()
    request_group.add_argument(
        "--preset",
        choices=PRESETS,
        default="hardware",
        help="Built-in request whose context is traced.",
    )
    request_group.add_argument(
        "--input-jsonl",
        type=Path,
        help="Custom request JSONL. It must contain one request unless --request-id selects one.",
    )
    parser.add_argument("--request-id", help="Select one request_id from --input-jsonl.")
    parser.add_argument(
        "--context-repetitions",
        type=int,
        default=12,
        help="Number of context paragraph repetitions for a built-in request.",
    )
    parser.add_argument(
        "--near-threshold-epsilon",
        type=float,
        default=0.25,
        help="Absolute score margin counted as near the threshold in summaries.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("traces/qwen3_8b_prefill_single"),
        help="New output directory; existing directories are never overwritten.",
    )
    return parser.parse_args()


def language_model_layer_count(model) -> int:
    language_model = model.model.language_model if hasattr(model.model, "language_model") else model.model
    return len(language_model.layers)


def validate_prefill_recorder(
    recorder: KVzapTraceRecorder,
    *,
    expected_layers: int,
    context_tokens: int,
    sliding_window: int,
) -> dict[str, np.ndarray]:
    """Require one and only one prefill event for every language-model layer."""
    if not recorder.events:
        raise AssertionError("The prefill forward pass produced no trace events")
    non_prefill = [event for event in recorder.events if event["phase"] != "prefill"]
    if non_prefill:
        raise AssertionError("Prefill-only trace unexpectedly contains decode events")
    layer_counts = Counter(int(event["layer"]) for event in recorder.events)
    expected_counts = {layer: 1 for layer in range(expected_layers)}
    if dict(layer_counts) != expected_counts:
        raise AssertionError(f"Expected one prefill event per layer, got {dict(sorted(layer_counts.items()))}")
    arrays = recorder.validate(sliding_window)
    if tuple(arrays["shape"]) != (expected_layers, recorder.events[0]["scores"].shape[0], context_tokens):
        raise AssertionError(
            f"Trace shape {tuple(arrays['shape'])} does not cover all {expected_layers} layers "
            f"and {context_tokens} context tokens"
        )
    return arrays


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Trace directory already exists: {args.output_dir}")
    if args.window_size < 0:
        raise ValueError("--window-size must be non-negative")
    if args.context_repetitions <= 0:
        raise ValueError("--context-repetitions must be positive")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id can only be used with --input-jsonl")

    request = (
        load_jsonl_request(args.input_jsonl, args.request_id)
        if args.input_jsonl is not None
        else build_builtin_request(args.preset, args.context_repetitions)
    )
    context = str(request["context"])
    question = str(request["question"])
    request_id = str(request["request_id"])
    dataset = str(request["dataset"])
    subset = str(request["subset"])

    expected_predictor = f"nvidia/KVzap-mlp-{args.model_name.split('/')[-1]}"
    if args.predictor_name != expected_predictor:
        raise ValueError(
            f"KVzapPress derives {expected_predictor!r} from the model; got {args.predictor_name!r}."
        )

    predictor_snapshot = Path(snapshot_download(repo_id=args.predictor_name))
    predictor_revision = predictor_snapshot.name
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, device_map="auto", dtype="auto")
    tokenized = pipe.preprocess(
        context,
        [question],
        answer_prefix="",
        max_context_length=pipe.tokenizer.model_max_length,
        enable_thinking=False,
    )
    context_ids = tokenized["context_ids"]
    question_ids = tokenized["questions_ids"][0]
    context_tokens = int(context_ids.shape[1])
    question_tokens = int(question_ids.shape[1])
    if context_tokens <= args.window_size:
        raise ValueError("Context does not exceed the protected window; increase --context-repetitions")

    recorder = KVzapTraceRecorder(request_id, args.near_threshold_epsilon)
    press = DMSPress(
        press=KVzapPress(model_type="mlp"),
        threshold=args.threshold,
        sliding_window_size=args.window_size,
        decoding=False,
        trace_callback=recorder,
    )
    cache = DynamicCache()
    seed_everything(args.seed)
    print(f"Request: {request_id} ({dataset}/{subset})")
    print(f"Running one prefill-only forward pass with {context_tokens} context tokens...")
    with torch.inference_mode(), press(pipe.model):
        pipe.model.model(
            input_ids=context_ids.to(pipe.model.device),
            past_key_values=cache,
            use_cache=True,
        )

    expected_layers = language_model_layer_count(pipe.model)
    arrays = validate_prefill_recorder(
        recorder,
        expected_layers=expected_layers,
        context_tokens=context_tokens,
        sliding_window=args.window_size,
    )
    masked_indices = snapshot_masked_indices(pipe.model)
    assert_trace_matches_indices(arrays["final_drop_mask"], masked_indices)

    request_source = "jsonl" if args.input_jsonl is not None else f"preset:{args.preset}"
    config_for_hash = {
        "model": args.model_name,
        "predictor": args.predictor_name,
        "predictor_revision": predictor_revision,
        "predictor_type": "mlp",
        "threshold": args.threshold,
        "sliding_window": args.window_size,
        "seed": args.seed,
        "request_source": request_source,
        "context_repetitions": None if args.input_jsonl is not None else args.context_repetitions,
        "near_threshold_epsilon": args.near_threshold_epsilon,
        "thinking": False,
        "decoding": False,
        "generation": False,
        "request_id": request_id,
        "dataset": dataset,
        "subset": subset,
        "request_content_hash": stable_hash({"context": context, "question": question}),
    }
    manifest = {
        "experiment_id": datetime.now(timezone.utc).strftime("kvzap-prefill-trace-%Y%m%dT%H%M%SZ"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config_hash": stable_hash(config_for_hash),
        "model": args.model_name,
        "predictor": "mlp",
        "predictor_checkpoint": args.predictor_name,
        "predictor_revision": predictor_revision,
        "dataset": dataset,
        "subset": subset,
        "threshold": args.threshold,
        "sliding_window": args.window_size,
        "dtype": str(next(pipe.model.parameters()).dtype),
        "seed": args.seed,
        "pruning_timing": "after_attention",
        "capture_scope": "context_prefill_only",
        "decoding_enabled": False,
        "generation_performed": False,
        "trace_equivalence_verified": None,
        "trace_equivalence_status": "not_applicable_single_observational_pass",
        "physical_compression_measured": False,
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
        "cuda_available": bool(torch.cuda.is_available()),
        "gpu": str(torch.cuda.get_device_name(0)) if torch.cuda.is_available() else None,
        "config": config_for_hash,
    }
    request_metadata = {
        "dataset": dataset,
        "subset": subset,
        "prompt_tokens": context_tokens + question_tokens,
        "context_tokens_scored": context_tokens,
        "question_tokens_not_scored": question_tokens,
        "generated_tokens_retokenized": 0,
        "threshold": args.threshold,
        "window": args.window_size,
        "seed": args.seed,
    }
    paths = recorder.write(
        args.output_dir,
        manifest=manifest,
        request_metadata=request_metadata,
        sliding_window=args.window_size,
    )
    token_ids_path = args.output_dir / "token_ids.npz"
    np.savez_compressed(
        token_ids_path,
        context_token_ids=context_ids.detach().cpu().numpy().astype(np.int64, copy=False),
        question_token_ids=question_ids.detach().cpu().numpy().astype(np.int64, copy=False),
    )
    run_metadata_path = args.output_dir / "run_metadata.json"
    run_metadata_path.write_text(
        json.dumps(
            {
                "request_id": request_id,
                "generation_performed": False,
                "answer": None,
                "note": "Scores and masks cover context prefill only; the question was tokenized for metadata only.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Prefill trace validated against DMS masked indices; no decoding or generation was executed.")
    print(f"Logical removed fraction: {press.compression_ratio:.2%}")
    for name, path in {**paths, "token_ids": token_ids_path, "run_metadata": run_metadata_path}.items():
        print(f"  {name}: {path} ({path.stat().st_size / 1024**2:.2f} MiB)")
    print("These files describe logical prefill masks only, not answer quality, physical memory reduction, or speedup.")


if __name__ == "__main__":
    main()
