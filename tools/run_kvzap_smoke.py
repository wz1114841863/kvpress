# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run a small, reproducible KVzap smoke test with the official Qwen3-8B MLP predictor."""

import argparse
import json
from pathlib import Path

from huggingface_hub import snapshot_download
from transformers import pipeline

from kvpress import DMSPress, KVzapPress


DEFAULT_MODEL = "Qwen/Qwen3-8B"
DEFAULT_PREDICTOR = "nvidia/KVzap-mlp-Qwen3-8B"

ARTICLE_PARAGRAPH = """
Machine learning is a subset of artificial intelligence that focuses on building
systems that learn from data. Recent advances in deep learning have improved
computer vision, natural language processing, and speech recognition.
Transformer models have achieved strong performance on many language tasks.
This article introduces an efficient attention method intended to reduce
computation and memory use while maintaining model quality.
""".strip()

DECODING_PROMPT = """
Explain which hardware characteristics matter most for LLM inference. Discuss
GPU memory capacity, memory bandwidth, tensor-core throughput, interconnect
bandwidth, batch size, and model quantization. Give a detailed answer with a
short conclusion.
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download/verify the official KVzap MLP predictor and run a small "
            "Qwen3-8B prefill or prefill+decoding smoke test."
        )
    )
    parser.add_argument("--model-name", default=DEFAULT_MODEL, help="Base model Hugging Face ID.")
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR, help="KVzap predictor Hugging Face ID.")
    parser.add_argument("--threshold", type=float, default=-4.0, help="Drop scores strictly below this threshold.")
    parser.add_argument("--window-size", type=int, default=128, help="Number of newest tokens protected from pruning.")
    parser.add_argument(
        "--mode",
        choices=("prefill", "prefill-decoding", "both"),
        default="prefill",
        help="Smoke-test phase(s) to run.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=256,
        help="Generation limit for prefill+decoding mode; use >128 to exercise decoding maturity.",
    )
    parser.add_argument(
        "--prefill-max-new-tokens",
        type=int,
        default=64,
        help="Generation limit for the prefill-only question answer.",
    )
    parser.add_argument(
        "--context-repetitions",
        type=int,
        default=12,
        help="Repeat the sample paragraph so the prefill context exceeds the protected window.",
    )
    parser.add_argument(
        "--enable-thinking",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable Qwen3 thinking for prefill+decoding mode.",
    )
    return parser.parse_args()


def download_and_check_predictor(predictor_name: str) -> Path:
    snapshot_path = Path(snapshot_download(repo_id=predictor_name))
    config_path = snapshot_path / "config.json"
    with config_path.open(encoding="utf-8") as stream:
        config = json.load(stream)

    expected = {
        "model_type": "kvzap",
        "input_dim": 4096,
        "hidden_dim": 512,
        "output_dim": 8,
        "n_modules": 36,
    }
    mismatches = {key: (config.get(key), value) for key, value in expected.items() if config.get(key) != value}
    if mismatches:
        raise RuntimeError(f"Unexpected Qwen3-8B KVzap predictor config: {mismatches}")

    print(f"Predictor snapshot ready: {snapshot_path}")
    print(
        "Predictor config: "
        f"layers={config['n_modules']}, input_dim={config['input_dim']}, "
        f"hidden_dim={config['hidden_dim']}, kv_heads={config['output_dim']}"
    )
    return snapshot_path


def make_press(args: argparse.Namespace, *, decoding: bool) -> DMSPress:
    model_type = "mlp"
    expected_name = f"nvidia/KVzap-{model_type}-{args.model_name.split('/')[-1]}"
    if args.predictor_name != expected_name:
        raise ValueError(
            "KVzapPress derives its predictor ID from the base model name. "
            f"For {args.model_name!r}, the current implementation expects {expected_name!r}, "
            f"not {args.predictor_name!r}."
        )
    return DMSPress(
        press=KVzapPress(model_type=model_type),
        threshold=args.threshold,
        sliding_window_size=args.window_size,
        decoding=decoding,
    )


def print_compression(press: DMSPress) -> None:
    ratios = sorted(press.compression_ratios.items())
    if not ratios:
        raise RuntimeError("KVzap did not record any per-layer compression ratios.")

    values = [ratio for _, ratio in ratios]
    print(f"Logical removed fraction (layer mean): {press.compression_ratio:.2%}")
    print(f"Per-layer removed fraction range: {min(values):.2%} .. {max(values):.2%}")
    print("Per-layer removed fractions:")
    print("  " + ", ".join(f"L{layer_idx}={ratio:.2%}" for layer_idx, ratio in ratios))
    if press.compression_ratio == 0:
        print("WARNING: no KV positions were masked; check token count, window size, and threshold.")


def run_prefill(pipe, args: argparse.Namespace) -> None:
    press = make_press(args, decoding=False)
    context = "\n\n".join([ARTICLE_PARAGRAPH] * args.context_repetitions)
    question = "\nWhat is this article about in two sentences?"
    tokenized = pipe.preprocess(
        context,
        [question],
        answer_prefix="",
        max_context_length=pipe.tokenizer.model_max_length,
        enable_thinking=False,
    )
    context_tokens = tokenized["context_ids"].shape[1]
    if context_tokens <= args.window_size:
        raise ValueError(
            f"Prefill context has {context_tokens} tokens, which does not exceed "
            f"the protected window ({args.window_size}). Increase --context-repetitions."
        )

    print(f"\nRunning prefill-only KVzap with {context_tokens} context tokens...")
    result = pipe(
        context,
        question=question,
        press=press,
        max_new_tokens=args.prefill_max_new_tokens,
        enable_thinking=False,
    )
    print(f"Loaded predictor ID: {press.press.kvzap_model_name}")
    print_compression(press)
    print(f"Answer: {result['answer']}")


def run_prefill_decoding(pipe, args: argparse.Namespace) -> None:
    if args.max_new_tokens <= args.window_size:
        print(
            "WARNING: --max-new-tokens does not exceed the protected window; "
            "decoding-time pruning may not be exercised."
        )

    press = make_press(args, decoding=True)
    print("\nRunning prefill+decoding KVzap...")
    result = pipe(
        DECODING_PROMPT,
        press=press,
        enable_thinking=args.enable_thinking,
        max_new_tokens=args.max_new_tokens,
    )
    print(f"Loaded predictor ID: {press.press.kvzap_model_name}")
    print_compression(press)
    print(f"Answer: {result['answer']}")


def main() -> None:
    args = parse_args()
    if args.window_size < 0:
        raise ValueError("--window-size must be non-negative.")
    if args.context_repetitions < 1:
        raise ValueError("--context-repetitions must be positive.")

    download_and_check_predictor(args.predictor_name)

    print(f"Loading base model: {args.model_name}")
    pipe = pipeline(
        "kv-press-text-generation",
        model=args.model_name,
        device_map="auto",
        dtype="auto",
    )
    print("Base model loaded successfully. The predictor loads on the first KVzap model call.")

    if args.mode in ("prefill", "both"):
        run_prefill(pipe, args)
    if args.mode in ("prefill-decoding", "both"):
        run_prefill_decoding(pipe, args)


if __name__ == "__main__":
    main()
