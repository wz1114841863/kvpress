#!/usr/bin/env python3
"""Static packed-page opportunity analysis for a completed SnapKV Route-A P0 stream."""

from __future__ import annotations

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
from tools.simulate_kvzap_packed_pages import PackedKVSimulator, percentile, safe_divide


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


def decisions_to_final_drop(decisions: list[FrontendDecision]) -> tuple[np.ndarray, np.ndarray, int, int, int]:
    """Recover an explicit [layer, KV-head, position] final drop mask once."""
    if not decisions:
        raise ValueError("P1 cannot map an empty terminal decision stream")
    if {item.frontend_name for item in decisions} != {SNAPKV_FRONTEND_NAME}:
        raise ValueError("P1 accepts only the SnapKV frontend stream")
    if {item.decision_epoch for item in decisions} != {SNAPKV_TERMINAL_EPOCH}:
        raise ValueError("P1 accepts only SnapKV terminal prefill decisions")
    calls = {item.model_call_index for item in decisions}
    layers = sorted({item.layer for item in decisions})
    heads = sorted({item.kv_head for item in decisions})
    lengths = {item.sequence_length for item in decisions}
    if calls != {0} or layers != list(range(len(layers))) or heads != list(range(len(heads))) or len(lengths) != 1:
        raise ValueError("P1 requires one contiguous P0 model call with contiguous layer/KV-head IDs and one sequence length")
    sequence_length = lengths.pop()
    final_drop = np.ones((len(layers), len(heads), sequence_length), dtype=np.bool_)
    valid = np.zeros_like(final_drop, dtype=np.bool_)
    for item in decisions:
        if valid[item.layer, item.kv_head, item.original_position]:
            raise ValueError("P1 terminal stream contains a duplicate layer/KV-head/position")
        final_drop[item.layer, item.kv_head, item.original_position] = not item.keep
        valid[item.layer, item.kv_head, item.original_position] = True
    if not valid.all():
        raise ValueError("P1 terminal stream does not cover every declared identity")
    return final_drop, valid, len(layers), len(heads), sequence_length


def replay_p1(
    *,
    decisions: list[FrontendDecision],
    request_id: str,
    resident_window: int,
    page_tokens: int,
    kv_bytes_per_token: int,
    metadata_bytes_per_page: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Map the P0 terminal set into fixed hot and append-only cold pages."""
    final_drop, valid, layer_count, head_count, sequence_length = decisions_to_final_drop(decisions)
    simulator = PackedKVSimulator(page_tokens, kv_bytes_per_token, metadata_bytes_per_page)
    state = simulator.replay(final_drop, valid, resident_window)
    hot = state["hot_slots"]
    cold_kept = state["cold_logical_kept_slots"]
    cold_allocated = state["cold_allocated_slots"]
    tail_waste = state["tail_waste_slots"]
    pages = state["cold_page_count"]
    logical_total = int(valid.sum())
    logical_kept = int(((~final_drop) & valid).sum())
    terminal_drop = logical_total - logical_kept
    ideal_slots = int((hot + cold_kept).sum())
    physical_slots = int((hot + cold_allocated).sum())
    page_values = pages.reshape(-1)
    request_row = {
        "request_id": request_id,
        "frontend_name": SNAPKV_FRONTEND_NAME,
        "decision_epoch": SNAPKV_TERMINAL_EPOCH,
        "page_tokens": page_tokens,
        "resident_window": resident_window,
        "logical_total_slots": logical_total,
        "logical_kept_slots": logical_kept,
        "terminal_drop_slots": terminal_drop,
        "hot_slots": int(hot.sum()),
        "cold_logical_kept_slots": int(cold_kept.sum()),
        "cold_allocated_slots": int(cold_allocated.sum()),
        "tail_waste_slots": int(tail_waste.sum()),
        "cold_page_count": int(pages.sum()),
        "metadata_bytes_declared": int(pages.sum()) * metadata_bytes_per_page,
        "full_kv_declared_bytes": logical_total * kv_bytes_per_token,
        "ideal_packed_declared_bytes": ideal_slots * kv_bytes_per_token,
        "physical_packed_declared_bytes": physical_slots * kv_bytes_per_token,
        "total_declared_bytes_including_metadata": physical_slots * kv_bytes_per_token + int(pages.sum()) * metadata_bytes_per_page,
        "ideal_packed_slots": ideal_slots,
        "physical_allocated_slots": physical_slots,
        "full_to_ideal_packed_factor": safe_divide(logical_total, ideal_slots),
        "full_to_physical_packed_factor": safe_divide(logical_total, physical_slots),
        "tail_fragmentation_fraction": safe_divide(int(tail_waste.sum()), int(cold_allocated.sum())),
        "physical_over_ideal_slot_fraction": safe_divide(physical_slots - ideal_slots, ideal_slots),
        "head_page_count_p50": percentile(page_values, 50),
        "head_page_count_p95": percentile(page_values, 95),
        "head_page_count_p99": percentile(page_values, 99),
        "head_page_count_max": int(page_values.max()),
    }
    head_rows = []
    for layer in range(layer_count):
        for kv_head in range(head_count):
            head_hot = int(hot[layer, kv_head])
            head_cold_kept = int(cold_kept[layer, kv_head])
            head_cold_allocated = int(cold_allocated[layer, kv_head])
            head_tail = int(tail_waste[layer, kv_head])
            head_logical = sequence_length
            head_kept = head_hot + head_cold_kept
            head_rows.append(
                {
                    "request_id": request_id,
                    "page_tokens": page_tokens,
                    "resident_window": resident_window,
                    "layer": layer,
                    "kv_head": kv_head,
                    "logical_total_slots": head_logical,
                    "logical_kept_slots": head_kept,
                    "terminal_drop_slots": head_logical - head_kept,
                    "hot_slots": head_hot,
                    "cold_logical_kept_slots": head_cold_kept,
                    "cold_allocated_slots": head_cold_allocated,
                    "tail_waste_slots": head_tail,
                    "cold_page_count": int(pages[layer, kv_head]),
                    "tail_page_valid_slots": int(state["tail_page_valid_slots"][layer, kv_head]),
                    "metadata_bytes_declared": int(pages[layer, kv_head]) * metadata_bytes_per_page,
                    "full_kv_declared_bytes": head_logical * kv_bytes_per_token,
                    "ideal_packed_declared_bytes": head_kept * kv_bytes_per_token,
                    "physical_packed_declared_bytes": (head_hot + head_cold_allocated) * kv_bytes_per_token,
                    "tail_fragmentation_fraction": safe_divide(head_tail, head_cold_allocated),
                }
            )
    return request_row, head_rows


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
            "packed_page_simulator": sha256_file(Path("tools/simulate_kvzap_packed_pages.py")),
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
