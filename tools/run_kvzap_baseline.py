# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run a small Full-KV versus KVzap baseline on Qwen3-8B."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import transformers
import yaml
from huggingface_hub import snapshot_download
from transformers import pipeline

from kvpress import DMSPress, KVzapPress


DEFAULT_MODEL = "Qwen/Qwen3-8B"
DEFAULT_PREDICTOR = "nvidia/KVzap-mlp-Qwen3-8B"
VARIANTS = ("full_kv", "kvzap_prefill", "kvzap_prefill_decoding")
RESULT_FIELDS = (
    "experiment_id",
    "config_hash",
    "request_id",
    "subset",
    "variant",
    "model",
    "predictor",
    "threshold",
    "window",
    "seed",
    "context_tokens",
    "question_tokens",
    "prompt_tokens",
    "generated_tokens_retokenized",
    "max_new_tokens",
    "answer",
    "required_substrings_json",
    "correct",
    "metric_value",
    "logical_removed_fraction",
    "logical_compression_factor",
    "layer_removed_fractions_json",
    "elapsed_ms_diagnostic",
)

ARTICLE_PARAGRAPH = """
Machine learning is a subset of artificial intelligence that builds systems
which learn from data. Deep learning has improved computer vision, natural
language processing, and speech recognition. Transformer models use attention
to process sequences and have achieved strong results on language tasks.
Efficient inference requires careful management of computation and memory.
""".strip()

