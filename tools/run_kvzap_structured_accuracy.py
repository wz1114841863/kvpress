"""Run a gated, prefill-only KVzap structured-mask accuracy screening."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Running ``python tools/<script>.py`` otherwise places ``tools/`` before the
# repository root on sys.path.  Some research environments also have another
# editable ``kvpress`` installed (for example FocusKV's vendored checkout).
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from transformers import pipeline  # noqa: E402

from kvpress import DMSPress, KVzapPress, make_margin_block_drop_transform  # noqa: E402


VARIANTS = ("full_kv", "kvzap_original", "b4_m0", "b4_m025")
QA_TASKS = {"narrativeqa", "qasper", "2wikimqa", "musique"}


def normalize(text: str) -> list[str]:
    return re.sub(r"\b(a|an|the)\b", " ", re.sub(r"[^\w\s]", " ", text.lower())).split()


def f1(prediction: str, reference: str) -> float:
    left, right = normalize(prediction), normalize(reference)
    if not left or not right:
        return float(left == right)
    common = sum((__import__("collections").Counter(left) & __import__("collections").Counter(right)).values())
    return 2 * common / (len(left) + len(right))


def rouge_l(prediction: str, reference: str) -> float:
    left, right = prediction.split(), reference.split()
    if not left or not right:
        return float(left == right)
    previous = [0] * (len(right) + 1)
    for token in left:
        current = [0]
        for index, other in enumerate(right, start=1):
            current.append(previous[index - 1] + 1 if token == other else max(previous[index], current[-1]))
        previous = current
    lcs = previous[-1]
    return 2 * lcs / (len(left) + len(right))


def metric(task: str, answer: str, references: list[str]) -> tuple[str, float]:
    scorer = f1 if task in QA_TASKS else rouge_l
    name = "qa_f1" if task in QA_TASKS else "rouge_l"
    return name, max(scorer(answer, reference) for reference in references)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        raise ValueError("Accuracy input JSONL is empty")
    for row in rows:
        if {"request_id", "context", "question", "answers", "task"} - row.keys():
            raise ValueError(f"Malformed accuracy input: {row.get('request_id')}")
    return rows


def make_press(variant: str, threshold: float, window: int, callback):
    if variant == "full_kv":
        return None
    transform = None
    if variant == "b4_m0":
        transform = make_margin_block_drop_transform(4, 0.0)
    if variant == "b4_m025":
        transform = make_margin_block_drop_transform(4, 0.25)
    return DMSPress(
        KVzapPress(model_type="mlp"),
        threshold=threshold,
        sliding_window_size=window,
        decoding=False,
        trace_callback=callback,
        drop_mask_transform=transform,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Actual-generation B=4 KVzap accuracy screening.")
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--max-requests", type=int, default=1)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--threshold", type=float, default=-4.0)
    parser.add_argument("--window", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", default="Qwen/Qwen3-8B")
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output exists: {args.output_dir}")
    rows = load_rows(args.input_jsonl)[: args.max_requests]
    source = json.loads(args.input_manifest.read_text(encoding="utf-8"))
    if hashlib.sha256(args.input_jsonl.read_bytes()).hexdigest() != source["output_jsonl_sha256"]:
        raise ValueError("Input JSONL hash differs from manifest")
    args.output_dir.mkdir(parents=True)
    result_path = args.output_dir / "request_results.csv"
    results = []
    for variant in args.variants:
        print(f"Loading isolated base model for variant: {variant}")
        pipe = pipeline("kv-press-text-generation", model=args.model, device_map="auto", dtype="auto")
        for row in rows:
            observed = []

            def callback(**event):
                observed.append(event)

            press = make_press(variant, args.threshold, args.window, callback)
            seed_everything(args.seed)
            output = pipe(
                row["context"],
                question=row["question"],
                press=press,
                enable_thinking=False,
                max_new_tokens=args.max_new_tokens,
            )
            answer = output["answer"]
            metric_name, score = metric(row["task"], answer, row["answers"])
            gate = variant == "full_kv" or (len(observed) == 36 and all(event["prefilling"] for event in observed))
            if press is not None and variant.startswith("b4_"):
                transform = make_margin_block_drop_transform(4, 0.0 if variant == "b4_m0" else 0.25)
                gate = gate and all(
                    torch.equal(
                        event["matured_drop_mask"],
                        transform(event["matured_scores"], args.threshold, event["matured_start"]),
                    )
                    for event in observed
                )
            results.append(
                {
                    "request_id": row["request_id"],
                    "task": row["task"],
                    "variant": variant,
                    "metric_name": metric_name,
                    "metric_value": score,
                    "answer": answer,
                    "mask_gate_pass": gate,
                    "logical_removed_fraction": 0.0 if press is None else press.compression_ratio,
                }
            )
            print(f"[{variant}] {row['request_id']}: {metric_name}={score:.4f}, mask_gate={gate}")
            if not gate:
                raise AssertionError("Mask gate failed; refusing to continue")
        del pipe
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    with result_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    config = {
        "schema_version": "kvzap-structured-accuracy-1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_manifest": str(args.input_manifest),
        "input_manifest_sha256": hashlib.sha256(args.input_manifest.read_bytes()).hexdigest(),
        "input_jsonl_sha256": source["output_jsonl_sha256"],
        "variants": args.variants,
        "max_requests": args.max_requests,
        "max_new_tokens": args.max_new_tokens,
        "threshold": args.threshold,
        "window": args.window,
        "seed": args.seed,
        "notes": [
            "Prefill-only DMS; actual fake-key masking applies during question/generation attention.",
            "F1 and whitespace-token ROUGE-L are screening metrics; reproduce official LongBench "
            "metrics separately for publication.",
        ],
    }
    (args.output_dir / "run_manifest.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Saved results: {result_path}")


if __name__ == "__main__":
    main()
