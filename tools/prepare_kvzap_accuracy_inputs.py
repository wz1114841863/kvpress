"""Rebuild answer-bearing accuracy inputs from a frozen LongBench pilot manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from datasets import load_dataset


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create immutable answer-bearing inputs for KVzap accuracy screening.")
    parser.add_argument("--pilot-manifest", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.output_jsonl.exists() or args.output_manifest.exists():
        raise FileExistsError("Accuracy input outputs already exist and will not be overwritten")
    pilot = json.loads(args.pilot_manifest.read_text(encoding="utf-8"))
    selected = pilot["selected_requests"]
    by_task: dict[str, list[dict]] = {}
    for row in selected:
        by_task.setdefault(row["task"], []).append(row)
    prepared = []
    for task, rows in by_task.items():
        dataset = load_dataset(pilot["dataset_repo"], task, split="test", revision=pilot["dataset_revision_resolved"])
        for source in rows:
            original = dataset[int(source["source_index"])]
            context, question = str(original["context"]), str(original["question"])
            if sha256(context) != source["context_sha256"] or sha256(question) != source["question_sha256"]:
                raise ValueError(f"Frozen source hash mismatch for {source['request_id']}")
            answers = original.get("answers")
            if not isinstance(answers, list) or not answers:
                raise ValueError(f"{task} row {source['source_index']} has no non-empty answers list")
            prepared.append(
                {
                    "request_id": source["request_id"],
                    "category": source["category"],
                    "task": task,
                    "subset": source["subset"],
                    "context": context,
                    "question": question,
                    "answers": [str(answer) for answer in answers],
                    "all_classes": original.get("all_classes"),
                    "source_index": source["source_index"],
                    "context_sha256": source["context_sha256"],
                    "question_sha256": source["question_sha256"],
                    "length_bucket": source["length_bucket"],
                }
            )
    if len(prepared) != len(selected) or len({row["request_id"] for row in prepared}) != len(prepared):
        raise ValueError("Prepared request count or identities differ from frozen selection")
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as stream:
        for row in prepared:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    output_sha = hashlib.sha256(args.output_jsonl.read_bytes()).hexdigest()
    record = {
        "schema_version": "kvzap-accuracy-input-1.0",
        "source_pilot_manifest": str(args.pilot_manifest),
        "source_pilot_manifest_sha256": hashlib.sha256(args.pilot_manifest.read_bytes()).hexdigest(),
        "dataset_repo": pilot["dataset_repo"],
        "dataset_revision": pilot["dataset_revision_resolved"],
        "request_count": len(prepared),
        "output_jsonl": str(args.output_jsonl),
        "output_jsonl_sha256": output_sha,
        "notes": [
            "Contains public benchmark text and references; do not commit it.",
            "Hashes must match frozen v2 selection.",
        ],
    }
    args.output_manifest.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Prepared {len(prepared)} answer-bearing requests: {args.output_jsonl}")


if __name__ == "__main__":
    main()
