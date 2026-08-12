# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Analyze one or more KVzap score/mask traces without loading the base model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np


SUPPORTED_SCHEMA = "1.0"
DEFAULT_BLOCK_SIZES = (4, 8, 16, 32)
DEFAULT_THRESHOLD_DELTAS = (-0.5, -0.25, 0.0, 0.25, 0.5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze KVzap scores, final masks, block occupancy, head similarity, load imbalance, "
            "and decoding growth from one or more trace directories."
        )
    )
    parser.add_argument("trace_dirs", nargs="+", type=Path, help="Directories produced by run_kvzap_trace.py.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("analysis/experiments/kvzap_trace_analysis"),
        help="New output directory; existing directories are not overwritten.",
    )
    parser.add_argument(
        "--block-sizes",
        nargs="+",
        type=int,
        default=list(DEFAULT_BLOCK_SIZES),
        help="Cold-cache token block sizes to evaluate.",
    )
    parser.add_argument(
        "--threshold-deltas",
        nargs="+",
        type=float,
        default=list(DEFAULT_THRESHOLD_DELTAS),
        help="Offsets added to the recorded threshold for score sensitivity analysis.",
    )
    parser.add_argument("--no-plots", action="store_true", help="Write CSV/JSON only; do not require matplotlib.")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Iterable[str] | None = None) -> None:
    if not rows and fieldnames is None:
        raise ValueError(f"Cannot infer columns for empty CSV: {path}")
    columns = list(fieldnames) if fieldnames is not None else list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def percentile(values: list[float] | np.ndarray, q: float) -> float:
    if len(values) == 0:
        return math.nan
    return float(np.percentile(values, q, method="higher"))


def coefficient_of_variation(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    mean = float(array.mean())
    return float(array.std() / mean) if mean else math.nan


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else math.nan


def get_git_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], check=False, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def stable_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_lengths(mask: np.ndarray, value: bool) -> np.ndarray:
    """Return run lengths along the final axis of an arbitrary-rank boolean mask."""
    rows = np.asarray(mask, dtype=np.bool_).reshape(-1, mask.shape[-1])
    lengths: list[int] = []
    for row in rows:
        selected = row == value
        padded = np.pad(selected.astype(np.int8), (1, 1))
        edges = np.flatnonzero(np.diff(padded))
        lengths.extend((edges[1::2] - edges[::2]).tolist())
    return np.asarray(lengths, dtype=np.int64)


def jaccard(left: np.ndarray, right: np.ndarray) -> float:
    union = int(np.logical_or(left, right).sum())
    return float(np.logical_and(left, right).sum() / union) if union else 1.0


