"""Estimate page-layout cost for original and block-coalesced KVzap masks.

This is a model-free Phase-3 estimator.  It consumes validated predictor-only
traces and reports two explicitly different storage models:

* ``packed``: an optimistic lower bound that compacts arbitrary kept tokens
  within each layer/head before page allocation;
* ``timeline``: a page-aligned layout over original token positions, where a
  page is allocated if it contains at least one kept cold token.

Neither model measures allocator behaviour, HBM traffic, latency, or accuracy.
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

from tools.analyze_kvzap_trace import get_git_commit, load_pilot_metadata, validate_trace
from tools.evaluate_kvzap_structured_masks import coalesced_drop_mask, metadata_for, safe_divide


POLICIES = ("original", "b4_m0", "b4_m025")
REQUEST_COLUMNS = (
    "trace_id", "request_id", "category", "task", "length_bucket", "policy_id", "page_tokens",
    "logical_total_tokens", "logical_kept_tokens", "logical_removed_fraction",
    "packed_capacity_tokens", "timeline_capacity_tokens",
    "packed_compression_factor", "timeline_compression_factor",
    "packed_page_count", "timeline_page_count",
    "packed_metadata_bytes", "timeline_metadata_bytes",
    "packed_read_bytes_proxy", "timeline_read_bytes_proxy",
    "timeline_page_occupancy", "timeline_head_pages_p50", "timeline_head_pages_p95",
    "timeline_head_pages_max", "timeline_head_pages_cv",
)
HEAD_COLUMNS = (
    "trace_id", "request_id", "policy_id", "page_tokens", "layer", "kv_head", "cold_kept_tokens",
    "packed_pages", "timeline_pages", "timeline_page_occupancy",
)
SUMMARY_COLUMNS = (
    "group_type", "group_value", "policy_id", "page_tokens", "request_count",
    "logical_removed_fraction_weighted", "packed_compression_factor_weighted",
    "timeline_compression_factor_weighted", "packed_metadata_bytes_per_request_mean",
    "timeline_metadata_bytes_per_request_mean", "packed_read_bytes_proxy_per_request_mean",
    "timeline_read_bytes_proxy_per_request_mean", "timeline_page_occupancy_mean",
    "timeline_head_pages_p95_mean", "timeline_head_pages_max_mean",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline KVzap page-layout and HBM-read proxy estimator.")
    parser.add_argument("trace_dirs", nargs="+", type=Path, help="Validated predictor-only trace directories.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; never overwritten.")
    parser.add_argument("--pilot-manifest", type=Path, help="Optional manifest for grouped summaries.")
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=list(POLICIES))
    parser.add_argument("--page-tokens", nargs="+", type=int, default=[4, 16, 32, 64])
    parser.add_argument(
        "--kv-bytes-per-token", type=int, default=512,
        help="Bytes for K+V of one layer/head/token; 512 is bf16 K,V with head_dim=128.",
    )
    parser.add_argument("--metadata-bytes-per-page", type=int, default=16)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], columns: Iterable[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def percentile(values: np.ndarray, q: float) -> float:
    return float(np.percentile(values, q, method="higher")) if values.size else math.nan


def make_policy(policy_id: str, scores: np.ndarray, valid: np.ndarray, original: np.ndarray, threshold: float, window: int) -> np.ndarray:
    if policy_id == "original":
        return original
    if policy_id == "b4_m0":
        return coalesced_drop_mask(scores, valid, original, threshold, window, 4, 0.0)
    if policy_id == "b4_m025":
        return coalesced_drop_mask(scores, valid, original, threshold, window, 4, 0.25)
    raise ValueError(f"Unsupported policy: {policy_id}")


def page_counts(cold_keep: np.ndarray, page_tokens: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return cold kept count, packed pages, and timeline pages for each L/H."""
    if page_tokens <= 0:
        raise ValueError("page_tokens must be positive")
    cold_kept = cold_keep.sum(axis=-1, dtype=np.int64)
    packed_pages = (cold_kept + page_tokens - 1) // page_tokens
    padding = (-cold_keep.shape[-1]) % page_tokens
    padded = np.pad(cold_keep, ((0, 0), (0, 0), (0, padding)), constant_values=False)
    timeline_pages = padded.reshape(*padded.shape[:2], -1, page_tokens).any(axis=-1).sum(axis=-1, dtype=np.int64)
    return cold_kept, packed_pages, timeline_pages


