# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Freeze a completed predictor-only LongBench pilot with checked provenance."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from tools.analyze_kvzap_trace import validate_trace


ANALYSIS_ARTIFACTS = (
    "analysis_manifest.json",
    "request_summary.csv",
    "request_group_summary.csv",
    "layer_head_retention.csv",
    "run_length_distribution.csv",
    "block_occupancy.csv",
    "head_similarity.csv",
    "request_pair_similarity.csv",
    "score_threshold_sensitivity.csv",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze a validated predictor-only LongBench pilot.")
    parser.add_argument("--pilot-id", required=True)
    parser.add_argument("--preparation-manifest", type=Path, required=True)
    parser.add_argument("--pilot-run-manifest", type=Path, required=True)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New freeze JSON; existing paths are refused.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "sha256": sha256(path)}


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Freeze output already exists: {args.output}")
    preparation = json.loads(args.preparation_manifest.read_text(encoding="utf-8"))
    run = json.loads(args.pilot_run_manifest.read_text(encoding="utf-8"))
    analysis = json.loads((args.analysis_dir / "analysis_manifest.json").read_text(encoding="utf-8"))
    if preparation.get("schema_version") != "kvzap-real-pilot-1.1":
        raise ValueError("Unsupported preparation manifest schema")
    selected = preparation["selected_requests"]
    requests = run["requests"]
    if len(selected) != preparation["selected_request_count"] or len(requests) != len(selected):
        raise ValueError("Preparation/run request counts disagree")
    statuses = Counter(entry.get("status") for entry in requests.values())
    if statuses != Counter({"complete": len(selected)}):
        raise ValueError(f"Pilot is not complete: {dict(statuses)}")
    errors = []
    traces = []
    for request in selected:
        request_id = request["request_id"]
        entry = requests.get(request_id)
        if entry is None:
            errors.append(f"missing run entry: {request_id}")
            continue
        try:
            trace = validate_trace(Path(entry["trace_dir"]))
        except (FileNotFoundError, ValueError) as error:
            errors.append(f"{request_id}: {error}")
            continue
        if trace["request"]["request_id"] != request_id:
            errors.append(f"{request_id}: trace request id differs")
            continue
        traces.append(trace)
    if errors:
        raise ValueError("Trace validation failed:\n" + "\n".join(errors))
    if analysis.get("trace_count") != len(traces):
        raise ValueError("Analysis trace count differs from validated trace count")
    summary = csv_rows(args.analysis_dir / "request_summary.csv")
    if len(summary) != len(traces):
        raise ValueError("request_summary.csv row count differs from trace count")
    total = sum(int(row["logical_total_kv"]) for row in summary)
    removed = sum(int(row["logical_removed_kv"]) for row in summary)
    observed = {
        "logical_removed_fraction": {
            "request_mean": float(np.mean([float(row["logical_removed_fraction"]) for row in summary])),
            "token_weighted": removed / total,
            "min": float(min(float(row["logical_removed_fraction"]) for row in summary)),
            "p50_higher": float(
                np.percentile([float(row["logical_removed_fraction"]) for row in summary], 50, method="higher")
            ),
            "max": float(max(float(row["logical_removed_fraction"]) for row in summary)),
        },
        "logical_compression_factor": {
            "request_mean": float(np.mean([float(row["logical_compression_factor"]) for row in summary])),
            "token_weighted": total / (total - removed),
        },
        "layer_load_cv_mean": float(np.mean([float(row["layer_load_cv"]) for row in summary])),
        "global_head_load_cv_mean": float(np.mean([float(row["global_head_load_cv"]) for row in summary])),
        "head_keep_jaccard_mean": float(np.mean([float(row["head_keep_jaccard_mean"]) for row in summary])),
        "head_keep_jaccard_excess_mean": float(
            np.mean([float(row["head_keep_jaccard_excess_mean"]) for row in summary])
        ),
        "near_threshold_0_25_fraction_mean": float(
            np.mean([float(row["near_threshold_0_25_fraction"]) for row in summary])
        ),
    }
    group_rows = csv_rows(args.analysis_dir / "request_group_summary.csv")
    all_group = next(row for row in group_rows if row["group_type"] == "all" and row["group_value"] == "all")
    artifacts = {
        str(args.preparation_manifest): artifact(args.preparation_manifest),
        str(args.pilot_run_manifest): artifact(args.pilot_run_manifest),
    }
    input_jsonl = Path(preparation["output_jsonl"])
    artifacts[str(input_jsonl)] = (
        artifact(input_jsonl)
        if input_jsonl.is_file()
        else {"sha256_from_preparation_manifest": preparation["output_jsonl_sha256"], "locally_available": False}
    )
    for name in ANALYSIS_ARTIFACTS:
        path = args.analysis_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Analysis artifact missing: {path}")
        artifacts[str(path)] = artifact(path)
    category_counts = Counter(request["category"] for request in selected)
    task_counts = Counter(request["task"] for request in selected)
    record = {
        "schema_version": "kvzap-longbench-pilot-freeze-1.1",
        "status": "frozen",
        "pilot_id": args.pilot_id,
        "preparation_git_commit": preparation["preparation_git_commit"],
        "runner_git_commit": run["runner_git_commit"],
        "analysis_git_commit": analysis["analysis_git_commit"],
        "dataset": preparation["dataset_repo"],
        "dataset_revision": preparation["dataset_revision_resolved"],
        "model": preparation["model_tokenizer"],
        "model_revision": preparation["model_revision_resolved"],
        "predictor": traces[0]["manifest"]["predictor_checkpoint"],
        "predictor_revision": traces[0]["manifest"]["predictor_revision"],
        "threshold": traces[0]["manifest"]["threshold"],
        "sliding_window": traces[0]["manifest"]["sliding_window"],
        "seed": preparation["seed"],
        "trace_schema": traces[0]["manifest"]["schema_version"],
        "request_count": len(traces),
        "request_status": {"complete": len(traces), "failed": 0, "offline_validation_errors": 0},
        "sampling": {
            "samples_per_category_length_bucket": preparation["samples_per_bucket"],
            "length_bins": preparation["length_bins"],
            "category_counts": dict(sorted(category_counts.items())),
            "task_counts": dict(sorted(task_counts.items())),
            "selection_policy": preparation["selection_policy"],
            "known_limit": (
                "Task availability remains unequal in some category/length buckets; "
                "bucket_report records each gap."
            ),
        },
        "observed_metrics": {**observed, "all_group": all_group},
        "artifact_sha256": artifacts,
        "trace_integrity": (
            "analysis_manifest.json stores ordered SHA-256 values for every source trace "
            "manifest.json and score_mask.npz."
        ),
        "input_jsonl_local_status": (
            "The JSONL is gitignored and may be absent locally; its expected SHA-256 is retained "
            "in the preparation manifest and this freeze record."
        ),
        "validated_invariants": [
            "all selected requests are complete",
            "all trace directories pass schema-1.1 validation",
            "scores are finite and valid",
            "predicted masks equal score < threshold",
            "the newest 128 tokens are protected",
            "Gate A evidence passes",
            "analysis count matches validated traces",
        ],
        "valid_for": ["LongBench predictor-only structural analysis", "offline regularization hypothesis screening"],
        "not_valid_for": [
            "answer accuracy or faithful generation",
            "actual DMS/decode lifecycle",
            "measured physical memory, HBM traffic, or speed",
            "claims beyond the sampled LongBench tasks and length buckets",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Frozen {len(traces)} validated traces: {args.output}")


if __name__ == "__main__":
    main()