def validate_trace(trace_dir: Path) -> dict[str, Any]:
    required = {
        "manifest.json",
        "score_mask.npz",
        "request_summary.csv",
        "layer_head_summary.csv",
        "decoding_events.csv",
    }
    missing = sorted(name for name in required if not (trace_dir / name).is_file())
    if missing:
        raise FileNotFoundError(f"{trace_dir} is missing trace files: {missing}")

    manifest = json.loads((trace_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SUPPORTED_SCHEMA:
        raise ValueError(
            f"Unsupported schema {manifest.get('schema_version')!r} in {trace_dir}; expected {SUPPORTED_SCHEMA!r}"
        )
    if manifest.get("tensor_layout") != "L,H,T":
        raise ValueError(f"Unsupported tensor layout in {trace_dir}: {manifest.get('tensor_layout')!r}")
    if not manifest.get("trace_equivalence_verified", False):
        raise ValueError(f"Trace equivalence was not verified in {trace_dir}")

    with np.load(trace_dir / "score_mask.npz") as archive:
        required_arrays = {"scores", "score_valid_mask", "predicted_drop_mask", "final_drop_mask", "shape"}
        if missing_arrays := sorted(required_arrays - set(archive.files)):
            raise ValueError(f"{trace_dir}/score_mask.npz is missing arrays: {missing_arrays}")
        arrays = {name: archive[name].copy() for name in required_arrays}

    expected_shape = tuple(int(value) for value in arrays.pop("shape"))
    for name, array in arrays.items():
        if array.shape != expected_shape:
            raise ValueError(f"{trace_dir}: {name} shape {array.shape} != declared {expected_shape}")
    scores = arrays["scores"]
    valid = arrays["score_valid_mask"].astype(np.bool_, copy=False)
    predicted = arrays["predicted_drop_mask"].astype(np.bool_, copy=False)
    final = arrays["final_drop_mask"].astype(np.bool_, copy=False)
    if not np.isfinite(scores[valid]).all():
        raise ValueError(f"{trace_dir}: valid scores contain NaN or infinity")
    if np.any(final & ~valid):
        raise ValueError(f"{trace_dir}: final mask drops a position without a valid score")
    if not valid.all():
        raise ValueError(f"{trace_dir}: pilot analyzer requires a dense valid [L,H,T] score trace")

    window = int(manifest["sliding_window"])
    tokens = expected_shape[-1]
    if window < 0 or window > tokens:
        raise ValueError(f"{trace_dir}: invalid sliding window {window} for T={tokens}")
    if window and final[..., tokens - window :].any():
        raise ValueError(f"{trace_dir}: final mask drops a protected recent token")
    cold_tokens = tokens - window
    if not np.array_equal(final[..., :cold_tokens], predicted[..., :cold_tokens]):
        raise ValueError(f"{trace_dir}: final cold-cache mask differs from the predictor threshold mask")

    request_rows = read_csv(trace_dir / "request_summary.csv")
    if len(request_rows) != 1:
        raise ValueError(f"Pilot trace must have exactly one request summary row, got {len(request_rows)}")
    request = request_rows[0]
    logical_total = int(valid.sum())
    logical_removed = int(final.sum())
    if logical_total != int(request["logical_total_kv"]):
        raise ValueError(f"{trace_dir}: request summary logical_total_kv does not match NPZ")
    if logical_total - logical_removed != int(request["logical_kept_kv"]):
        raise ValueError(f"{trace_dir}: request summary logical_kept_kv does not match NPZ")

    trace_id = f"{manifest['experiment_id']}::{request['request_id']}"
    return {
        "trace_dir": trace_dir,
        "trace_id": trace_id,
        "manifest": manifest,
        "request": request,
        "scores": scores,
        "valid": valid,
        "predicted": predicted,
        "final": final,
        "events": read_csv(trace_dir / "decoding_events.csv"),
    }


def analyze_trace(
    trace: dict[str, Any], block_sizes: list[int], threshold_deltas: list[float]
) -> dict[str, list[dict[str, Any]] | dict[str, Any]]:
    manifest = trace["manifest"]
    request = trace["request"]
    scores = trace["scores"]
    valid = trace["valid"]
    predicted = trace["predicted"]
    final = trace["final"]
    trace_id = trace["trace_id"]
    layers, heads, tokens = scores.shape
    window = int(manifest["sliding_window"])
    cold_tokens = tokens - window
    cold_final = final[..., :cold_tokens]
    cold_valid = valid[..., :cold_tokens]
    threshold = float(manifest["threshold"])

    base = {
        "trace_id": trace_id,
        "experiment_id": manifest["experiment_id"],
        "request_id": request["request_id"],
    }
    logical_total = int(valid.sum())
    logical_removed = int(final.sum())
    predicted_removed = int(np.logical_and(predicted, valid).sum())
    recent_predicted = int(np.logical_and(predicted[..., cold_tokens:], valid[..., cold_tokens:]).sum())
    summary = {
        **base,
        "model": manifest["model"],
        "dataset": manifest["dataset"],
        "subset": manifest["subset"],
        "predictor_checkpoint": manifest["predictor_checkpoint"],
        "threshold": threshold,
        "sliding_window": window,
        "layers": layers,
        "kv_heads": heads,
        "sequence_tokens": tokens,
        "prompt_tokens": int(request["prompt_tokens"]),
        "generated_tokens_retokenized": int(request["generated_tokens_retokenized"]),
        "logical_total_kv": logical_total,
        "logical_removed_kv": logical_removed,
        "logical_removed_fraction": logical_removed / logical_total,
        "logical_compression_factor": safe_divide(logical_total, logical_total - logical_removed),
        "cold_removed_fraction": float(cold_final.sum() / cold_valid.sum()),
        "predicted_removed_fraction": predicted_removed / logical_total,
        "protected_recent_predicted_drops": recent_predicted,
        "protected_recent_final_drops": int(final[..., cold_tokens:].sum()),
    }

    layer_head_rows = []
    for layer in range(layers):
        for head in range(heads):
            head_valid = valid[layer, head]
            head_scores = scores[layer, head, head_valid]
            kept = int(np.logical_and(~final[layer, head], head_valid).sum())
            cold_kept = int(np.logical_and(~cold_final[layer, head], cold_valid[layer, head]).sum())
            layer_head_rows.append(
                {
                    **base,
                    "layer": layer,
                    "kv_head": head,
                    "sequence_tokens": int(head_valid.sum()),
                    "kept_tokens": kept,
                    "removed_tokens": int(np.logical_and(final[layer, head], head_valid).sum()),
                    "retention_ratio": kept / int(head_valid.sum()),
                    "cold_retention_ratio": cold_kept / int(cold_valid[layer, head].sum()),
                    "score_mean": float(head_scores.mean()),
                    "score_std": float(head_scores.std()),
                    "margin_abs_mean": float(np.abs(head_scores - threshold).mean()),
                    "near_threshold_0_10_fraction": float((np.abs(head_scores - threshold) <= 0.10).mean()),
                    "near_threshold_0_25_fraction": float((np.abs(head_scores - threshold) <= 0.25).mean()),
                }
            )

    layer_retention = [
        float(np.logical_and(~final[layer], valid[layer]).sum() / valid[layer].sum()) for layer in range(layers)
    ]
    global_head_retention = [
        float(np.logical_and(~final[:, head], valid[:, head]).sum() / valid[:, head].sum()) for head in range(heads)
    ]
    summary.update(
        {
            "layer_retention_min": min(layer_retention),
            "layer_retention_max": max(layer_retention),
            "layer_load_cv": coefficient_of_variation(layer_retention),
            "global_head_retention_min": min(global_head_retention),
            "global_head_retention_max": max(global_head_retention),
            "global_head_load_cv": coefficient_of_variation(global_head_retention),
            "all_cold_dropped_layer_heads": int(cold_final.all(axis=-1).sum()),
            "all_cold_kept_layer_heads": int((~cold_final).all(axis=-1).sum()),
        }
    )

    run_summary_rows = []
    run_distribution_rows = []
    for state, value in (("drop", True), ("keep", False)):
        lengths = run_lengths(cold_final, value)
        run_summary_rows.append(
            {
                **base,
                "state": state,
                "run_count": len(lengths),
                "mean": float(lengths.mean()) if len(lengths) else math.nan,
                "p50": percentile(lengths, 50),
                "p90": percentile(lengths, 90),
                "p95": percentile(lengths, 95),
                "p99": percentile(lengths, 99),
                "max": int(lengths.max()) if len(lengths) else 0,
            }
        )
        for length, count in sorted(Counter(lengths.tolist()).items()):
            run_distribution_rows.append({**base, "state": state, "run_length": length, "count": count})

    block_rows = []
    for block_size in block_sizes:
        if block_size <= 0:
            raise ValueError(f"Block sizes must be positive, got {block_size}")
        occupancies = []
        logical_cold_kept = 0
        physical_cold_exact = 0
        physical_cold_padded = 0
        exact_cold_slots = 0
        for layer in range(layers):
            for head in range(heads):
                keep = ~cold_final[layer, head]
                logical_cold_kept += int(keep.sum())
                for start in range(0, cold_tokens, block_size):
                    block = keep[start : start + block_size]
                    occupancies.append(float(block.mean()))
                    exact_cold_slots += len(block)
                    if block.any():
                        physical_cold_exact += len(block)
                        physical_cold_padded += block_size
        physical_total_exact = layers * heads * window + physical_cold_exact
        physical_total_padded = layers * heads * window + physical_cold_padded
        block_rows.append(
            {
                **base,
                "block_size": block_size,
                "block_count": len(occupancies),
                "all_drop_block_fraction": float(np.mean(np.asarray(occupancies) == 0)),
                "all_keep_block_fraction": float(np.mean(np.asarray(occupancies) == 1)),
                "mixed_block_fraction": float(
                    np.mean(np.logical_and(np.asarray(occupancies) > 0, np.asarray(occupancies) < 1))
                ),
                "logical_cold_retention": logical_cold_kept / exact_cold_slots,
                "physical_cold_retention_exact_span": physical_cold_exact / exact_cold_slots,
                "physical_cold_retention_padded": physical_cold_padded / exact_cold_slots,
                "internal_fragmentation_exact_span": safe_divide(
                    physical_cold_exact - logical_cold_kept, physical_cold_exact
                ),
                "internal_fragmentation_padded": safe_divide(
                    physical_cold_padded - logical_cold_kept, physical_cold_padded
                ),
                "physical_compression_factor_exact_span": safe_divide(logical_total, physical_total_exact),
                "physical_compression_factor_padded": safe_divide(logical_total, physical_total_padded),
            }
        )

    head_similarity_rows = []
    for layer in range(layers):
        for left_head in range(heads):
            for right_head in range(left_head + 1, heads):
                left_drop = cold_final[layer, left_head]
                right_drop = cold_final[layer, right_head]
                head_similarity_rows.append(
                    {
                        **base,
                        "layer": layer,
                        "left_kv_head": left_head,
                        "right_kv_head": right_head,
                        "drop_jaccard": jaccard(left_drop, right_drop),
                        "keep_jaccard": jaccard(~left_drop, ~right_drop),
                    }
                )
    summary.update(
        {
            "head_drop_jaccard_mean": float(np.mean([row["drop_jaccard"] for row in head_similarity_rows])),
            "head_keep_jaccard_mean": float(np.mean([row["keep_jaccard"] for row in head_similarity_rows])),
        }
    )

    score_sensitivity_rows = []
    valid_scores = scores[valid]
    for delta in threshold_deltas:
        score_sensitivity_rows.append(
            {
                **base,
                "threshold_delta": delta,
                "effective_threshold": threshold + delta,
                "predicted_drop_fraction": float((valid_scores < threshold + delta).mean()),
            }
        )

    decoding_rows, decoding_summary = analyze_decoding_events(trace, layers * heads)
    if decoding_rows[-1]["cumulative_dropped_kv"] != logical_removed:
        raise ValueError(f"{trace['trace_dir']}: final decoding event does not match final_drop_mask")
    summary.update(decoding_summary)
    return {
        "summary": summary,
        "layer_head": layer_head_rows,
        "run_summary": run_summary_rows,
        "run_distribution": run_distribution_rows,
        "block": block_rows,
        "head_similarity": head_similarity_rows,
        "score_sensitivity": score_sensitivity_rows,
        "decoding": decoding_rows,
    }


def analyze_decoding_events(
    trace: dict[str, Any], expected_layer_heads: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in trace["events"]:
        grouped[(row["phase"], int(row["step"]))].append(row)
    for key, rows in grouped.items():
        if len(rows) != expected_layer_heads:
            raise ValueError(f"{trace['trace_dir']}: event {key} has {len(rows)} rows, expected {expected_layer_heads}")

    ordered = sorted(grouped, key=lambda key: (0 if key[0] == "prefill" else 1, key[1]))
    previous_cache = 0
    output_rows = []
    for phase, step in ordered:
        rows = grouped[(phase, step)]
        cache_tokens = int(rows[0]["cache_tokens"])
        if any(int(row["cache_tokens"]) != cache_tokens for row in rows):
            raise ValueError(f"{trace['trace_dir']}: inconsistent cache length at {(phase, step)}")
        tokens_added = cache_tokens - previous_cache
        if phase == "prefill":
            event_kind = "context_prefill"
        elif tokens_added > 1:
            event_kind = "prompt_chunk"
        else:
            event_kind = "generation"
        newly_dropped = sum(int(row["newly_dropped_tokens"]) for row in rows)
        newly_admitted = sum(int(row["newly_admitted_tokens"]) for row in rows)
        output_rows.append(
            {
                "trace_id": trace["trace_id"],
                "experiment_id": trace["manifest"]["experiment_id"],
                "request_id": trace["request"]["request_id"],
                "phase": phase,
                "step": step,
                "event_kind": event_kind,
                "cache_tokens": cache_tokens,
                "tokens_added": tokens_added,
                "newly_dropped_kv": newly_dropped,
                "newly_admitted_kv": newly_admitted,
                "drop_fraction_of_matured": safe_divide(newly_dropped, newly_dropped + newly_admitted),
                "logical_kept_kv": sum(int(row["logical_kept_tokens"]) for row in rows),
                "cumulative_dropped_kv": sum(int(row["cumulative_dropped_tokens"]) for row in rows),
            }
        )
        previous_cache = cache_tokens

    generation_rows = [row for row in output_rows if row["event_kind"] == "generation"]
    prompt_chunks = [row for row in output_rows if row["event_kind"] == "prompt_chunk"]
    generation_dropped = [row["newly_dropped_kv"] for row in generation_rows]
    generation_admitted = [row["newly_admitted_kv"] for row in generation_rows]
    summary = {
        "context_prefill_tokens": next(
            row["cache_tokens"] for row in output_rows if row["event_kind"] == "context_prefill"
        ),
        "prompt_chunk_count": len(prompt_chunks),
        "prompt_chunk_tokens": sum(row["tokens_added"] for row in prompt_chunks),
        "generation_steps": len(generation_rows),
        "final_cache_tokens": output_rows[-1]["cache_tokens"],
        "generation_newly_dropped_mean": float(np.mean(generation_dropped)) if generation_dropped else math.nan,
        "generation_newly_dropped_p90": percentile(generation_dropped, 90),
        "generation_newly_dropped_max": max(generation_dropped, default=0),
        "generation_newly_admitted_mean": float(np.mean(generation_admitted)) if generation_admitted else math.nan,
        "generation_newly_admitted_p90": percentile(generation_admitted, 90),
        "generation_newly_admitted_max": max(generation_admitted, default=0),
    }
    return output_rows, summary


def figure_metadata(trace: dict[str, Any]) -> str:
    manifest = trace["manifest"]
    request = trace["request"]
    return (
        f"model={manifest['model']} | dataset={manifest['dataset']}/{manifest['subset']} | "
        f"threshold={manifest['threshold']} | predictor={manifest['predictor_checkpoint']} | "
        f"window={manifest['sliding_window']} | prompt/output={request['prompt_tokens']}/"
        f"{request['generated_tokens_retokenized']} | N=1 | experiment={manifest['experiment_id']} | "
        f"git={manifest['git_commit'][:12]}"
    )


def write_figures(output_dir: Path, traces: list[dict[str, Any]], results: list[dict[str, Any]]) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise RuntimeError(
            "Plotting requires matplotlib; install project dev dependencies or use --no-plots"
        ) from error

    figures_dir = output_dir / "figures"
    figures_dir.mkdir()
    for trace, result in zip(traces, results):
        suffix = trace["manifest"]["experiment_id"].replace("kvzap-trace-", "")
        metadata = figure_metadata(trace)
        layers, heads, _ = trace["scores"].shape

        retention = np.zeros((layers, heads), dtype=np.float64)
        for row in result["layer_head"]:
            retention[row["layer"], row["kv_head"]] = row["retention_ratio"]
        fig, axis = plt.subplots(figsize=(10, 6))
        image = axis.imshow(retention, aspect="auto", interpolation="nearest", vmin=0, vmax=1, cmap="viridis")
        axis.set(title="Layer–KV-head retention", xlabel="KV head", ylabel="Layer")
        fig.colorbar(image, ax=axis, label="Retention ratio")
        fig.suptitle(metadata, fontsize=7, y=0.01)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        fig.savefig(figures_dir / f"layer_head_retention_{suffix}.png", dpi=180)
        plt.close(fig)

        fig, axis = plt.subplots(figsize=(8, 5))
        for state in ("drop", "keep"):
            rows = [row for row in result["run_distribution"] if row["state"] == state]
            lengths = np.asarray([row["run_length"] for row in rows])
            counts = np.asarray([row["count"] for row in rows])
            cdf = np.cumsum(counts) / counts.sum()
            axis.step(lengths, cdf, where="post", label=state)
        axis.set(xscale="log", xlabel="Run length (tokens, log scale)", ylabel="CDF", title="Cold-cache run lengths")
        axis.grid(alpha=0.25)
        axis.legend()
        fig.suptitle(metadata, fontsize=7, y=0.01)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        fig.savefig(figures_dir / f"run_length_cdf_{suffix}.png", dpi=180)
        plt.close(fig)

        block_rows = result["block"]
        sizes = [row["block_size"] for row in block_rows]
        fig, axis = plt.subplots(figsize=(8, 5))
        axis.plot(sizes, [row["all_drop_block_fraction"] for row in block_rows], marker="o", label="all-drop blocks")
        axis.plot(sizes, [row["mixed_block_fraction"] for row in block_rows], marker="o", label="mixed blocks")
        axis.plot(
            sizes,
            [row["physical_cold_retention_padded"] for row in block_rows],
            marker="o",
            label="physical cold retention (padded)",
        )
        axis.set(xlabel="Block size", ylabel="Fraction", title="Block occupancy and physical retention", xticks=sizes)
        axis.grid(alpha=0.25)
        axis.legend()
        fig.suptitle(metadata, fontsize=7, y=0.01)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        fig.savefig(figures_dir / f"block_occupancy_{suffix}.png", dpi=180)
        plt.close(fig)

        keep_similarity = np.eye(heads, dtype=np.float64)
        drop_similarity = np.eye(heads, dtype=np.float64)
        pair_counts = np.zeros((heads, heads), dtype=np.int64)
        for row in result["head_similarity"]:
            left = row["left_kv_head"]
            right = row["right_kv_head"]
            keep_similarity[left, right] += row["keep_jaccard"]
            keep_similarity[right, left] += row["keep_jaccard"]
            drop_similarity[left, right] += row["drop_jaccard"]
            drop_similarity[right, left] += row["drop_jaccard"]
            pair_counts[left, right] += 1
            pair_counts[right, left] += 1
        off_diagonal = pair_counts > 0
        keep_similarity[off_diagonal] /= pair_counts[off_diagonal]
        drop_similarity[off_diagonal] /= pair_counts[off_diagonal]
        fig, axes = plt.subplots(1, 2, figsize=(11, 5))
        for axis, matrix, title in zip(
            axes,
            (keep_similarity, drop_similarity),
            ("Keep-mask Jaccard", "Drop-mask Jaccard"),
        ):
            image = axis.imshow(matrix, vmin=0, vmax=1, cmap="magma")
            axis.set(title=title, xlabel="KV head", ylabel="KV head")
            fig.colorbar(image, ax=axis, fraction=0.046)
        fig.suptitle(metadata, fontsize=7, y=0.01)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        fig.savefig(figures_dir / f"head_similarity_{suffix}.png", dpi=180)
        plt.close(fig)

        fig, axis = plt.subplots(figsize=(8, 5))
        margins = np.abs(trace["scores"][trace["valid"]] - float(trace["manifest"]["threshold"]))
        sorted_margins = np.sort(margins)
        axis.plot(sorted_margins, np.arange(1, len(sorted_margins) + 1) / len(sorted_margins))
        axis.set(xlabel="Absolute score margin", ylabel="CDF", title="Score margin from pruning threshold")
        axis.set_xlim(left=0)
        axis.grid(alpha=0.25)
        fig.suptitle(metadata, fontsize=7, y=0.01)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        fig.savefig(figures_dir / f"score_margin_cdf_{suffix}.png", dpi=180)
        plt.close(fig)

        decoding = result["decoding"]
        fig, axis = plt.subplots(figsize=(9, 5))
        axis.plot([row["cache_tokens"] for row in decoding], [row["logical_kept_kv"] for row in decoding])
        for row in decoding:
            if row["event_kind"] == "prompt_chunk":
                axis.axvline(row["cache_tokens"], color="tab:orange", linestyle="--", alpha=0.7)
        axis.set(xlabel="Cache tokens", ylabel="Logical kept KV across layer-heads", title="Decoding KV growth")
        axis.grid(alpha=0.25)
        fig.suptitle(metadata, fontsize=7, y=0.01)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        fig.savefig(figures_dir / f"decoding_growth_{suffix}.png", dpi=180)
        plt.close(fig)

    removed_fractions = sorted(result["summary"]["logical_removed_fraction"] for result in results)
    first_manifest = traces[0]["manifest"]
    prompt_lengths = [int(trace["request"]["prompt_tokens"]) for trace in traces]
    output_lengths = [int(trace["request"]["generated_tokens_retokenized"]) for trace in traces]
    common_metadata = (
        f"model={first_manifest['model']} | datasets=multiple | threshold={first_manifest['threshold']} | "
        f"predictor={first_manifest['predictor_checkpoint']} | window={first_manifest['sliding_window']} | "
        f"prompt range={min(prompt_lengths)}..{max(prompt_lengths)} | "
        f"output range={min(output_lengths)}..{max(output_lengths)} | N={len(traces)} | "
        f"analysis git={get_git_commit()[:12]}"
    )
    fig, axis = plt.subplots(figsize=(8, 5))
    axis.step(
        removed_fractions,
        np.arange(1, len(removed_fractions) + 1) / len(removed_fractions),
        where="post",
    )
    axis.set(xlabel="Logical removed fraction", ylabel="Request CDF", title="Per-request KVzap compression")
    axis.set_xlim(0, 1)
    axis.grid(alpha=0.25)
    fig.suptitle(common_metadata, fontsize=7, y=0.01)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(figures_dir / "request_compression_cdf.png", dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Analysis output directory already exists: {args.output_dir}")
    if len(set(args.block_sizes)) != len(args.block_sizes):
        raise ValueError("--block-sizes contains duplicates")
    if not args.no_plots:
        try:
            import matplotlib  # noqa: F401
        except ImportError as error:
            raise RuntimeError(
                "Plotting requires matplotlib; install project dev dependencies or use --no-plots"
            ) from error
    traces = [validate_trace(path) for path in args.trace_dirs]
    compatibility_fields = ("model", "predictor_checkpoint", "threshold", "sliding_window")
    reference = tuple(traces[0]["manifest"][field] for field in compatibility_fields)
    for trace in traces[1:]:
        current = tuple(trace["manifest"][field] for field in compatibility_fields)
        if current != reference:
            raise ValueError(
                "All traces in one analysis must use the same model, predictor, threshold, and sliding window"
            )
    results = [analyze_trace(trace, args.block_sizes, args.threshold_deltas) for trace in traces]
    args.output_dir.mkdir(parents=True)

    outputs = {
        "request_summary.csv": [result["summary"] for result in results],
        "layer_head_retention.csv": [row for result in results for row in result["layer_head"]],
        "run_length_summary.csv": [row for result in results for row in result["run_summary"]],
        "run_length_distribution.csv": [row for result in results for row in result["run_distribution"]],
        "block_occupancy.csv": [row for result in results for row in result["block"]],
        "head_similarity.csv": [row for result in results for row in result["head_similarity"]],
        "score_threshold_sensitivity.csv": [row for result in results for row in result["score_sensitivity"]],
        "decoding_growth.csv": [row for result in results for row in result["decoding"]],
    }
    for filename, rows in outputs.items():
        write_csv(args.output_dir / filename, rows)

    analysis_config = {
        "source_experiment_ids": [trace["manifest"]["experiment_id"] for trace in traces],
        "block_sizes": args.block_sizes,
        "threshold_deltas": args.threshold_deltas,
        "plots_generated": not args.no_plots,
    }
    analysis_manifest = {
        "analysis_schema_version": "1.0",
        "analysis_git_commit": get_git_commit(),
        "analysis_config_hash": stable_hash(analysis_config),
        "source_trace_schema": SUPPORTED_SCHEMA,
        "trace_count": len(traces),
        "source_traces": [str(trace["trace_dir"]) for trace in traces],
        "source_git_commits": [trace["manifest"]["git_commit"] for trace in traces],
        **analysis_config,
        "notes": [
            "All compression metrics are logical or offline physical-layout estimates.",
            "Physical block estimates use keep-any allocation and report exact-span and padded variants.",
            "Prompt chunks with tokens_added > 1 are separated from one-token generation events.",
            "No accuracy, HBM traffic, runtime speedup, or measured physical allocation is inferred.",
        ],
    }
    (args.output_dir / "analysis_manifest.json").write_text(
        json.dumps(analysis_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not args.no_plots:
        write_figures(args.output_dir, traces, results)

    print(f"Analyzed {len(traces)} trace(s). Results: {args.output_dir}")
    for result in results:
        summary = result["summary"]
        print(
            f"  {summary['experiment_id']}: removed={summary['logical_removed_fraction']:.2%}, "
            f"factor={summary['logical_compression_factor']:.2f}x, "
            f"layer-CV={summary['layer_load_cv']:.2%}, "
            f"keep-Jaccard={summary['head_keep_jaccard_mean']:.3f}"
        )


if __name__ == "__main__":
    main()
