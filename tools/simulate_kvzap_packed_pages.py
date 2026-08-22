"""Static Route-A0 replay of validated KVzap masks into packed cold pages.

This consumes predictor-only prefill traces only.  It is deliberately a final
mask replay: it does not infer per-step admissions, allocator behaviour, HBM
traffic, latency, or throughput.
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


REQUEST_COLUMNS = (
    "trace_id", "request_id", "category", "task", "length_bucket", "page_tokens",
    "logical_total_kv", "logical_kept_kv", "logical_removed_fraction",
    "full_kv_allocated_slots", "ideal_packed_kvzap_slots", "physical_allocated_slots",
    "hot_slots", "cold_logical_kept_slots", "cold_allocated_slots", "tail_waste_slots",
    "cold_page_count", "metadata_bytes", "hot_kv_bytes", "cold_kv_bytes", "total_kv_bytes",
    "total_storage_bytes_including_metadata", "ideal_packed_kvzap_bytes", "full_kv_bytes",
    "physical_compression_factor", "ideal_packed_compression_factor", "fragmentation_fraction",
    "head_capacity_slots_p50", "head_capacity_slots_p95", "head_capacity_slots_p99", "head_capacity_slots_max",
    "head_page_count_p50", "head_page_count_p95", "head_page_count_p99", "head_page_count_max",
)
HEAD_COLUMNS = (
    "trace_id", "request_id", "page_tokens", "layer", "kv_head", "hot_slots",
    "cold_logical_kept_slots", "cold_allocated_slots", "tail_waste_slots", "cold_page_count",
    "tail_page_valid_slots", "metadata_bytes", "hot_kv_bytes", "cold_kv_bytes", "total_kv_bytes",
    "fragmentation_fraction",
)
SUMMARY_COLUMNS = (
    "group_type", "group_value", "page_tokens", "request_count", "logical_total_kv",
    "logical_kept_kv", "physical_allocated_slots", "cold_page_count", "metadata_bytes",
    "full_kv_bytes", "ideal_packed_kvzap_bytes", "total_kv_bytes",
    "physical_compression_factor", "ideal_packed_compression_factor", "fragmentation_fraction",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Static Route-A0 packed cold-page replay for validated KVzap traces.")
    parser.add_argument("trace_dirs", nargs="+", type=Path, help="Validated predictor-only trace directories.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; existing directories are never overwritten.")
    parser.add_argument("--pilot-manifest", type=Path, help="Optional pilot preparation manifest for grouped summaries.")
    parser.add_argument("--page-tokens", nargs="+", type=int, default=[16, 32, 64, 128])
    parser.add_argument("--cache-dtype", default="bfloat16", help="Declared cache dtype label recorded in provenance.")
    parser.add_argument("--kv-bytes-per-token", type=int, default=512, help="Declared bytes for one layer/head K+V token.")
    parser.add_argument("--metadata-bytes-per-page", type=int, default=16, help="Declared cold-page metadata bytes.")
    return parser.parse_args()


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else math.nan


def percentile(values: np.ndarray, q: float) -> float:
    return float(np.percentile(values, q, method="higher")) if values.size else math.nan


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], columns: Iterable[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


class PackedKVSimulator:
    """Replay a final cold keep mask into independent append-only L/H page lists."""

    def __init__(self, page_tokens: int, kv_bytes_per_token: int, metadata_bytes_per_page: int) -> None:
        if page_tokens <= 0 or kv_bytes_per_token <= 0 or metadata_bytes_per_page < 0:
            raise ValueError("page_tokens and kv_bytes_per_token must be positive; metadata bytes must be non-negative")
        self.page_tokens = page_tokens
        self.kv_bytes_per_token = kv_bytes_per_token
        self.metadata_bytes_per_page = metadata_bytes_per_page

    def replay(self, final_drop: np.ndarray, valid: np.ndarray, window: int) -> dict[str, np.ndarray]:
        """Return per-head packed-page state without modifying the supplied mask."""
        if final_drop.shape != valid.shape or final_drop.ndim != 3:
            raise ValueError("final_drop and valid must be same-shape [L,H,T] arrays")
        tokens = final_drop.shape[-1]
        if window < 0 or window > tokens:
            raise ValueError(f"invalid window {window} for T={tokens}")
        if np.any(final_drop[..., tokens - window :] & valid[..., tokens - window :]) if window else False:
            raise ValueError("protected hot-window token was dropped")
        hot_valid = valid[..., tokens - window :] if window else valid[..., :0]
        cold_keep = (~final_drop[..., : tokens - window]) & valid[..., : tokens - window]
        hot_slots = hot_valid.sum(axis=-1, dtype=np.int64)
        cold_kept = cold_keep.sum(axis=-1, dtype=np.int64)
        page_count = (cold_kept + self.page_tokens - 1) // self.page_tokens
        cold_allocated = page_count * self.page_tokens
        tail_waste = cold_allocated - cold_kept
        tail_valid = np.where(page_count > 0, ((cold_kept - 1) % self.page_tokens) + 1, 0)
        return {
            "hot_slots": hot_slots, "cold_logical_kept_slots": cold_kept,
            "cold_allocated_slots": cold_allocated, "tail_waste_slots": tail_waste,
            "cold_page_count": page_count, "tail_page_valid_slots": tail_valid,
        }


def group_metadata(request_id: str, metadata: dict[str, dict[str, Any]]) -> dict[str, str]:
    row = metadata.get(request_id)
    if row is None:
        return {"category": "unknown", "task": "unknown", "length_bucket": "unknown"}
    low, high = row["length_bucket"]
    return {"category": str(row["category"]), "task": f"{row['category']}/{row['task']}", "length_bucket": f"[{low},{high})"}


def replay_trace(trace: dict[str, Any], simulator: PackedKVSimulator, metadata: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest, request = trace["manifest"], trace["request"]
    final, valid = trace["final"], trace["valid"]
    state = simulator.replay(final, valid, int(manifest["sliding_window"]))
    hot = state["hot_slots"]
    cold_kept = state["cold_logical_kept_slots"]
    cold_allocated = state["cold_allocated_slots"]
    pages = state["cold_page_count"]
    tail_waste = state["tail_waste_slots"]
    total = int(valid.sum())
    logical_kept = int(((~final) & valid).sum())
    physical = hot + cold_allocated
    ideal = hot + cold_kept
    page_values, capacity_values = pages.reshape(-1), physical.reshape(-1)
    base = {
        "trace_id": trace["trace_id"], "request_id": request["request_id"],
        **group_metadata(request["request_id"], metadata), "page_tokens": simulator.page_tokens,
        "logical_total_kv": total, "logical_kept_kv": logical_kept, "logical_removed_fraction": 1 - safe_divide(logical_kept, total),
        "full_kv_allocated_slots": total, "ideal_packed_kvzap_slots": int(ideal.sum()), "physical_allocated_slots": int(physical.sum()),
        "hot_slots": int(hot.sum()), "cold_logical_kept_slots": int(cold_kept.sum()), "cold_allocated_slots": int(cold_allocated.sum()),
        "tail_waste_slots": int(tail_waste.sum()), "cold_page_count": int(pages.sum()), "metadata_bytes": int(pages.sum()) * simulator.metadata_bytes_per_page,
        "hot_kv_bytes": int(hot.sum()) * simulator.kv_bytes_per_token, "cold_kv_bytes": int(cold_allocated.sum()) * simulator.kv_bytes_per_token,
        "total_kv_bytes": int(physical.sum()) * simulator.kv_bytes_per_token,
        "total_storage_bytes_including_metadata": int(physical.sum()) * simulator.kv_bytes_per_token + int(pages.sum()) * simulator.metadata_bytes_per_page,
        "ideal_packed_kvzap_bytes": int(ideal.sum()) * simulator.kv_bytes_per_token, "full_kv_bytes": total * simulator.kv_bytes_per_token,
        "physical_compression_factor": safe_divide(total, int(physical.sum())), "ideal_packed_compression_factor": safe_divide(total, int(ideal.sum())),
        "fragmentation_fraction": safe_divide(int(tail_waste.sum()), int(cold_allocated.sum())),
        "head_capacity_slots_p50": percentile(capacity_values, 50), "head_capacity_slots_p95": percentile(capacity_values, 95), "head_capacity_slots_p99": percentile(capacity_values, 99), "head_capacity_slots_max": int(capacity_values.max()),
        "head_page_count_p50": percentile(page_values, 50), "head_page_count_p95": percentile(page_values, 95), "head_page_count_p99": percentile(page_values, 99), "head_page_count_max": int(page_values.max()),
    }
    heads = []
    for layer in range(final.shape[0]):
        for head_index in range(final.shape[1]):
            head_hot, head_cold, head_allocated, head_pages = (int(hot[layer, head_index]), int(cold_kept[layer, head_index]), int(cold_allocated[layer, head_index]), int(pages[layer, head_index]))
            heads.append({
                "trace_id": trace["trace_id"], "request_id": request["request_id"], "page_tokens": simulator.page_tokens,
                "layer": layer, "kv_head": head_index, "hot_slots": head_hot, "cold_logical_kept_slots": head_cold,
                "cold_allocated_slots": head_allocated, "tail_waste_slots": int(tail_waste[layer, head_index]), "cold_page_count": head_pages,
                "tail_page_valid_slots": int(state["tail_page_valid_slots"][layer, head_index]), "metadata_bytes": head_pages * simulator.metadata_bytes_per_page,
                "hot_kv_bytes": head_hot * simulator.kv_bytes_per_token, "cold_kv_bytes": head_allocated * simulator.kv_bytes_per_token,
                "total_kv_bytes": (head_hot + head_allocated) * simulator.kv_bytes_per_token,
                "fragmentation_fraction": safe_divide(int(tail_waste[layer, head_index]), head_allocated),
            })
    return base, heads


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for kind, value in (("all", "all"), ("category", row["category"]), ("task", row["task"]), ("length_bucket", row["length_bucket"])):
            groups[(kind, value, int(row["page_tokens"]))].append(row)
    output = []
    for (kind, value, page), values in sorted(groups.items()):
        total = sum(int(row["logical_total_kv"]) for row in values)
        kept = sum(int(row["logical_kept_kv"]) for row in values)
        physical = sum(int(row["physical_allocated_slots"]) for row in values)
        ideal = sum(int(row["ideal_packed_kvzap_slots"]) for row in values)
        cold_allocated = sum(int(row["cold_allocated_slots"]) for row in values)
        tail = sum(int(row["tail_waste_slots"]) for row in values)
        output.append({"group_type": kind, "group_value": value, "page_tokens": page, "request_count": len(values), "logical_total_kv": total, "logical_kept_kv": kept, "physical_allocated_slots": physical, "cold_page_count": sum(int(row["cold_page_count"]) for row in values), "metadata_bytes": sum(int(row["metadata_bytes"]) for row in values), "full_kv_bytes": sum(int(row["full_kv_bytes"]) for row in values), "ideal_packed_kvzap_bytes": sum(int(row["ideal_packed_kvzap_bytes"]) for row in values), "total_kv_bytes": sum(int(row["total_kv_bytes"]) for row in values), "physical_compression_factor": safe_divide(total, physical), "ideal_packed_compression_factor": safe_divide(total, ideal), "fragmentation_fraction": safe_divide(tail, cold_allocated)})
    return output


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    if not args.page_tokens or len(set(args.page_tokens)) != len(args.page_tokens) or any(page <= 0 for page in args.page_tokens):
        raise ValueError("--page-tokens must contain unique positive integers")
    if args.kv_bytes_per_token <= 0 or args.metadata_bytes_per_page < 0:
        raise ValueError("byte parameters are invalid")
    _, metadata = load_pilot_metadata(args.pilot_manifest) if args.pilot_manifest else (None, {})
    traces = [validate_trace(path) for path in args.trace_dirs]
    if not all(trace["predictor_only"] for trace in traces):
        raise ValueError("Route-A0 accepts predictor-only traces only")
    args.output_dir.mkdir(parents=True)
    request_rows: list[dict[str, Any]] = []
    head_rows: list[dict[str, Any]] = []
    for page in args.page_tokens:
        simulator = PackedKVSimulator(page, args.kv_bytes_per_token, args.metadata_bytes_per_page)
        for trace in traces:
            request, heads = replay_trace(trace, simulator, metadata)
            request_rows.append(request)
            head_rows.extend(heads)
    write_csv(args.output_dir / "request_packed_page_replay.csv", request_rows, REQUEST_COLUMNS)
    write_csv(args.output_dir / "layer_head_packed_page_replay.csv", head_rows, HEAD_COLUMNS)
    write_csv(args.output_dir / "packed_page_replay_summary.csv", summarize(request_rows), SUMMARY_COLUMNS)
    provenance = [{
        "trace_dir": str(trace["trace_dir"]),
        "manifest_sha256": sha256(trace["trace_dir"] / "manifest.json"),
        "score_mask_sha256": sha256(trace["trace_dir"] / "score_mask.npz"),
        "model": trace["manifest"].get("model"), "model_revision": trace["manifest"].get("model_revision"),
        "predictor_checkpoint": trace["manifest"].get("predictor_checkpoint"),
        "predictor_revision": trace["manifest"].get("predictor_revision"),
        "threshold": trace["manifest"].get("threshold"), "sliding_window": trace["manifest"].get("sliding_window"),
        "source_git_commit": trace["manifest"].get("git_commit"), "config_hash": trace["manifest"].get("config_hash"),
    } for trace in traces]
    manifest = {"schema_version": "kvzap-route-a0-static-packed-page-replay-1.0", "git_commit": get_git_commit(), "trace_count": len(traces), "source_traces": provenance, "pilot_manifest": None if args.pilot_manifest is None else str(args.pilot_manifest), "pilot_manifest_sha256": None if args.pilot_manifest is None else sha256(args.pilot_manifest), "page_tokens": args.page_tokens, "cache_dtype": args.cache_dtype, "kv_bytes_per_layer_head_token": args.kv_bytes_per_token, "metadata_bytes_per_cold_page": args.metadata_bytes_per_page, "storage_model": "hot window stored regularly; mature retained tokens append to independent per-(layer,kv_head) cold pages", "baselines": {"full_kv": "all valid L/H/T slots", "ideal_packed_kvzap": "hot slots plus exact cold kept slots; zero cold tail waste and metadata"}, "notes": ["Static final-mask replay only; it is not a dynamic admission trace.", "Byte fields are declared storage accounting assumptions, not HBM measurements.", "No allocator, latency, throughput, break-even, or accuracy conclusion is supported."]}
    (args.output_dir / "replay_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Replayed {len(traces)} predictor-only trace(s): {args.output_dir}")


if __name__ == "__main__":
    main()
