# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Evaluate offline KVzap score-to-mask regularization candidates.

This tool does not load a model and never changes a trace.  Its block-coalesced
masks are hypotheses for a later accuracy evaluation, not replacements for the
official KVzap mask.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from tools.analyze_kvzap_trace import get_git_commit, load_pilot_metadata, safe_divide, validate_trace


DEFAULT_BLOCK_SIZES = (4, 8)
DEFAULT_MARGINS = (-0.25, 0.0, 0.25)
DEFAULT_HEAD_CAPACITY_QUANTA = (16, 32, 64, 128)

POLICY_COLUMNS = (
    "trace_id",
    "request_id",
    "category",
    "task",
    "length_bucket",
    "policy_family",
    "policy_id",
    "block_size",
    "margin",
    "logical_removed_fraction",
    "logical_compression_factor",
    "cold_removed_fraction",
    "newly_dropped_fraction",
    "recovered_keep_fraction",
    "mixed_block_fraction",
    "physical_total_padded",
    "physical_compression_factor_padded",
    "score_margin_abs_p50",
)
HEAD_BUCKET_COLUMNS = (
    "trace_id",
    "request_id",
    "category",
    "task",
    "length_bucket",
    "capacity_quantum",
    "logical_compression_factor",
    "capacity_compression_factor",
    "capacity_fragmentation",
    "head_cold_kept_p50",
    "head_cold_kept_p90",
    "head_cold_kept_max",
    "head_cold_kept_cv",
)
SUMMARY_COLUMNS = (
    "group_type",
    "group_value",
    "policy_family",
    "policy_id",
    "request_count",
    "logical_removed_fraction_weighted",
    "logical_removed_fraction_mean",
    "logical_compression_factor_weighted",
    "newly_dropped_fraction_mean",
    "recovered_keep_fraction_mean",
    "mixed_block_fraction_mean",
    "physical_compression_factor_padded_weighted",
    "physical_compression_factor_padded_mean",
    "score_margin_abs_p50_mean",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate offline structured KVzap mask candidates.")
    parser.add_argument("trace_dirs", nargs="+", type=Path, help="Validated predictor-only trace directories.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory; never overwritten.")
    parser.add_argument("--pilot-manifest", type=Path, help="Optional manifest for category/task/length summaries.")
    parser.add_argument("--block-sizes", nargs="+", type=int, default=list(DEFAULT_BLOCK_SIZES))
    parser.add_argument("--margins", nargs="+", type=float, default=list(DEFAULT_MARGINS))
    parser.add_argument(
        "--head-capacity-quanta",
        nargs="+",
        type=int,
        default=list(DEFAULT_HEAD_CAPACITY_QUANTA),
        help="Cold-token allocation quanta for per-layer/head capacity bucketing.",
    )
    return parser.parse_args()


def write_csv(path: Path, rows: list[dict[str, Any]], columns: Iterable[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: np.ndarray, q: float) -> float:
    return float(np.percentile(values, q, method="higher")) if values.size else math.nan


def coalesced_drop_mask(
    scores: np.ndarray,
    valid: np.ndarray,
    original_drop: np.ndarray,
    threshold: float,
    window: int,
    block_size: int,
    margin: float,
) -> np.ndarray:
    """Make every mature block all-drop or all-keep using its maximum score.

    A block drops only when every valid score is below ``threshold + margin``.
    The protected trailing window remains byte-for-byte identical to the original
    mask.  Positive margins can introduce new drops; negative margins are more
    conservative.  This explicit asymmetry is reported in the output.
    """
    if block_size <= 0:
        raise ValueError(f"block_size must be positive, got {block_size}")
    output = original_drop.copy()
    cold_tokens = scores.shape[-1] - window
    padding = (-cold_tokens) % block_size
    cold_valid = np.pad(valid[..., :cold_tokens], ((0, 0), (0, 0), (0, padding)), constant_values=False)
    cold_scores = np.pad(scores[..., :cold_tokens], ((0, 0), (0, 0), (0, padding)), constant_values=np.inf)
    block_valid = cold_valid.reshape(*cold_valid.shape[:2], -1, block_size)
    block_scores = cold_scores.reshape(*cold_scores.shape[:2], -1, block_size)
    drops = np.all(np.logical_or(~block_valid, block_scores < threshold + margin), axis=-1)
    expanded = np.repeat(drops, block_size, axis=-1)[..., :cold_tokens]
    output[..., :cold_tokens] = expanded & valid[..., :cold_tokens]
    return output


def mask_metrics(
    final_drop: np.ndarray,
    original_drop: np.ndarray,
    valid: np.ndarray,
    window: int,
    block_size: int | None,
    scores: np.ndarray,
    threshold: float,
) -> dict[str, float]:
    tokens = final_drop.shape[-1]
    cold_tokens = tokens - window
    total = int(valid.sum())
    removed = int(final_drop.sum())
    cold_valid = valid[..., :cold_tokens]
    cold_drop = final_drop[..., :cold_tokens]
    original_cold = original_drop[..., :cold_tokens]
    values: dict[str, float] = {
        "logical_removed_fraction": removed / total,
        "logical_compression_factor": safe_divide(total, total - removed),
        "cold_removed_fraction": float(cold_drop.sum() / cold_valid.sum()),
        "newly_dropped_fraction": float(np.logical_and(cold_drop, ~original_cold).sum() / cold_valid.sum()),
        "recovered_keep_fraction": float(np.logical_and(~cold_drop, original_cold).sum() / cold_valid.sum()),
        "mixed_block_fraction": math.nan,
        "physical_total_padded": math.nan,
        "physical_compression_factor_padded": math.nan,
        "score_margin_abs_p50": percentile(np.abs(scores[valid] - threshold), 50),
    }
    if block_size is None:
        return values
    padding = (-cold_tokens) % block_size
    cold_keep = np.pad(~cold_drop, ((0, 0), (0, 0), (0, padding)), constant_values=False)
    blocks = cold_keep.reshape(*cold_keep.shape[:2], -1, block_size)
    has_keep = blocks.any(axis=-1)
    all_keep = blocks.all(axis=-1)
    physical_cold = int(has_keep.sum()) * block_size
    mixed = int(np.logical_and(has_keep, ~all_keep).sum())
    physical_total = final_drop.shape[0] * final_drop.shape[1] * window + physical_cold
    values["mixed_block_fraction"] = mixed / has_keep.size
    values["physical_total_padded"] = physical_total
    values["physical_compression_factor_padded"] = safe_divide(total, physical_total)
    return values


def capacity_bucket_metrics(final_drop: np.ndarray, valid: np.ndarray, window: int, quantum: int) -> dict[str, float]:
    if quantum <= 0:
        raise ValueError(f"head capacity quantum must be positive, got {quantum}")
    cold_tokens = final_drop.shape[-1] - window
    cold_keep = np.logical_and(~final_drop[..., :cold_tokens], valid[..., :cold_tokens]).sum(axis=-1).astype(np.int64)
    allocated = ((cold_keep + quantum - 1) // quantum) * quantum
    total = int(valid.sum())
    logical_kept = int(np.logical_and(~final_drop, valid).sum())
    capacity_kept = final_drop.shape[0] * final_drop.shape[1] * window + int(allocated.sum())
    mean = float(cold_keep.mean())
    return {
        "logical_compression_factor": safe_divide(total, logical_kept),
        "capacity_compression_factor": safe_divide(total, capacity_kept),
        "capacity_fragmentation": safe_divide(int(allocated.sum()) - int(cold_keep.sum()), int(allocated.sum())),
        "head_cold_kept_p50": percentile(cold_keep, 50),
        "head_cold_kept_p90": percentile(cold_keep, 90),
        "head_cold_kept_max": int(cold_keep.max()),
        "head_cold_kept_cv": float(cold_keep.std() / mean) if mean else math.nan,
    }


def metadata_for(request_id: str, metadata: dict[str, dict[str, Any]]) -> dict[str, str]:
    row = metadata.get(request_id, {})
    bucket = row.get("length_bucket")
    return {
        "category": str(row.get("category", "unlabeled")),
        "task": str(row.get("task", "unlabeled")),
        "length_bucket": "unlabeled" if bucket is None else f"[{bucket[0]},{bucket[1]})",
    }


def summarize_policy_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for group_type, group_value in (
            ("all", "all"),
            ("category", row["category"]),
            ("task", row["task"]),
            ("length_bucket", row["length_bucket"]),
        ):
            groups[(group_type, group_value, row["policy_id"])].append(row)
    output = []
    for (group_type, group_value, policy_id), values in sorted(groups.items()):
        total_weight = sum(float(row["logical_total"]) for row in values)
        total_removed = sum(float(row["logical_removed_fraction"]) * float(row["logical_total"]) for row in values)
        total_kept = total_weight - total_removed
        output.append(
            {
                "group_type": group_type,
                "group_value": group_value,
                "policy_family": values[0]["policy_family"],
                "policy_id": policy_id,
                "request_count": len(values),
                "logical_removed_fraction_weighted": total_removed / total_weight,
                "logical_removed_fraction_mean": float(
                    np.mean([float(row["logical_removed_fraction"]) for row in values])
                ),
                "logical_compression_factor_weighted": safe_divide(total_weight, total_kept),
                "newly_dropped_fraction_mean": float(np.mean([float(row["newly_dropped_fraction"]) for row in values])),
                "recovered_keep_fraction_mean": float(
                    np.mean([float(row["recovered_keep_fraction"]) for row in values])
                ),
                "mixed_block_fraction_mean": float(np.nanmean([float(row["mixed_block_fraction"]) for row in values])),
                "physical_compression_factor_padded_weighted": safe_divide(
                    total_weight, sum(float(row["physical_total_padded"]) for row in values)
                ),
                "physical_compression_factor_padded_mean": float(
                    np.nanmean([float(row["physical_compression_factor_padded"]) for row in values])
                ),
                "score_margin_abs_p50_mean": float(np.mean([float(row["score_margin_abs_p50"]) for row in values])),
            }
        )
    return output


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    for values, flag in ((args.block_sizes, "--block-sizes"), (args.head_capacity_quanta, "--head-capacity-quanta")):
        if any(value <= 0 for value in values) or len(values) != len(set(values)):
            raise ValueError(f"{flag} must contain unique positive integers")
    pilot_manifest, metadata = load_pilot_metadata(args.pilot_manifest) if args.pilot_manifest else (None, {})
    traces = [validate_trace(path) for path in args.trace_dirs]
    if not all(trace["predictor_only"] for trace in traces):
        raise ValueError("Structured policy evaluation currently accepts predictor-only traces only")
    args.output_dir.mkdir(parents=True)
    policy_rows: list[dict[str, Any]] = []
    bucket_rows: list[dict[str, Any]] = []
    for trace in traces:
        manifest, request = trace["manifest"], trace["request"]
        scores, valid, original = trace["scores"], trace["valid"], trace["final"]
        base = {
            "trace_id": trace["trace_id"],
            "request_id": request["request_id"],
            **metadata_for(request["request_id"], metadata),
        }
        total = int(valid.sum())
        for block_size in args.block_sizes:
            for margin in args.margins:
                policy = coalesced_drop_mask(
                    scores,
                    valid,
                    original,
                    float(manifest["threshold"]),
                    int(manifest["sliding_window"]),
                    block_size,
                    margin,
                )
                metrics = mask_metrics(
                    policy,
                    original,
                    valid,
                    int(manifest["sliding_window"]),
                    block_size,
                    scores,
                    float(manifest["threshold"]),
                )
                policy_rows.append(
                    {
                        **base,
                        "policy_family": "margin_aware_block_coalescing",
                        "policy_id": f"coalesce_B{block_size}_m{margin:+.2f}",
                        "block_size": block_size,
                        "margin": margin,
                        **metrics,
                        "logical_total": total,
                    }
                )
        for quantum in args.head_capacity_quanta:
            bucket_rows.append(
                {
                    **base,
                    "capacity_quantum": quantum,
                    **capacity_bucket_metrics(original, valid, int(manifest["sliding_window"]), quantum),
                }
            )
    write_csv(args.output_dir / "structured_policy_request.csv", policy_rows, (*POLICY_COLUMNS, "logical_total"))
    write_csv(args.output_dir / "structured_policy_summary.csv", summarize_policy_rows(policy_rows), SUMMARY_COLUMNS)
    write_csv(args.output_dir / "head_length_bucketing.csv", bucket_rows, HEAD_BUCKET_COLUMNS)
    manifest = {
        "schema_version": "kvzap-structured-policy-evaluation-1.0",
        "git_commit": get_git_commit(),
        "trace_count": len(traces),
        "source_traces": [str(trace["trace_dir"]) for trace in traces],
        "source_trace_manifest_sha256": [sha256(trace["trace_dir"] / "manifest.json") for trace in traces],
        "pilot_manifest": None if args.pilot_manifest is None else str(args.pilot_manifest),
        "pilot_manifest_sha256": None if args.pilot_manifest is None else sha256(args.pilot_manifest),
        "block_sizes": args.block_sizes,
        "margins": args.margins,
        "head_capacity_quanta": args.head_capacity_quanta,
        "notes": [
            "All results are offline logical-mask or allocation estimates; no model inference occurs.",
            "Coalescing changes only mature cold tokens and preserves the trailing protected window.",
            "Positive coalescing margins may add drops and require independent accuracy evaluation.",
            "Head-length bucketing changes only capacity allocation, not token masks.",
            "No accuracy, physical allocation, HBM traffic, or speed conclusion is licensed by this output.",
        ],
    }
    (args.output_dir / "evaluation_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Evaluated {len(traces)} trace(s). Results: {args.output_dir}")


if __name__ == "__main__":
    main()
