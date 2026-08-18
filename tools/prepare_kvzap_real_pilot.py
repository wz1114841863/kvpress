# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Prepare a deterministic, length-stratified real-data JSONL pilot for predictor-only tracing."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from datasets import load_dataset
from huggingface_hub import HfApi
from transformers import AutoTokenizer


DEFAULT_REPO = "Xnhyacinth/LongBench"
DEFAULT_MODEL = "Qwen/Qwen3-8B"
DEFAULT_MODEL_REVISION = "b968826d9c46dd6066d109eabc6255188de91218"
DEFAULT_TASK_SPECS = (
    "retrieval:narrativeqa",
    "retrieval:qasper",
    "summarization:gov_report",
    "summarization:qmsum",
    "summarization:multi_news",
    "reasoning:2wikimqa",
    "reasoning:musique",
)
DEFAULT_LENGTH_BINS = ("1024:4096", "4096:8192", "8192:16384")
PILOT_SCHEMA = "kvzap-real-pilot-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download the repository-supported processed LongBench dataset, count context tokens with the "
            "target tokenizer, and select a deterministic category/length-stratified predictor-trace pilot."
        )
    )
    parser.add_argument("--dataset-repo", default=DEFAULT_REPO, help="Processed Hugging Face dataset repository.")
    parser.add_argument("--dataset-revision", default="main", help="Dataset revision to resolve and freeze.")
    parser.add_argument("--split", default="test", help="Dataset split.")
    parser.add_argument("--model-name", default=DEFAULT_MODEL, help="Tokenizer used for length stratification.")
    parser.add_argument(
        "--model-revision",
        default=DEFAULT_MODEL_REVISION,
        help="Frozen model/tokenizer revision validated by Gate B.",
    )
    parser.add_argument(
        "--task-spec",
        action="append",
        dest="task_specs",
        help="Repeat category:dataset_config. Defaults to seven retrieval/summarization/reasoning tasks.",
    )
    parser.add_argument(
        "--length-bin",
        action="append",
        dest="length_bins",
        help="Repeat lower:upper for a half-open context-token interval. Defaults: 1024:4096, 4096:8192, 8192:16384.",
    )
    parser.add_argument(
        "--samples-per-bucket",
        type=int,
        default=2,
        help="Samples selected for every category x length bucket (default yields up to 18 requests).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic selection seed.")
    parser.add_argument(
        "--strict-buckets",
        action="store_true",
        help="Fail instead of recording a shortfall when a category/length bucket has too few unique contexts.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=Path("pilot_inputs/longbench_core_v1.jsonl"),
        help="Ignored raw-text JSONL consumed by the batch trace runner.",
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=Path("pilot_inputs/longbench_core_v1.manifest.json"),
        help="Preparation provenance and selected source rows.",
    )
    return parser.parse_args()


def get_git_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return "unknown"
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        check=False,
        capture_output=True,
        text=True,
    )
    dirty = status.returncode == 0 and bool(status.stdout.strip())
    return f"{result.stdout.strip()}+dirty" if dirty else result.stdout.strip()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_hub_revision(api: HfApi, repo_id: str, revision: str, *, repo_type: str) -> str:
    """Resolve a Hub ref without relying on private attributes of a loaded object."""
    if repo_type == "dataset":
        info = api.dataset_info(repo_id, revision=revision)
    elif repo_type == "model":
        info = api.model_info(repo_id, revision=revision)
    else:
        raise ValueError(f"Unsupported Hub repository type: {repo_type}")
    resolved = getattr(info, "sha", None)
    if not resolved:
        raise ValueError(f"The Hub did not return a resolved revision for {repo_type} {repo_id}@{revision}")
    if len(revision) == 40 and resolved != revision:
        raise ValueError(
            f"Resolved {repo_type} revision {resolved!r} differs from requested immutable commit {revision!r}"
        )
    return resolved


def parse_task_specs(specs: Iterable[str]) -> list[tuple[str, str]]:
    parsed = []
    for spec in specs:
        category, separator, task = spec.partition(":")
        if not separator or not category.strip() or not task.strip():
            raise ValueError(f"Invalid --task-spec {spec!r}; expected category:dataset_config")
        parsed.append((category.strip(), task.strip()))
    if len(parsed) != len(set(parsed)):
        raise ValueError("Duplicate --task-spec values are not allowed")
    return parsed


def parse_length_bins(specs: Iterable[str]) -> list[tuple[int, int]]:
    bins = []
    for spec in specs:
        lower_text, separator, upper_text = spec.partition(":")
        if not separator:
            raise ValueError(f"Invalid --length-bin {spec!r}; expected lower:upper")
        lower, upper = int(lower_text), int(upper_text)
        if lower < 0 or upper <= lower:
            raise ValueError(f"Invalid --length-bin {spec!r}; require 0 <= lower < upper")
        bins.append((lower, upper))
    ordered = sorted(bins)
    if ordered != bins:
        raise ValueError("--length-bin values must be ordered by lower bound")
    for left, right in zip(bins, bins[1:]):
        if left[1] > right[0]:
            raise ValueError(f"Overlapping length bins are not allowed: {left} and {right}")
    return bins


