"""Replay validated Route-A2 admissions into alternative packed cold-page sizes.

This is a pure offline accounting transform: it consumes recorded admission
events and never loads a model, re-scores tokens, or claims allocator/HBM data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kvpress.lifecycle import PackedColdPageState
from tools.validate_kvzap_decode_lifecycle_trace import read_csv, validate


EVENT_COLUMNS = (
    "request_id", "page_tokens", "model_call", "phase", "layer", "kv_head", "score_start", "q_len",
    "cache_tokens_after", "matured_tokens", "cold_admitted_tokens", "cold_dropped_tokens",
    "cold_page_allocations", "cold_page_seals", "tail_valid_count", "cold_logical_tokens",
    "cold_allocated_slots", "tail_waste_slots", "metadata_update_bytes",
)
FINAL_COLUMNS = (
    "request_id", "page_tokens", "layer", "kv_head", "cold_logical_tokens", "cold_allocated_slots",
    "cold_page_count", "tail_valid_count", "tail_waste_slots", "cold_page_allocations", "cold_page_seals",
)
SUMMARY_COLUMNS = (
    "request_id", "page_tokens", "layer_heads", "final_cache_tokens", "full_kv_slots",
    "hot_regular_slots", "cold_logical_tokens", "cold_allocated_slots", "cold_page_count",
    "tail_waste_slots", "fragmentation_fraction", "metadata_bytes", "ideal_packed_kv_slots",
    "physical_packed_kv_slots", "ideal_capacity_compression", "physical_capacity_compression",
    "declared_hot_to_cold_read_bytes", "declared_cold_write_bytes", "declared_metadata_update_bytes",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A2 packed-page replay over validated lifecycle events.")
    parser.add_argument("--lifecycle-dir", type=Path, required=True)
    parser.add_argument("--page-tokens", type=int, nargs="+", default=[16, 32, 64, 128])
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory only; existing outputs are never overwritten.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def replay(events: list[dict[str, str]], *, page_tokens: int, metadata_bytes_per_page: int, kv_bytes_per_token: int, window: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return event/final/summary rows from page-size-independent admissions."""
    if page_tokens <= 0:
        raise ValueError("page_tokens must be positive")
    grouped: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
    for row in events:
        grouped[(int(row["layer"]), int(row["kv_head"]))].append(row)
    event_rows: list[dict[str, Any]] = []
    final_rows: list[dict[str, Any]] = []
    total_matured = total_admitted = total_dropped = total_allocations = total_seals = 0
    final_cache_tokens: set[int] = set()
    request_ids = {row["request_id"] for row in events}
    if len(request_ids) != 1:
        raise ValueError("A lifecycle replay input must contain exactly one request_id")
    request_id = next(iter(request_ids))
    for (layer, head), rows in sorted(grouped.items()):
        rows.sort(key=lambda row: int(row["model_call"]))
        state = PackedColdPageState(page_tokens)
        for row in rows:
            admitted = int(row["cold_admitted_tokens"])
            allocations, seals = state.append(admitted)
            matured, dropped = int(row["matured_tokens"]), int(row["cold_dropped_tokens"])
            total_matured += matured
            total_admitted += admitted
            total_dropped += dropped
            total_allocations += allocations
            total_seals += seals
            event_rows.append({
                "request_id": request_id, "page_tokens": page_tokens, "model_call": int(row["model_call"]),
                "phase": row["phase"], "layer": layer, "kv_head": head, "score_start": int(row["score_start"]),
                "q_len": int(row["q_len"]), "cache_tokens_after": int(row["cache_tokens_after"]),
                "matured_tokens": matured, "cold_admitted_tokens": admitted, "cold_dropped_tokens": dropped,
                "cold_page_allocations": allocations, "cold_page_seals": seals, "tail_valid_count": state.tail_valid_count,
                "cold_logical_tokens": state.logical_tokens, "cold_allocated_slots": state.allocated_slots,
                "tail_waste_slots": state.allocated_slots - state.logical_tokens,
                "metadata_update_bytes": allocations * metadata_bytes_per_page,
            })
        final_cache_tokens.add(int(rows[-1]["cache_tokens_after"]))
        final_rows.append({
            "request_id": request_id, "page_tokens": page_tokens, "layer": layer, "kv_head": head,
            "cold_logical_tokens": state.logical_tokens, "cold_allocated_slots": state.allocated_slots,
            "cold_page_count": state.page_count, "tail_valid_count": state.tail_valid_count,
            "tail_waste_slots": state.allocated_slots - state.logical_tokens,
            "cold_page_allocations": state.allocation_count, "cold_page_seals": state.seal_count,
        })
    if len(final_cache_tokens) != 1:
        raise ValueError("Layer/head final cache lengths disagree")
    cold_logical = sum(int(row["cold_logical_tokens"]) for row in final_rows)
    cold_allocated = sum(int(row["cold_allocated_slots"]) for row in final_rows)
    cold_pages = sum(int(row["cold_page_count"]) for row in final_rows)
    heads = len(final_rows)
    full_slots = next(iter(final_cache_tokens)) * heads
    hot_slots = min(window, next(iter(final_cache_tokens))) * heads
    ideal_slots = hot_slots + cold_logical
    physical_slots = hot_slots + cold_allocated
    summary = {
        "request_id": request_id, "page_tokens": page_tokens, "layer_heads": heads,
        "final_cache_tokens": next(iter(final_cache_tokens)), "full_kv_slots": full_slots,
        "hot_regular_slots": hot_slots, "cold_logical_tokens": cold_logical,
        "cold_allocated_slots": cold_allocated, "cold_page_count": cold_pages,
        "tail_waste_slots": cold_allocated - cold_logical,
        "fragmentation_fraction": (cold_allocated - cold_logical) / cold_allocated if cold_allocated else 0.0,
        "metadata_bytes": cold_pages * metadata_bytes_per_page, "ideal_packed_kv_slots": ideal_slots,
        "physical_packed_kv_slots": physical_slots,
        "ideal_capacity_compression": full_slots / ideal_slots if ideal_slots else 0.0,
        "physical_capacity_compression": full_slots / physical_slots if physical_slots else 0.0,
        "declared_hot_to_cold_read_bytes": sum(int(row["matured_tokens"]) for row in event_rows) * kv_bytes_per_token,
        "declared_cold_write_bytes": total_admitted * kv_bytes_per_token,
        "declared_metadata_update_bytes": total_allocations * metadata_bytes_per_page,
        "_total_dropped": total_dropped, "_total_seals": total_seals,
    }
    if total_matured != total_admitted + total_dropped:
        raise AssertionError("Replay admission conservation failed")
    return event_rows, final_rows, summary


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    if not args.page_tokens or any(page <= 0 for page in args.page_tokens) or len(set(args.page_tokens)) != len(args.page_tokens):
        raise ValueError("--page-tokens must be unique positive integers")
    validation = validate(args.lifecycle_dir)
    manifest_path = args.lifecycle_dir / "lifecycle_manifest.json"
    events_path = args.lifecycle_dir / "lifecycle_events.csv"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    events = read_csv(events_path)
    metadata, kv_bytes, window = int(manifest["metadata_bytes_per_cold_page"]), int(manifest["kv_bytes_per_layer_head_token"]), int(manifest["sliding_window"])
    args.output_dir.mkdir(parents=True, exist_ok=False)
    all_events: list[dict[str, Any]] = []
    all_final: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for page in args.page_tokens:
        event_rows, final_rows, summary = replay(events, page_tokens=page, metadata_bytes_per_page=metadata, kv_bytes_per_token=kv_bytes, window=window)
        all_events.extend(event_rows)
        all_final.extend(final_rows)
        summaries.append({key: value for key, value in summary.items() if not key.startswith("_")})
    paths = {"events": args.output_dir / "lifecycle_page_replay_events.csv", "final": args.output_dir / "lifecycle_page_replay_final.csv", "summary": args.output_dir / "lifecycle_page_replay_summary.csv"}
    write_csv(paths["events"], EVENT_COLUMNS, all_events)
    write_csv(paths["final"], FINAL_COLUMNS, all_final)
    write_csv(paths["summary"], SUMMARY_COLUMNS, summaries)
    replay_manifest = {
        "schema_version": "kvzap-route-a2-page-replay-1.0", "created_at": datetime.now(timezone.utc).isoformat(),
        "source_lifecycle_dir": str(args.lifecycle_dir), "source_artifact_sha256": {"lifecycle_manifest": sha256(manifest_path), "lifecycle_events": sha256(events_path)},
        "source_validation": validation, "request_id": manifest["request_id"], "page_tokens": args.page_tokens,
        "sliding_window": window, "metadata_bytes_per_cold_page": metadata, "kv_bytes_per_layer_head_token": kv_bytes,
        "notes": ["Pure offline replay of already-recorded cold admissions; it does not load a model or re-score tokens.", "Capacity and byte fields are declared accounting values, not allocator, HBM, latency, throughput, or break-even measurements."],
    }
    paths["manifest"] = args.output_dir / "lifecycle_page_replay_manifest.json"
    paths["manifest"].write_text(json.dumps(replay_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A2 page replay complete for {len(args.page_tokens)} page sizes.")
    for name, path in paths.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
