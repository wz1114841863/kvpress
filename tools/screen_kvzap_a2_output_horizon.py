"""Select naturally long normal-generation requests before costly Route-A2 tracing.

The screen deliberately runs no KVzap predictor, no observer, and no pruning.
It is only a sequential candidate selector.  The subsequent A2 collector
remains the authority for actual decode-call counts and lifecycle accounting.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import pipeline

from tools.export_kvzap_predictor_trace import GATE_B_MODEL_REVISION, assert_no_runtime_mask_state, file_sha256, get_git_commit, stable_hash
from tools.run_kvzap_trace import DEFAULT_MODEL, load_jsonl_request, seed_everything


COLUMNS = (
    "request_id", "dataset", "subset", "context_tokens", "max_new_tokens",
    "decoded_answer_token_count", "answer_sha256", "meets_min_decoded_answer_tokens",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sequential normal-generation screen for naturally long Route-A2 candidate outputs.")
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--request-id", action="append", required=True, help="One candidate ID; repeat this option to screen candidates sequentially.")
    parser.add_argument("--model-name", default=DEFAULT_MODEL)
    parser.add_argument("--model-revision", default=GATE_B_MODEL_REVISION)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-new-tokens", type=int, default=128, help="Ceiling only; the screen selects natural outputs that do not stop early.")
    parser.add_argument("--min-decoded-answer-tokens", type=int, default=64)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory only; existing directories are never overwritten.")
    return parser.parse_args()


def answer_hash(output: dict[str, Any]) -> str:
    return hashlib.sha256(str(output["answer"]).encode("utf-8")).hexdigest()


def answer_token_count(tokenizer, output: dict[str, Any]) -> int:
    return len(tokenizer.encode(str(output["answer"]), add_special_tokens=False))


def result_row(request: dict[str, Any], *, context_tokens: int, max_new_tokens: int, decoded_answer_tokens: int, answer_sha256: str, minimum: int) -> dict[str, Any]:
    return {
        "request_id": request["request_id"], "dataset": request["dataset"], "subset": request["subset"],
        "context_tokens": context_tokens, "max_new_tokens": max_new_tokens,
        "decoded_answer_token_count": decoded_answer_tokens, "answer_sha256": answer_sha256,
        "meets_min_decoded_answer_tokens": decoded_answer_tokens >= minimum,
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    if args.max_new_tokens <= 0 or args.min_decoded_answer_tokens <= 0:
        raise ValueError("max/min output token limits must be positive")
    if len(set(args.request_id)) != len(args.request_id):
        raise ValueError("Each --request-id must be unique")
    if args.model_name != DEFAULT_MODEL or args.model_revision != GATE_B_MODEL_REVISION:
        raise ValueError("A2 horizon screening is bounded to the frozen Qwen3-8B model revision")
    requests = [load_jsonl_request(args.input_jsonl, request_id) for request_id in args.request_id]
    print(f"Loading base model: {args.model_name}")
    pipe = pipeline("kv-press-text-generation", model=args.model_name, revision=args.model_revision, device_map="auto", dtype="auto")
    model_revision = getattr(pipe.model.config, "_commit_hash", None)
    if model_revision != args.model_revision:
        raise ValueError(f"Loaded model revision {model_revision!r} differs from requested {args.model_revision!r}")
    rows: list[dict[str, Any]] = []
    for index, request in enumerate(requests, start=1):
        tokenized = pipe.preprocess(str(request["context"]), [str(request["question"])], answer_prefix="", max_context_length=pipe.tokenizer.model_max_length, enable_thinking=False)
        context_tokens = int(tokenized["context_ids"].shape[1])
        print(f"Candidate {index}/{len(requests)}: {request['request_id']} ({context_tokens} context tokens)")
        seed_everything(args.seed)
        with torch.no_grad():
            output = pipe(str(request["context"]), question=str(request["question"]), max_new_tokens=args.max_new_tokens, enable_thinking=False)
        assert_no_runtime_mask_state(pipe.model)
        rows.append(result_row(request, context_tokens=context_tokens, max_new_tokens=args.max_new_tokens, decoded_answer_tokens=answer_token_count(pipe.tokenizer, output), answer_sha256=answer_hash(output), minimum=args.min_decoded_answer_tokens))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    csv_path = args.output_dir / "horizon_screening.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    config = {"model": args.model_name, "model_revision": model_revision, "seed": args.seed, "max_new_tokens": args.max_new_tokens, "min_decoded_answer_tokens": args.min_decoded_answer_tokens, "request_ids": args.request_id, "input_jsonl_sha256": file_sha256(args.input_jsonl)}
    manifest = {
        "schema_version": "kvzap-route-a2-horizon-screen-1.0", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "rows": len(rows), "accepted_request_ids": [row["request_id"] for row in rows if row["meets_min_decoded_answer_tokens"]],
        "notes": ["This is sequential normal dense-KV greedy generation without KVzap, DMS, predictor scoring, or lifecycle observation.", "decoded_answer_token_count is a decoded-text tokenizer proxy used only to select candidates; Route-A2 collector decode_model_call_count is the authoritative lifecycle horizon.", "This screen establishes neither answer correctness nor accuracy, physical memory, HBM traffic, latency, throughput, or break-even."],
        "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__),
    }
    manifest_path = args.output_dir / "horizon_screening_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A2 horizon screen complete: {sum(row['meets_min_decoded_answer_tokens'] for row in rows)}/{len(rows)} candidates meet >= {args.min_decoded_answer_tokens} decoded tokens.")
    print(f"  screening: {csv_path}")
    print(f"  manifest: {manifest_path}")


if __name__ == "__main__":
    main()
