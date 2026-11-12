#!/usr/bin/env python3
"""Static packed-page opportunity analysis for a completed SnapKV Route-A P0 stream."""

from __future__ import annotations

from kvpress.research.snapkv import decisions_to_final_drop, replay_p1

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from kvpress.route_a_frontend_contract import (
    FRONTEND_DECISION_STREAM_SCHEMA,
    SNAPKV_FRONTEND_NAME,
    SNAPKV_TERMINAL_EPOCH,
    FrontendDecision,
    load_frontend_decision_stream,
    validate_snapkv_p0_contract,
)
from tools.analyze_kvzap_trace import get_git_commit, stable_hash
from kvpress.research.packing import PackedKVSimulator, percentile, safe_divide


P1_SCHEMA = "route-a-snapkv-p1-static-packed-opportunity-1.0"
P0_SCHEMA = "route-a-snapkv-p0-contract-gate-1.0"
P0_MANIFEST_NAME = "snapkv_p0_contract_manifest.json"
P0_STREAM_NAME = "snapkv_prefill_terminal_decisions.npz"

REQUEST_COLUMNS = (
    "request_id",
    "frontend_name",
    "decision_epoch",
    "page_tokens",
    "resident_window",
    "logical_total_slots",
    "logical_kept_slots",
    "terminal_drop_slots",
    "hot_slots",
    "cold_logical_kept_slots",
    "cold_allocated_slots",
    "tail_waste_slots",
    "cold_page_count",
    "metadata_bytes_declared",
    "full_kv_declared_bytes",
    "ideal_packed_declared_bytes",
    "physical_packed_declared_bytes",
    "total_declared_bytes_including_metadata",
    "ideal_packed_slots",
    "physical_allocated_slots",
    "full_to_ideal_packed_factor",
    "full_to_physical_packed_factor",
    "tail_fragmentation_fraction",
    "physical_over_ideal_slot_fraction",
    "head_page_count_p50",
    "head_page_count_p95",
    "head_page_count_p99",
    "head_page_count_max",
)

