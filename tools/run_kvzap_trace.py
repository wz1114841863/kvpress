# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Export one correctness-checked KVzap score/mask trace on Qwen3-8B."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import transformers
from huggingface_hub import snapshot_download
from transformers import pipeline

from kvpress import DMSPress, KVzapPress
from kvpress.trace import KVzapTraceRecorder


DEFAULT_MODEL = "Qwen/Qwen3-8B"
DEFAULT_PREDICTOR = "nvidia/KVzap-mlp-Qwen3-8B"
PRESETS = ("hardware", "retrieval", "summarization", "reasoning")

SYSTEMS_PARAGRAPH = """
Large-language-model inference depends on GPU memory capacity, memory bandwidth,
matrix-multiplication throughput, and communication between accelerators. Model
weights, activations, and the key-value cache compete for memory. Quantization
can reduce weight storage and bandwidth, while batching changes arithmetic
intensity and latency. The best hardware choice therefore depends on model size,
context length, workload, latency target, and deployment scale.
""".strip()

HARDWARE_QUESTION = """
Using the context, write a detailed answer of at least 240 words explaining which
hardware characteristics matter for LLM inference. Discuss memory capacity,
memory bandwidth, compute throughput, interconnects, batching, quantization,
latency, and deployment scale. Finish with a concise recommendation.
""".strip()

ARTICLE_PARAGRAPH = """
Machine learning develops systems that learn patterns from data. Deep learning
has improved computer vision, natural-language processing, and speech
recognition. Transformer models use attention to process sequences, while
efficient inference requires careful management of computation, memory, and the
key-value cache. New pruning methods aim to reduce memory use without losing the
information needed to answer a request.
""".strip()

REASONING_PARAGRAPH = """
A deployment must serve a 64 GB language model and a 12 GB peak key-value cache.
Accelerator Atlas has 80 GB memory, 3.0 TB/s bandwidth, and costs 4 credits per
hour. Accelerator Borealis has 48 GB memory, 1.8 TB/s bandwidth, and costs 2
credits per hour. Two Borealis devices provide 96 GB total memory, but tensor
parallelism adds 20 percent communication overhead and requires splitting the
model across both devices. Quantization reduces the model to 40 GB and the KV
cache to 9 GB, while adding a 5 percent compute overhead. The service requires
the complete working set to fit in accelerator memory and prefers the lowest
cost configuration that satisfies capacity before comparing bandwidth.
""".strip()