def length_bucket(token_count: int, bins: list[tuple[int, int]]) -> tuple[int, int] | None:
    return next((bounds for bounds in bins if bounds[0] <= token_count < bounds[1]), None)


def context_token_count(tokenizer, context: str) -> int:
    """Match the context-only part of KVPressTextGenerationPipeline.preprocess without loading a model."""

    if tokenizer.chat_template is None:
        rendered_context = str(getattr(tokenizer, "bos_token", "") or "") + context
    else:
        separator = "#" * (len(context) + 10)
        rendered = tokenizer.apply_chat_template(
            [{"role": "user", "content": context + separator}],
            add_generation_prompt=True,
            tokenize=False,
            enable_thinking=False,
        )
        if rendered.count(separator) != 1:
            raise ValueError("Could not uniquely split the tokenizer chat template at the context boundary")
        rendered_context, _ = rendered.split(separator)
    return len(tokenizer.encode(rendered_context, add_special_tokens=False))


def deterministic_key(seed: int, candidate: dict[str, Any]) -> str:
    identity = f"{seed}:{candidate['task']}:{candidate['source_index']}:{candidate['context_sha256']}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def balanced_take(candidates: list[dict[str, Any]], count: int, seed: int) -> list[dict[str, Any]]:
    """Round-robin across task configs, with deterministic within-task ordering."""

    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_task[candidate["task"]].append(candidate)
    for task in by_task:
        by_task[task].sort(key=lambda row: deterministic_key(seed, row))
    task_order = sorted(by_task, key=lambda task: hashlib.sha256(f"{seed}:{task}".encode()).hexdigest())
    selected = []
    while len(selected) < count:
        progressed = False
        for task in task_order:
            if by_task[task] and len(selected) < count:
                selected.append(by_task[task].pop(0))
                progressed = True
        if not progressed:
            break
    return selected