SYSTEMS_PARAGRAPH = """
Large-language-model inference depends on GPU memory capacity, memory bandwidth,
matrix-multiplication throughput, and communication between accelerators. Model
weights, activations, and the key-value cache compete for memory. Quantization
can reduce weight storage and bandwidth, while batching changes arithmetic
intensity and latency. The best hardware choice therefore depends on model size,
context length, workload, latency target, and deployment scale.
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Full KV, KVzap prefill, and KVzap prefill+decoding on a few fixed requests."
    )
    parser.add_argument("--model-name", default=DEFAULT_MODEL, help="Base model Hugging Face ID.")
    parser.add_argument("--predictor-name", default=DEFAULT_PREDICTOR, help="KVzap predictor Hugging Face ID.")
    parser.add_argument("--threshold", type=float, default=-4.0, help="Drop scores strictly below this threshold.")
    parser.add_argument("--window-size", type=int, default=128, help="Number of newest tokens protected from pruning.")
    parser.add_argument("--seed", type=int, default=42, help="Seed reset before every request/variant run.")
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=VARIANTS,
        default=list(VARIANTS),
        help="Baseline variants to run.",
    )
    parser.add_argument(
        "--input-jsonl",
        type=Path,
        help="Optional request JSONL; built-in requests are used by default.",
    )
    parser.add_argument(
        "--context-repetitions",
        type=int,
        default=12,
        help="Repetitions used to construct each built-in long context.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        help="Optional override for every request's generation limit.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("analysis"), help="Directory for baseline artifacts.")
    parser.add_argument("--overwrite", action="store_true", help="Replace the three baseline artifacts if they exist.")
    return parser.parse_args()


def build_builtin_requests(context_repetitions: int) -> list[dict[str, Any]]:
    if context_repetitions < 2:
        raise ValueError("context_repetitions must be at least 2")

    article_blocks = [ARTICLE_PARAGRAPH] * context_repetitions
    article_blocks.insert(
        context_repetitions // 2,
        "The archival retrieval code for this experiment is ORCHID-7429.",
    )
    systems_context = "\n\n".join([SYSTEMS_PARAGRAPH] * context_repetitions)
    return [
        {
            "request_id": "builtin_retrieval_code",
            "subset": "retrieval",
            "context": "\n\n".join(article_blocks),
            "question": "What is the archival retrieval code? Answer with the code only.",
            "required_substrings": ["ORCHID-7429"],
            "max_new_tokens": 32,
        },
        {
            "request_id": "builtin_article_summary",
            "subset": "summarization",
            "context": "\n\n".join([ARTICLE_PARAGRAPH] * context_repetitions),
            "question": "Summarize the article in two sentences.",
            "required_substrings": ["machine learning", "attention"],
            "max_new_tokens": 96,
        },
        {
            "request_id": "builtin_long_hardware_answer",
            "subset": "long_generation",
            "context": systems_context,
            "question": (
                "Using the context, write a detailed answer of at least 180 words explaining which hardware "
                "characteristics matter for LLM inference. Include memory capacity, memory bandwidth, "
                "throughput, interconnects, batching, and quantization."
            ),
            "required_substrings": ["memory", "bandwidth", "quantization"],
            "max_new_tokens": 256,
        },
    ]


def load_requests(path: Path) -> list[dict[str, Any]]:
    requests = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            request = json.loads(line)
            missing = {"request_id", "context", "question"} - request.keys()
            if missing:
                raise ValueError(f"{path}:{line_number} missing required fields: {sorted(missing)}")
            request.setdefault("subset", "custom")
            request.setdefault("required_substrings", [])
            request.setdefault("max_new_tokens", 64)
            if not isinstance(request["required_substrings"], list):
                raise ValueError(f"{path}:{line_number} required_substrings must be a list")
            requests.append(request)
    if not requests:
        raise ValueError(f"No requests found in {path}")
    return requests


def score_required_substrings(answer: str, required_substrings: list[str]) -> tuple[bool | None, float | None]:
    if not required_substrings:
        return None, None
    answer_lower = answer.lower()
    matched = sum(required.lower() in answer_lower for required in required_substrings)
    metric_value = matched / len(required_substrings)
    return matched == len(required_substrings), metric_value


def removed_fraction_to_factor(removed_fraction: float) -> float:
    if not 0 <= removed_fraction < 1:
        raise ValueError(f"removed_fraction must be in [0, 1), got {removed_fraction}")
    return 1 / (1 - removed_fraction)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def get_git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def stable_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prepare_output_paths(output_dir: Path, overwrite: bool) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "config": output_dir / "baseline_config.yaml",
        "results": output_dir / "baseline_results.csv",
        "notes": output_dir / "reproduction_notes.md",
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing and not overwrite:
        joined = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"Baseline artifacts already exist: {joined}. Use --overwrite to replace them.")
    return paths


def make_press(variant: str, threshold: float, window_size: int) -> DMSPress | None:
    if variant == "full_kv":
        return None
    return DMSPress(
        press=KVzapPress(model_type="mlp"),
        threshold=threshold,
        sliding_window_size=window_size,
        decoding=variant == "kvzap_prefill_decoding",
    )


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(path)


def write_reproduction_notes(
    path: Path,
    config: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    lines = [
        "# KVzap baseline reproduction notes",
        "",
        f"- Experiment ID: `{config['experiment_id']}`",
        f"- Config hash: `{config['config_hash']}`",
        f"- Git commit: `{config['git_commit']}`",
        f"- Model: `{config['model']}`",
        f"- Predictor: `{config['predictor']}`",
        f"- Threshold/window: `{config['threshold']}` / `{config['sliding_window']}`",
        "- Decoding: greedy with Qwen thinking disabled.",
        "- Runtime is diagnostic only; the current fake-key DMS path does not provide physical KV compression.",
        (
            "- `generated_tokens_retokenized` is computed by tokenizing the decoded answer "
            "and may exclude EOS/special tokens."
        ),
        "",
        "## Variant summary",
        "",
    ]
    for variant in config["variants"]:
        variant_rows = [row for row in rows if row["variant"] == variant]
        if not variant_rows:
            continue
        mean_removed = sum(float(row["logical_removed_fraction"]) for row in variant_rows) / len(variant_rows)
        scored = [row for row in variant_rows if row["correct"] != ""]
        correct = sum(row["correct"] == "True" for row in scored)
        lines.append(
            f"- `{variant}`: requests={len(variant_rows)}, correct={correct}/{len(scored)}, "
            f"mean logical removed fraction={mean_removed:.4f}"
        )
    lines.extend(
        [
            "",
            "These built-in checks are smoke-level functional metrics, not official RULER/LongBench accuracy.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.window_size < 0:
        raise ValueError("--window-size must be non-negative")
    if args.max_new_tokens is not None and args.max_new_tokens <= 0:
        raise ValueError("--max-new-tokens must be positive")

    requests = load_requests(args.input_jsonl) if args.input_jsonl else build_builtin_requests(args.context_repetitions)
    if args.max_new_tokens is not None:
        for request in requests:
            request["max_new_tokens"] = args.max_new_tokens

    expected_predictor = f"nvidia/KVzap-mlp-{args.model_name.split('/')[-1]}"
    if args.predictor_name != expected_predictor:
        raise ValueError(
            f"KVzapPress derives {expected_predictor!r} from the base model; "
            f"--predictor-name was {args.predictor_name!r}."
        )

    paths = prepare_output_paths(args.output_dir, args.overwrite)
    predictor_snapshot = Path(snapshot_download(repo_id=args.predictor_name))
    predictor_revision = predictor_snapshot.name
    experiment_id = datetime.now(timezone.utc).strftime("kvzap-baseline-%Y%m%dT%H%M%SZ")
    config_for_hash = {
        "model": args.model_name,
        "predictor": args.predictor_name,
        "predictor_revision": predictor_revision,
        "predictor_type": "mlp",
        "threshold": args.threshold,
        "sliding_window": args.window_size,
        "variants": args.variants,
        "seed": args.seed,
        "thinking": False,
        "decoding": "greedy",
        "requests": [
            {
                "request_id": request["request_id"],
                "subset": request["subset"],
                "max_new_tokens": request["max_new_tokens"],
            }
            for request in requests
        ],
    }
    config = {
        "schema_version": "baseline-1.0",
        "experiment_id": experiment_id,
        "config_hash": stable_hash(config_for_hash),
        "git_commit": get_git_commit(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        **config_for_hash,
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }
    paths["config"].write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    print(f"Loading base model: {args.model_name}")
    pipe = pipeline(
        "kv-press-text-generation",
        model=args.model_name,
        device_map="auto",
        dtype="auto",
    )
    print("Base model loaded. Running deterministic baseline variants...")

    rows: list[dict[str, Any]] = []
    presses = {
        variant: make_press(variant, args.threshold, args.window_size)
        for variant in args.variants
    }
    for variant in args.variants:
        press = presses[variant]
        for request in requests:
            seed_everything(args.seed)
            tokenized = pipe.preprocess(
                request["context"],
                [request["question"]],
                answer_prefix="",
                max_context_length=pipe.tokenizer.model_max_length,
                enable_thinking=False,
            )
            context_tokens = int(tokenized["context_ids"].shape[1])
            question_tokens = int(tokenized["questions_ids"][0].shape[1])
            max_new_tokens = int(request["max_new_tokens"])

            if torch.cuda.is_available():
                torch.cuda.synchronize()
            start = time.perf_counter()
            output = pipe(
                request["context"],
                question=request["question"],
                press=press,
                max_new_tokens=max_new_tokens,
                enable_thinking=False,
            )
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            elapsed_ms = (time.perf_counter() - start) * 1000

            answer = output["answer"]
            generated_tokens = len(pipe.tokenizer.encode(answer, add_special_tokens=False))
            correct, metric_value = score_required_substrings(answer, request["required_substrings"])
            if press is None:
                removed_fraction = 0.0
                layer_ratios: dict[int, float] = {}
            else:
                removed_fraction = float(press.compression_ratio)
                layer_ratios = dict(sorted(press.compression_ratios.items()))

            row = {
                "experiment_id": experiment_id,
                "config_hash": config["config_hash"],
                "request_id": request["request_id"],
                "subset": request["subset"],
                "variant": variant,
                "model": args.model_name,
                "predictor": "" if press is None else args.predictor_name,
                "threshold": "" if press is None else args.threshold,
                "window": "" if press is None else args.window_size,
                "seed": args.seed,
                "context_tokens": context_tokens,
                "question_tokens": question_tokens,
                "prompt_tokens": context_tokens + question_tokens,
                "generated_tokens_retokenized": generated_tokens,
                "max_new_tokens": max_new_tokens,
                "answer": answer,
                "required_substrings_json": json.dumps(request["required_substrings"]),
                "correct": "" if correct is None else str(correct),
                "metric_value": "" if metric_value is None else metric_value,
                "logical_removed_fraction": removed_fraction,
                "logical_compression_factor": removed_fraction_to_factor(removed_fraction),
                "layer_removed_fractions_json": json.dumps(layer_ratios, sort_keys=True),
                "elapsed_ms_diagnostic": elapsed_ms,
            }
            rows.append(row)
            write_csv(rows, paths["results"])
            print(
                f"[{variant}] {request['request_id']}: correct={correct}, "
                f"removed={removed_fraction:.2%}, generated_tokens~={generated_tokens}"
            )

    write_reproduction_notes(paths["notes"], config, rows)
    print(f"Saved config: {paths['config']}")
    print(f"Saved results: {paths['results']}")
    print(f"Saved notes: {paths['notes']}")


if __name__ == "__main__":
    main()