def build_builtin_request(preset: str, context_repetitions: int) -> dict[str, Any]:
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset {preset!r}; choose from {PRESETS}")
    if context_repetitions < 2:
        raise ValueError("context_repetitions must be at least 2 for built-in requests")

    if preset == "hardware":
        return {
            "request_id": "builtin_hardware_trace",
            "dataset": "builtin",
            "subset": "long_generation",
            "context": "\n\n".join([SYSTEMS_PARAGRAPH] * context_repetitions),
            "question": HARDWARE_QUESTION,
        }
    if preset == "retrieval":
        blocks = [ARTICLE_PARAGRAPH] * context_repetitions
        blocks.insert(context_repetitions // 2, "The archival retrieval code is ORCHID-7429.")
        return {
            "request_id": "builtin_retrieval_trace",
            "dataset": "builtin",
            "subset": "retrieval",
            "context": "\n\n".join(blocks),
            "question": "What is the archival retrieval code? Answer with the code only.",
        }
    if preset == "summarization":
        return {
            "request_id": "builtin_summarization_trace",
            "dataset": "builtin",
            "subset": "summarization",
            "context": "\n\n".join([ARTICLE_PARAGRAPH] * context_repetitions),
            "question": (
                "Summarize the context in two concise paragraphs. Explain the role of transformers, "
                "attention, efficient inference, and KV-cache pruning."
            ),
        }
    return {
        "request_id": "builtin_reasoning_trace",
        "dataset": "builtin",
        "subset": "reasoning",
        "context": "\n\n".join([REASONING_PARAGRAPH] * context_repetitions),
        "question": (
            "Compare one Atlas, two unquantized Borealis devices, and one quantized Borealis device. "
            "Show the capacity and hourly-cost reasoning step by step, account for the stated overheads, "
            "and recommend the lowest-cost valid configuration in at least 180 words."
        ),
    }


def load_jsonl_request(path: Path, request_id: str | None) -> dict[str, Any]:
    requests = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            request = json.loads(line)
            missing = {"request_id", "context", "question"} - request.keys()
            if missing:
                raise ValueError(f"{path}:{line_number} missing required fields: {sorted(missing)}")
            request.setdefault("dataset", "custom")
            request.setdefault("subset", "custom")
            requests.append(request)
    if not requests:
        raise ValueError(f"No requests found in {path}")
    if request_id is not None:
        selected = [request for request in requests if request["request_id"] == request_id]
        if len(selected) != 1:
            raise ValueError(f"Expected exactly one request_id={request_id!r} in {path}, found {len(selected)}")
        return selected[0]
    if len(requests) != 1:
        raise ValueError(f"{path} contains {len(requests)} requests; select one with --request-id")
    return requests[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one request twice (trace off/on), verify identical output and KVzap masks, "
            "then export raw score, predicted mask, final mask, and decoding events."
        )
    )
    parser.add_argument("--model-name", default=DEFAULT_MODEL, help="Base model Hugging Face ID.")
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR, help="KVzap predictor Hugging Face ID.")
    parser.add_argument("--threshold", type=float, default=-4.0, help="Drop scores strictly below this threshold.")
    parser.add_argument("--window-size", type=int, default=128, help="Number of newest tokens protected from pruning.")
    parser.add_argument("--seed", type=int, default=42, help="Seed reset before each of the two runs.")
    parser.add_argument("--max-new-tokens", type=int, default=384, help="Greedy generation limit.")
    request_group = parser.add_mutually_exclusive_group()
    request_group.add_argument(
        "--preset",
        choices=PRESETS,
        default="hardware",
        help="Built-in request to trace; defaults to the original hardware-themed request.",
    )
    request_group.add_argument(
        "--input-jsonl",
        type=Path,
        help="Custom request JSONL. It must contain one request unless --request-id selects one.",
    )
    parser.add_argument(
        "--request-id",
        help="Select one request_id from --input-jsonl; invalid without --input-jsonl.",
    )
    parser.add_argument(
        "--context-repetitions",
        type=int,
        default=12,
        help="Number of context paragraph repetitions.",
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
        default=Path("traces/qwen3_8b_single"),
        help="New directory for the pilot trace; existing directories are never overwritten.",
    )
    return parser.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def get_git_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], check=False, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def stable_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def language_model_layers(model):
    language_model = model.model.language_model if hasattr(model.model, "language_model") else model.model
    return language_model.layers


def snapshot_masked_indices(model) -> list[tuple[torch.Tensor, torch.Tensor, torch.Tensor] | None]:
    snapshots = []
    for layer in language_model_layers(model):
        indices = getattr(layer.self_attn, "masked_key_indices", None)
        snapshots.append(None if indices is None else tuple(index.detach().cpu().clone() for index in indices))
    return snapshots


def assert_same_indices(
    expected: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor] | None],
    actual: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor] | None],
) -> None:
    if len(expected) != len(actual):
        raise AssertionError(f"Layer counts differ: {len(expected)} != {len(actual)}")
    for layer_idx, (left, right) in enumerate(zip(expected, actual)):
        if (left is None) != (right is None):
            raise AssertionError(f"Layer {layer_idx} has different masked-index presence")
        if left is not None and right is not None:
            if any(not torch.equal(left_item, right_item) for left_item, right_item in zip(left, right)):
                raise AssertionError(f"Layer {layer_idx} masked indices differ with tracing enabled")


def assert_trace_matches_indices(
    final_drop_mask: np.ndarray,
    masked_indices: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor] | None],
) -> None:
    if final_drop_mask.shape[0] != len(masked_indices):
        raise AssertionError("Trace and model have different layer counts")
    for layer_idx, indices in enumerate(masked_indices):
        traced = np.argwhere(final_drop_mask[layer_idx])
        if indices is None:
            expected = np.empty((0, 2), dtype=np.int64)
        else:
            batch, head, token = (item.numpy() for item in indices)
            if np.any(batch != 0):
                raise AssertionError("Pilot trace only supports batch index zero")
            expected = np.stack([head, token], axis=1)
        traced = traced[np.lexsort((traced[:, 1], traced[:, 0]))] if len(traced) else traced
        expected = expected[np.lexsort((expected[:, 1], expected[:, 0]))] if len(expected) else expected
        if not np.array_equal(traced, expected):
            raise AssertionError(f"Layer {layer_idx} final trace mask differs from masked_key_indices")