def select_pilot_rows(
    candidates: list[dict[str, Any]],
    *,
    bins: list[tuple[int, int]],
    samples_per_bucket: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    categories = list(dict.fromkeys(candidate["category"] for candidate in candidates))
    category_rank = {category: index for index, category in enumerate(categories)}
    selected = []
    bucket_report = []
    for category in categories:
        for bounds in bins:
            eligible = [
                candidate
                for candidate in candidates
                if candidate["category"] == category and candidate["length_bucket"] == bounds
            ]
            chosen = balanced_take(eligible, samples_per_bucket, seed)
            selected.extend(chosen)
            bucket_report.append(
                {
                    "category": category,
                    "lower_tokens_inclusive": bounds[0],
                    "upper_tokens_exclusive": bounds[1],
                    "available_unique_contexts": len(eligible),
                    "selected": len(chosen),
                    "requested": samples_per_bucket,
                    "shortfall": samples_per_bucket - len(chosen),
                }
            )
    selected.sort(
        key=lambda row: (category_rank[row["category"]], row["length_bucket"], row["task"], row["source_index"])
    )
    return selected, bucket_report


def collect_candidates(
    task_specs: list[tuple[str, str]],
    bins: list[tuple[int, int]],
    *,
    dataset_repo: str,
    dataset_revision: str,
    split: str,
    token_counter: Callable[[str], int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = []
    task_report = []
    seen_contexts: set[str] = set()
    for category, task in task_specs:
        dataset = load_dataset(dataset_repo, task, split=split, revision=dataset_revision)
        missing_columns = {"context", "question"} - set(dataset.column_names)
        if missing_columns:
            raise ValueError(f"{dataset_repo}/{task} is missing columns: {sorted(missing_columns)}")
        counts = Counter()
        for source_index, row in enumerate(dataset):
            context = str(row["context"])
            question = str(row["question"])
            context_hash = text_sha256(context)
            if context_hash in seen_contexts:
                counts["duplicate_context"] += 1
                continue
            token_count = token_counter(context)
            bounds = length_bucket(token_count, bins)
            if bounds is None:
                counts["outside_length_bins"] += 1
                continue
            seen_contexts.add(context_hash)
            counts["eligible"] += 1
            candidates.append(
                {
                    "request_id": f"longbench__{task}__row{source_index:06d}",
                    "dataset": "longbench",
                    "subset": f"{category}/{task}",
                    "category": category,
                    "task": task,
                    "source_index": source_index,
                    "source_split": split,
                    "estimated_context_tokens": token_count,
                    "length_bucket": bounds,
                    "context_sha256": context_hash,
                    "question_sha256": text_sha256(question),
                    "context": context,
                    "question": question,
                }
            )
        task_report.append(
            {
                "category": category,
                "task": task,
                "dataset_rows": len(dataset),
                "dataset_fingerprint": getattr(dataset, "_fingerprint", None),
                **dict(counts),
            }
        )
    return candidates, task_report


def main() -> None:
    args = parse_args()
    if args.samples_per_bucket <= 0:
        raise ValueError("--samples-per-bucket must be positive")
    if args.output_jsonl == args.output_manifest:
        raise ValueError("--output-jsonl and --output-manifest must differ")
    for path in (args.output_jsonl, args.output_manifest):
        if path.exists():
            raise FileExistsError(f"Output already exists and will not be overwritten: {path}")

    task_specs = parse_task_specs(args.task_specs or DEFAULT_TASK_SPECS)
    bins = parse_length_bins(args.length_bins or DEFAULT_LENGTH_BINS)
    requested_categories = sorted({category for category, _ in task_specs})
    if requested_categories != ["reasoning", "retrieval", "summarization"]:
        print(f"Warning: non-default category set requested: {requested_categories}")

    hub_api = HfApi()
    resolved_dataset_revision = resolve_hub_revision(
        hub_api, args.dataset_repo, args.dataset_revision, repo_type="dataset"
    )
    print(f"Resolved dataset revision: {args.dataset_repo}@{resolved_dataset_revision}")
    resolved_model_revision = resolve_hub_revision(
        hub_api, args.model_name, args.model_revision, repo_type="model"
    )
    print(f"Resolved tokenizer revision: {args.model_name}@{resolved_model_revision}")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, revision=resolved_model_revision)
    candidates, task_report = collect_candidates(
        task_specs,
        bins,
        dataset_repo=args.dataset_repo,
        dataset_revision=resolved_dataset_revision,
        split=args.split,
        token_counter=lambda context: context_token_count(tokenizer, context),
    )
    selected, bucket_report = select_pilot_rows(
        candidates,
        bins=bins,
        samples_per_bucket=args.samples_per_bucket,
        seed=args.seed,
    )
    shortfalls = [row for row in bucket_report if row["shortfall"]]
    if shortfalls and args.strict_buckets:
        raise ValueError(f"Pilot buckets have shortfalls: {shortfalls}")
    if shortfalls:
        print(f"Warning: {len(shortfalls)} category/length buckets have shortfalls; see the manifest")
    if not selected:
        raise ValueError("No samples were selected")

    for path in (args.output_jsonl, args.output_manifest):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as stream:
        for row in selected:
            serialized = dict(row)
            serialized["length_bucket"] = list(serialized["length_bucket"])
            stream.write(json.dumps(serialized, ensure_ascii=False, sort_keys=True) + "\n")

    manifest = {
        "schema_version": PILOT_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "preparation_git_commit": get_git_commit(),
        "dataset_repo": args.dataset_repo,
        "dataset_revision_requested": args.dataset_revision,
        "dataset_revision_resolved": resolved_dataset_revision,
        "split": args.split,
        "model_tokenizer": args.model_name,
        "model_revision_requested": args.model_revision,
        "model_revision_resolved": resolved_model_revision,
        "tokenizer_revision": resolved_model_revision,
        "enable_thinking": False,
        "seed": args.seed,
        "task_specs": [{"category": category, "task": task} for category, task in task_specs],
        "length_bins": [list(bounds) for bounds in bins],
        "samples_per_bucket": args.samples_per_bucket,
        "selected_request_count": len(selected),
        "output_jsonl": str(args.output_jsonl),
        "output_jsonl_sha256": file_sha256(args.output_jsonl),
        "task_report": task_report,
        "bucket_report": bucket_report,
        "selected_requests": [
            {
                key: (list(value) if key == "length_bucket" else value)
                for key, value in row.items()
                if key not in {"context", "question"}
            }
            for row in selected
        ],
        "notes": [
            "The JSONL contains public benchmark text and is ignored by Git.",
            "estimated_context_tokens reproduces the current KVPress context/chat-template boundary without a model.",
            "The exporter records the actual scored context length; analysis must use that observed length.",
            "Answers are intentionally omitted because this pilot collects predictor-only structural traces, "
            "not accuracy.",
        ],
    }
    args.output_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Selected {len(selected)} unique request(s)")
    for row in bucket_report:
        print(
            f"  {row['category']} [{row['lower_tokens_inclusive']},{row['upper_tokens_exclusive']}): "
            f"selected={row['selected']}/{row['requested']} available={row['available_unique_contexts']}"
        )
    print(f"  jsonl: {args.output_jsonl}")
    print(f"  manifest: {args.output_manifest}")


if __name__ == "__main__":
    main()