def layout_rows(
    trace: dict[str, Any], policy_id: str, page_tokens: int, kv_bytes_per_token: int, metadata_bytes_per_page: int,
    metadata: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest, request = trace["manifest"], trace["request"]
    scores, valid, original = trace["scores"], trace["valid"], trace["final"]
    window = int(manifest["sliding_window"])
    if scores.shape[-1] <= window:
        raise ValueError(f"Trace {trace['trace_dir']} has no mature cold tokens")
    final_drop = make_policy(policy_id, scores, valid, original, float(manifest["threshold"]), window)
    total = int(valid.sum())
    kept = int(np.logical_and(~final_drop, valid).sum())
    hot_valid = valid[..., -window:].sum(axis=-1, dtype=np.int64)
    cold_keep = np.logical_and(~final_drop[..., :-window], valid[..., :-window])
    cold_kept, packed_pages, timeline_pages = page_counts(cold_keep, page_tokens)
    packed_capacity = int(hot_valid.sum() + (packed_pages * page_tokens).sum())
    timeline_capacity = int(hot_valid.sum() + (timeline_pages * page_tokens).sum())
    packed_count, timeline_count = int(packed_pages.sum()), int(timeline_pages.sum())
    occupancy = safe_divide(int(cold_kept.sum()), timeline_count * page_tokens)
    timeline_values = timeline_pages.reshape(-1).astype(np.float64)
    timeline_mean = float(timeline_values.mean())
    base = {
        "trace_id": trace["trace_id"], "request_id": request["request_id"],
        **metadata_for(request["request_id"], metadata), "policy_id": policy_id, "page_tokens": page_tokens,
        "logical_total_tokens": total, "logical_kept_tokens": kept, "logical_removed_fraction": 1 - safe_divide(kept, total),
        "packed_capacity_tokens": packed_capacity, "timeline_capacity_tokens": timeline_capacity,
        "packed_compression_factor": safe_divide(total, packed_capacity),
        "timeline_compression_factor": safe_divide(total, timeline_capacity),
        "packed_page_count": packed_count, "timeline_page_count": timeline_count,
        "packed_metadata_bytes": packed_count * metadata_bytes_per_page,
        "timeline_metadata_bytes": timeline_count * metadata_bytes_per_page,
        "packed_read_bytes_proxy": packed_capacity * kv_bytes_per_token + packed_count * metadata_bytes_per_page,
        "timeline_read_bytes_proxy": timeline_capacity * kv_bytes_per_token + timeline_count * metadata_bytes_per_page,
        "timeline_page_occupancy": occupancy,
        "timeline_head_pages_p50": percentile(timeline_values, 50),
        "timeline_head_pages_p95": percentile(timeline_values, 95),
        "timeline_head_pages_max": int(timeline_values.max()),
        "timeline_head_pages_cv": float(timeline_values.std() / timeline_mean) if timeline_mean else math.nan,
    }
    head_rows = []
    for layer in range(cold_keep.shape[0]):
        for head in range(cold_keep.shape[1]):
            pages = int(timeline_pages[layer, head])
            head_rows.append({
                "trace_id": trace["trace_id"], "request_id": request["request_id"], "policy_id": policy_id,
                "page_tokens": page_tokens, "layer": layer, "kv_head": head,
                "cold_kept_tokens": int(cold_kept[layer, head]), "packed_pages": int(packed_pages[layer, head]),
                "timeline_pages": pages,
                "timeline_page_occupancy": safe_divide(int(cold_kept[layer, head]), pages * page_tokens),
            })
    return base, head_rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for kind, value in (("all", "all"), ("category", row["category"]), ("task", row["task"]), ("length_bucket", row["length_bucket"])):
            groups[(kind, value, row["policy_id"], int(row["page_tokens"]))].append(row)
    output = []
    for (kind, value, policy, page), values in sorted(groups.items()):
        total = sum(int(row["logical_total_tokens"]) for row in values)
        kept = sum(int(row["logical_kept_tokens"]) for row in values)
        packed = sum(int(row["packed_capacity_tokens"]) for row in values)
        timeline = sum(int(row["timeline_capacity_tokens"]) for row in values)
        output.append({
            "group_type": kind, "group_value": value, "policy_id": policy, "page_tokens": page,
            "request_count": len(values), "logical_removed_fraction_weighted": 1 - safe_divide(kept, total),
            "packed_compression_factor_weighted": safe_divide(total, packed),
            "timeline_compression_factor_weighted": safe_divide(total, timeline),
            "packed_metadata_bytes_per_request_mean": float(np.mean([row["packed_metadata_bytes"] for row in values])),
            "timeline_metadata_bytes_per_request_mean": float(np.mean([row["timeline_metadata_bytes"] for row in values])),
            "packed_read_bytes_proxy_per_request_mean": float(np.mean([row["packed_read_bytes_proxy"] for row in values])),
            "timeline_read_bytes_proxy_per_request_mean": float(np.mean([row["timeline_read_bytes_proxy"] for row in values])),
            "timeline_page_occupancy_mean": float(np.mean([row["timeline_page_occupancy"] for row in values])),
            "timeline_head_pages_p95_mean": float(np.mean([row["timeline_head_pages_p95"] for row in values])),
            "timeline_head_pages_max_mean": float(np.mean([row["timeline_head_pages_max"] for row in values])),
        })
    return output


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    if not args.page_tokens or any(value <= 0 for value in args.page_tokens) or len(set(args.page_tokens)) != len(args.page_tokens):
        raise ValueError("--page-tokens must contain unique positive integers")
    if len(set(args.policies)) != len(args.policies):
        raise ValueError("--policies must not contain duplicates")
    if args.kv_bytes_per_token <= 0 or args.metadata_bytes_per_page < 0:
        raise ValueError("Byte parameters must be non-negative, and KV bytes must be positive")
    _, metadata = load_pilot_metadata(args.pilot_manifest) if args.pilot_manifest else (None, {})
    traces = [validate_trace(path) for path in args.trace_dirs]
    if not all(trace["predictor_only"] for trace in traces):
        raise ValueError("This estimator accepts predictor-only traces only")
    args.output_dir.mkdir(parents=True)
    requests: list[dict[str, Any]] = []
    heads: list[dict[str, Any]] = []
    for trace in traces:
        for policy in args.policies:
            for page in args.page_tokens:
                request_row, head_rows = layout_rows(trace, policy, page, args.kv_bytes_per_token, args.metadata_bytes_per_page, metadata)
                requests.append(request_row)
                heads.extend(head_rows)
    write_csv(args.output_dir / "request_layout_cost.csv", requests, REQUEST_COLUMNS)
    write_csv(args.output_dir / "layer_head_page_cost.csv", heads, HEAD_COLUMNS)
    write_csv(args.output_dir / "layout_cost_summary.csv", summarize(requests), SUMMARY_COLUMNS)
    manifest = {
        "schema_version": "kvzap-physical-layout-estimate-1.0", "git_commit": get_git_commit(),
        "trace_count": len(traces), "source_traces": [str(trace["trace_dir"]) for trace in traces],
        "source_trace_manifest_sha256": [sha256(trace["trace_dir"] / "manifest.json") for trace in traces],
        "pilot_manifest": None if args.pilot_manifest is None else str(args.pilot_manifest),
        "pilot_manifest_sha256": None if args.pilot_manifest is None else sha256(args.pilot_manifest),
        "policies": args.policies, "page_tokens": args.page_tokens, "kv_bytes_per_token": args.kv_bytes_per_token,
        "metadata_bytes_per_page": args.metadata_bytes_per_page,
        "notes": [
            "Packed layout is an optimistic per-layer/head token-compaction lower bound.",
            "Timeline layout allocates every original-position page containing one or more kept cold tokens.",
            "Read-byte values are one-query all-active-KV proxies, not measured HBM traffic or latency.",
            "No result in this directory licenses accuracy, measured memory, throughput, or speed claims.",
        ],
    }
    (args.output_dir / "evaluation_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Estimated {len(traces)} trace(s). Results: {args.output_dir}")


if __name__ == "__main__":
    main()