def run_request(
    pipe,
    press: DMSPress,
    context: str,
    question: str,
    seed: int,
    max_new_tokens: int,
) -> dict[str, Any]:
    seed_everything(seed)
    return pipe(
        context,
        question=question,
        press=press,
        max_new_tokens=max_new_tokens,
        enable_thinking=False,
    )


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Trace directory already exists: {args.output_dir}")
    if args.window_size < 0:
        raise ValueError("--window-size must be non-negative")
    if args.max_new_tokens <= 0 or args.context_repetitions <= 0:
        raise ValueError("--max-new-tokens and --context-repetitions must be positive")
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
    context_tokens = int(tokenized["context_ids"].shape[1])
    question_tokens = int(tokenized["questions_ids"][0].shape[1])
    if context_tokens + question_tokens <= args.window_size:
        raise ValueError("Prompt does not exceed the protected window; increase --context-repetitions")

    press = DMSPress(
        press=KVzapPress(model_type="mlp"),
        threshold=args.threshold,
        sliding_window_size=args.window_size,
        decoding=True,
    )
    print(f"Request: {request_id} ({dataset}/{subset})")
    print("Pass 1/2: tracing disabled...")
    untraced_output = run_request(pipe, press, context, question, args.seed, args.max_new_tokens)
    untraced_ratios = dict(press.compression_ratios)
    untraced_indices = snapshot_masked_indices(pipe.model)

    recorder = KVzapTraceRecorder(request_id, args.near_threshold_epsilon)
    press.trace_callback = recorder
    print("Pass 2/2: tracing enabled (diagnostic CPU copies are expected)...")
    traced_output = run_request(pipe, press, context, question, args.seed, args.max_new_tokens)
    traced_ratios = dict(press.compression_ratios)
    traced_indices = snapshot_masked_indices(pipe.model)

    if untraced_output["answer"] != traced_output["answer"]:
        raise AssertionError("Generated answer changed with tracing enabled; no trace was written")
    if untraced_ratios != traced_ratios:
        raise AssertionError("Per-layer compression ratios changed with tracing enabled; no trace was written")
    assert_same_indices(untraced_indices, traced_indices)
    arrays = recorder.validate(args.window_size)
    assert_trace_matches_indices(arrays["final_drop_mask"], traced_indices)

    generated_tokens = len(pipe.tokenizer.encode(traced_output["answer"], add_special_tokens=False))
    config_for_hash = {
        "model": args.model_name,
        "predictor": args.predictor_name,
        "predictor_revision": predictor_revision,
        "predictor_type": "mlp",
        "threshold": args.threshold,
        "sliding_window": args.window_size,
        "seed": args.seed,
        "max_new_tokens": args.max_new_tokens,
        "request_source": "jsonl" if args.input_jsonl is not None else f"preset:{args.preset}",
        "context_repetitions": None if args.input_jsonl is not None else args.context_repetitions,
        "near_threshold_epsilon": args.near_threshold_epsilon,
        "thinking": False,
        "decoding": True,
        "request_id": request_id,
        "dataset": dataset,
        "subset": subset,
        "request_content_hash": stable_hash({"context": context, "question": question}),
    }
    manifest = {
        "experiment_id": datetime.now(timezone.utc).strftime("kvzap-trace-%Y%m%dT%H%M%SZ"),
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
        "decoding_enabled": True,
        "trace_equivalence_verified": True,
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
        "generated_tokens_retokenized": generated_tokens,
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
    answers_path = args.output_dir / "answer.json"
    answers_path.write_text(
        json.dumps(
            {
                "request_id": request_id,
                "trace_off_answer": untraced_output["answer"],
                "trace_on_answer": traced_output["answer"],
                "identical": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Trace equivalence verified: answer, per-layer ratios, and masked indices are identical.")
    print(f"Logical removed fraction: {press.compression_ratio:.2%}")
    for name, path in {**paths, "answer": answers_path}.items():
        print(f"  {name}: {path} ({path.stat().st_size / 1024**2:.2f} MiB)")
    print("These files describe logical masks only; they do not demonstrate physical KV-memory reduction or speedup.")


if __name__ == "__main__":
    main()
