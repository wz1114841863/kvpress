"""Replay validated Route-A2 admissions into alternative packed cold-page sizes.

This is a pure offline accounting transform: it consumes recorded admission
events and never loads a model, re-scores tokens, or claims allocator/HBM data.
The events contain modeled admission decisions derived during read-only
observation; they are not measurements from a physical packing controller.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Re-export the original names for existing callers.
from kvpress.research.lifecycle import PackedColdPageState, replay, replay_page_sizes
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
    all_events, all_final, summaries = replay_page_sizes(
        events, page_sizes=args.page_tokens, metadata_bytes_per_page=metadata,
        kv_bytes_per_token=kv_bytes, window=window,
    )
    args.output_dir.mkdir(parents=True, exist_ok=False)
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