HEAD_COLUMNS = (
    "request_id",
    "page_tokens",
    "resident_window",
    "layer",
    "kv_head",
    "logical_total_slots",
    "logical_kept_slots",
    "terminal_drop_slots",
    "hot_slots",
    "cold_logical_kept_slots",
    "cold_allocated_slots",
    "tail_waste_slots",
    "cold_page_count",
    "tail_page_valid_slots",
    "metadata_bytes_declared",
    "full_kv_declared_bytes",
    "ideal_packed_declared_bytes",
    "physical_packed_declared_bytes",
    "tail_fragmentation_fraction",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P1 static SnapKV terminal-stream packed-page opportunity analysis; no model execution or hardware claim."
    )
    parser.add_argument("--p0-dir", type=Path, required=True, help="Completed SnapKV P0 output directory.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    parser.add_argument("--page-tokens", nargs="+", type=int, default=[16, 32, 64, 128])
    parser.add_argument(
        "--resident-window",
        type=int,
        help="Must equal P0 SnapKV observation window; default is the P0 declared window.",
    )
    parser.add_argument("--cache-dtype", default="bfloat16", help="Declared accounting label only.")
    parser.add_argument("--kv-bytes-per-token", type=int, default=512, help="Declared K+V accounting bytes per layer/KV-head token.")
    parser.add_argument("--metadata-bytes-per-page", type=int, default=16, help="Declared static page-metadata accounting bytes.")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], columns: Iterable[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def load_p0_input(p0_dir: Path) -> tuple[dict[str, Any], list[FrontendDecision], int, float]:
    """Load a hash-bound accepted P0 source and revalidate its terminal stream."""
    manifest_path = p0_dir / P0_MANIFEST_NAME
    stream_path = p0_dir / P0_STREAM_NAME
    if not manifest_path.is_file() or not stream_path.is_file():
        raise FileNotFoundError("P1 requires the completed P0 manifest and terminal decision stream")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != P0_SCHEMA or manifest.get("status") != "complete":
        raise ValueError("P1 requires a complete SnapKV P0 manifest")
    if manifest.get("decision_stream_schema") != FRONTEND_DECISION_STREAM_SCHEMA:
        raise ValueError("P0 decision-stream schema is incompatible with P1")
    if manifest.get("decision_stream_file") != P0_STREAM_NAME:
        raise ValueError("P0 terminal stream filename is not the registered P1 input")
    if manifest.get("decision_stream_sha256") != sha256_file(stream_path):
        raise ValueError("P0 terminal stream SHA-256 differs from its manifest")
    if manifest.get("trace_off_on_answer_match") is not True:
        raise ValueError("P1 requires the P0 trace-off/on observer guard")
    config = manifest.get("config", {})
    window_size = config.get("window_size")
    compression_ratio = config.get("compression_ratio")
    if not isinstance(window_size, int) or not isinstance(compression_ratio, (int, float)):
        raise ValueError("P0 config lacks an integer window_size or numeric compression_ratio")
    decisions = load_frontend_decision_stream(stream_path)
    contract = validate_snapkv_p0_contract(
        decisions,
        window_size=window_size,
        compression_ratio=float(compression_ratio),
    )
    if contract["event_count"] != manifest.get("decision_stream_event_count"):
        raise ValueError("P0 manifest event count differs from revalidated terminal stream")
    return manifest, decisions, window_size, float(compression_ratio)






def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"P1 output directory already exists: {args.output_dir}")
    if not args.page_tokens or len(set(args.page_tokens)) != len(args.page_tokens) or any(page <= 0 for page in args.page_tokens):
        raise ValueError("--page-tokens must contain unique positive values")
    if args.kv_bytes_per_token <= 0 or args.metadata_bytes_per_page < 0:
        raise ValueError("declared accounting dimensions are invalid")
    p0_manifest, decisions, p0_window, _compression_ratio = load_p0_input(args.p0_dir)
    resident_window = p0_window if args.resident_window is None else args.resident_window
    if resident_window != p0_window:
        raise ValueError("P1 resident_window must equal the P0 SnapKV observation window")
    request_rows = []
    head_rows = []
    for page_tokens in args.page_tokens:
        request_row, rows = replay_p1(
            decisions=decisions,
            request_id=str(p0_manifest["request_id"]),
            resident_window=resident_window,
            page_tokens=page_tokens,
            kv_bytes_per_token=args.kv_bytes_per_token,
            metadata_bytes_per_page=args.metadata_bytes_per_page,
        )
        request_rows.append(request_row)
        head_rows.extend(rows)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "snapkv_p1_request_packed_opportunity.csv", request_rows, REQUEST_COLUMNS)
    write_csv(args.output_dir / "snapkv_p1_layer_head_packed_opportunity.csv", head_rows, HEAD_COLUMNS)
    report = {
        "schema_version": P1_SCHEMA,
        "status": "complete",
        "input": {
            "p0_dir": str(args.p0_dir),
            "p0_manifest_sha256": sha256_file(args.p0_dir / P0_MANIFEST_NAME),
            "p0_terminal_stream_sha256": sha256_file(args.p0_dir / P0_STREAM_NAME),
            "p0_source_git_commit": p0_manifest.get("git_commit"),
            "p0_config_hash": p0_manifest.get("config_hash"),
        },
        "mapping": {
            "terminal_drop": "absent from Route-A stores",
            "terminal_keep_at_or_after_resident_window_start": "resident hot window",
            "terminal_keep_before_resident_window_start": "append-only per-(layer,kv_head) cold pages in original-position order",
            "native_score_ranked_gather_order_used": False,
            "resident_window_is_p0_snapkv_observation_window": True,
        },
        "config": {
            "page_tokens": args.page_tokens,
            "resident_window": resident_window,
            "cache_dtype": args.cache_dtype,
            "kv_bytes_per_layer_head_token_declared": args.kv_bytes_per_token,
            "metadata_bytes_per_cold_page_declared": args.metadata_bytes_per_page,
        },
        "request_rows": request_rows,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "source_sha256": {
            "frontend_contract": sha256_file(Path("kvpress/route_a_frontend_contract.py")),
            "p1_tool": sha256_file(Path(__file__)),
            "packed_page_simulator": sha256_file(Path("kvpress/research/packing.py")),
        },
        "boundaries": [
            "P1 is a static final-decision replay of one completed SnapKV P0 request; it performs no model execution and does not modify the P0 stream.",
            "The resident window equals SnapKV's protected observation window for this mapping study; it is not a final Route-A or hardware hot-window selection.",
            "Slot/page/tail values are trace-derived under the stated mapping. Declared byte and metadata fields are accounting assumptions, not allocator memory or HBM traffic measurements.",
            "P1 establishes neither SnapKV same-mask Route-A functional equivalence, native decode quality, online maturity/pending behavior, scheduler/backpressure, latency, throughput, energy, area, hardware specification, nor RTL readiness.",
        ],
    }
    (args.output_dir / "snapkv_p1_packed_opportunity_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"SnapKV P1 static packed opportunity completed: {args.output_dir}")


if __name__ == "__main__":
    main()
