"""Static Route-A0 replay of validated KVzap masks into packed cold pages.

This consumes predictor-only prefill traces only.  It is deliberately a final
mask replay: it does not infer per-step admissions, allocator behaviour, HBM
traffic, latency, or throughput.

Data flow: validate existing trace -> replay each layer/head mask -> write
request, head and grouped CSVs. PackedKVSimulator is also used by the SnapKV
layout study; its shared implementation lives in kvpress.research.packing.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

# Keep these imports available from this historical entrypoint for callers.
from kvpress.research.packing import (
    PackedKVSimulator, group_metadata, percentile, replay_trace, replay_traces, safe_divide, summarize,
)
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





def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], columns: Iterable[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)










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
    request_rows, head_rows, summary_rows = replay_traces(
        traces, args.page_tokens, metadata, args.kv_bytes_per_token, args.metadata_bytes_per_page
    )
    args.output_dir.mkdir(parents=True)
    write_csv(args.output_dir / "request_packed_page_replay.csv", request_rows, REQUEST_COLUMNS)
    write_csv(args.output_dir / "layer_head_packed_page_replay.csv", head_rows, HEAD_COLUMNS)
    write_csv(args.output_dir / "packed_page_replay_summary.csv", summary_rows, SUMMARY_COLUMNS)
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
