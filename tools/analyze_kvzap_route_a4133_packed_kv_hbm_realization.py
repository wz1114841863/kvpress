#!/usr/bin/env python3
"""A4.13.3 fair legal-GQA packed-KV HBM/source-buffer accounting replay."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a4132_packed_cold_hbm_traffic import (
    GQA_GROUP,
    PAGE_BYTES,
    PAGE_TOKENS,
    SECTOR_BYTES,
    WORD_BYTES,
    WORKLOADS,
    gqa_groups,
    read_manifest,
    source_state,
    validate_events,
)
from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4133-packed-kv-hbm-realization-1.0"
EXPECTED_A4132 = (
    "kvzap-route-a4132-packed-cold-hbm-traffic-1.0",
    "400df695bc2a41572e7a41376520621250403288658d9fc9b74b250bd9148099",
)
POSITION_SIDECAR_BYTES_PER_TOKEN = 8
POSITION_SIDECAR_BYTES_PER_PAGE = PAGE_TOKENS * POSITION_SIDECAR_BYTES_PER_TOKEN
PARTIAL_BYTES_FP32 = GQA_GROUP * (128 + 2) * 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.13.3 fair Full-KV-vs-packed legal-GQA page/beat/source-buffer accounting. Declared normalized model only; not measured HBM traffic, timing, PPA, or RTL."
    )
    parser.add_argument("--a4132-report", type=Path, required=True, help="Exact accepted A4.13.2 report.")
    for workload in WORKLOADS:
        parser.add_argument(f"--{workload}-manifest", type=Path, required=True, help=f"Exact A4.13.1 {workload} manifest bound by A4.13.2.")
    parser.add_argument("--preflight-only", action="store_true", help="Validate report/manifest hashes and fair GQA groups without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def ceil_div(value: int, divisor: int) -> int:
    return (value + divisor - 1) // divisor


def stat(values: list[int]) -> dict[str, int]:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "sum": 0}
    return {
        "count": len(ordered),
        "min": ordered[0],
        "p50": ordered[int((len(ordered) - 1) * .5)],
        "p95": ordered[int((len(ordered) - 1) * .95)],
        "p99": ordered[int((len(ordered) - 1) * .99)],
        "max": ordered[-1],
        "sum": sum(ordered),
    }


def read_a4132(path: Path) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != EXPECTED_A4132[1]:
        raise ValueError("A4.13.3 requires the exact accepted A4.13.2 report")
    report = json.loads(path.read_text(encoding="utf-8"))
    config = report.get("config", {})
    if report.get("schema_version") != EXPECTED_A4132[0] or report.get("status") != "complete" or config.get("gqa_group_size") != GQA_GROUP or config.get("packed_page_bytes") != PAGE_BYTES or config.get("declared_accounting_sector_bytes") != SECTOR_BYTES:
        raise ValueError("A4.13.2 report is incomplete or has incompatible fixed accounting")
    rows = report.get("workload_rows", [])
    if [row.get("workload") for row in rows] != list(WORKLOADS):
        raise ValueError("A4.13.2 workload ordering changed")
    return report


def validate_bound_manifests(report: dict[str, Any], paths: dict[str, Path]) -> dict[str, tuple[dict[str, Any], list[dict[str, Any]]]]:
    parsed: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    inputs = report.get("input_artifacts", {})
    for workload, path in paths.items():
        expected = inputs.get(f"{workload}_manifest", {}).get("sha256")
        if not expected or not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"{workload}: manifest does not match A4.13.2-bound input")
        manifest, events = read_manifest(path, workload)
        validate_events(events)
        groups = gqa_groups(events)
        if len(events) != len(groups) * GQA_GROUP:
            raise ValueError(f"{workload}: legal GQA group coverage is not exactly four-way")
        parsed[workload] = (manifest, events)
    return parsed


def event_transfer(event: dict[str, Any], packed: bool) -> dict[str, int]:
    hot, pending, packed_tokens, page_count, full_pages, tail = source_state(event)
    if packed:
        useful = (hot + pending + packed_tokens) * WORD_BYTES
        payload = (hot + pending) * WORD_BYTES + page_count * PAGE_BYTES
        sidecar = page_count * POSITION_SIDECAR_BYTES_PER_PAGE
        return {
            "useful_kv_bytes": useful,
            "page_rounded_payload_bytes": payload,
            "position_sidecar_bytes": sidecar,
            "total_declared_transfer_bytes": payload + sidecar,
            "page_fetches": page_count,
            "full_page_fetches": full_pages,
            "tail_page_fetches": page_count - full_pages,
            "consumer_payload_beats": ceil_div((hot + pending) * WORD_BYTES, SECTOR_BYTES) + page_count * (PAGE_BYTES // SECTOR_BYTES),
        }
    causal_tokens = int(event["cache_position"]) + 1
    page_count = ceil_div(causal_tokens, PAGE_TOKENS)
    full_pages = causal_tokens // PAGE_TOKENS
    return {
        "useful_kv_bytes": causal_tokens * WORD_BYTES,
        "page_rounded_payload_bytes": page_count * PAGE_BYTES,
        "position_sidecar_bytes": 0,
        "total_declared_transfer_bytes": page_count * PAGE_BYTES,
        "page_fetches": page_count,
        "full_page_fetches": full_pages,
        "tail_page_fetches": page_count - full_pages,
        "consumer_payload_beats": page_count * (PAGE_BYTES // SECTOR_BYTES),
    }


def summarize(events: list[dict[str, Any]], packed: bool) -> dict[str, Any]:
    totals = defaultdict(int)
    per_position: dict[tuple[str, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for event in events:
        data = event_transfer(event, packed)
        for name, value in data.items():
            totals[name] += value
        position = per_position[(str(event["phase"]), int(event["cache_position"]))]
        for name, value in data.items():
            position[name] += value
    beats = ceil_div(totals["total_declared_transfer_bytes"], SECTOR_BYTES)
    if beats != totals["consumer_payload_beats"] + ceil_div(totals["position_sidecar_bytes"], SECTOR_BYTES):
        raise ValueError("transfer-beat conservation failed")
    return {
        "legal_gqa_reference_attention_groups": len(events),
        "useful_kv_bytes": totals["useful_kv_bytes"],
        "page_rounded_payload_bytes": totals["page_rounded_payload_bytes"],
        "position_sidecar_bytes": totals["position_sidecar_bytes"],
        "total_declared_transfer_bytes": totals["total_declared_transfer_bytes"],
        "declared_256B_transfer_beats": beats,
        "payload_consumer_beats": totals["consumer_payload_beats"],
        "page_fetches": totals["page_fetches"],
        "full_page_fetches": totals["full_page_fetches"],
        "tail_page_fetches": totals["tail_page_fetches"],
        "useful_bytes_per_total_declared_transferred_byte": totals["useful_kv_bytes"] / totals["total_declared_transfer_bytes"],
        "per_observed_attention_position": {
            phase: {
                "observed_positions": len([key for key in per_position if key[0] == phase]),
                "page_fetches": stat([row["page_fetches"] for key, row in per_position.items() if key[0] == phase]),
                "total_declared_transfer_bytes": stat([row["total_declared_transfer_bytes"] for key, row in per_position.items() if key[0] == phase]),
                "declared_256B_transfer_beats": stat([ceil_div(row["total_declared_transfer_bytes"], SECTOR_BYTES) for key, row in per_position.items() if key[0] == phase]),
            }
            for phase in sorted({key[0] for key in per_position})
        },
    }


def source_buffer_sensitivity(summary: dict[str, Any]) -> list[dict[str, Any]]:
    fill = int(summary["declared_256B_transfer_beats"])
    consume = int(summary["payload_consumer_beats"])
    page_count = int(summary["page_fetches"])
    return [
        {
            "candidate": "S1_one_32KiB_page_source_buffer",
            "source_buffer_capacity_bytes": PAGE_BYTES,
            "logical_interface": {"page_fill_streams": 1, "four_query_head_broadcast_consumer_streams": 4, "fill_consume_overlap": False},
            "declared_normalized_service_slots": fill + consume,
            "interpretation": "One declared transfer beat and one consumer beat each use one normalized slot; fill and consumption are serialized. This is not a frequency or physical-cycle claim.",
        },
        {
            "candidate": "S2_two_32KiB_ping_pong_page_source_buffers",
            "source_buffer_capacity_bytes": 2 * PAGE_BYTES,
            "logical_interface": {"page_fill_streams": 1, "four_query_head_broadcast_consumer_streams": 4, "fill_consume_overlap": True},
            "ideal_steady_state_normalized_service_slot_lower_bound": max(fill, consume),
            "ideal_overlap_slots_avoided_vs_S1": min(fill, consume),
            "interpretation": "Ideal steady-state lower bound only: independent logical fill and consume progress are required. It neither chooses source-buffer ports nor proves physical overlap.",
        },
        {
            "shared_interface_terms": {
                "packed_page_fetches": page_count,
                "four_query_head_partial_state_interface_bytes_if_fp32": PARTIAL_BYTES_FP32,
                "boundary": "Partial state is an interface size, not a selected register/SRAM resource or merge transfer.",
            }
        },
    ]


def phase_rows(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for phase in sorted({str(event["phase"]) for event in events}):
        groups = [event for event in events if str(event["phase"]) == phase]
        full, route = summarize(groups, packed=False), summarize(groups, packed=True)
        result[phase] = {
            "observed_legal_gqa_groups": len(groups),
            "observed_unique_cache_positions": len({int(event["cache_position"]) for event in groups}),
            "fair_full_kv_legal_gqa_reuse": full,
            "route_a_packed_legal_gqa_reuse": route,
            "route_a_vs_full": {
                "total_declared_transfer_byte_ratio": route["total_declared_transfer_bytes"] / full["total_declared_transfer_bytes"],
                "declared_256B_transfer_beat_ratio": route["declared_256B_transfer_beats"] / full["declared_256B_transfer_beats"],
                "page_fetch_ratio": route["page_fetches"] / full["page_fetches"],
                "boundary": "Ratios are fixed page/beat accounting under identical verified GQA groups, not measured HBM bandwidth or speedup.",
            },
            "route_a_source_buffer_sensitivity": source_buffer_sensitivity(route),
        }
    return result


def verify_a4132_consistency(report: dict[str, Any], workload: str, groups: list[dict[str, Any]]) -> None:
    row = next(item for item in report["workload_rows"] if item["workload"] == workload)
    full = summarize(groups, packed=False)
    route = summarize(groups, packed=True)
    old_full = row["full_kv_hbm_baseline"]
    old_route = row["packed_legal_gqa_reuse"]
    if old_full["reference_attention_evaluations"] != len(groups) * GQA_GROUP or old_full["declared_hbm_transferred_bytes"] != full["useful_kv_bytes"] * GQA_GROUP:
        raise ValueError(f"{workload}: Full-KV legal-GQA derivation no longer agrees with A4.13.2 no-reuse source trace")
    if old_route["reference_attention_evaluations"] != len(groups) or old_route["declared_hbm_transferred_bytes"] != route["page_rounded_payload_bytes"]:
        raise ValueError(f"{workload}: Route-A legal-GQA payload accounting no longer agrees with A4.13.2")


def admission_and_merge(report: dict[str, Any], workload: str) -> dict[str, Any]:
    row = next(item for item in report["workload_rows"] if item["workload"] == workload)
    p3 = row["p3_admission_staging_mapping_carried_from_a4131"]
    move = p3["declared_admission_movement"]
    hbm_write = int(move["hbm_pending_write_bytes"]) + int(move["hbm_packed_write_bytes"])
    return {
        "p3_carried_admission_mapping": p3,
        "declared_hbm_write_bytes_excluding_pending_read": hbm_write,
        "declared_hbm_write_256B_transfer_beats_excluding_pending_read": ceil_div(hbm_write, SECTOR_BYTES),
        "merge_interface_carried_from_a4131": row["merge_interface_carried_from_a4131"],
        "boundary": "P3 movement and merge values are carried declared mappings/interfaces. They are not observed HBM writes, DMA traffic, or physical merge transfers.",
    }


def materialize(output_dir: Path, inputs: dict[str, Path]) -> dict[str, dict[str, str]]:
    folder = output_dir / "input_artifacts"
    folder.mkdir()
    output: dict[str, dict[str, str]] = {}
    for label, source in inputs.items():
        target = folder / f"{label}_{source.name}"
        shutil.copyfile(source, target)
        output[label] = {"source_path": str(source), "materialized_copy": str(target), "sha256": sha256_file(target)}
    return output


def main() -> None:
    args = parse_args()
    report = read_a4132(args.a4132_report)
    manifests = {workload: getattr(args, f"{workload}_manifest") for workload in WORKLOADS}
    parsed = validate_bound_manifests(report, manifests)
    grouped = {workload: gqa_groups(events) for workload, (_manifest, events) in parsed.items()}
    for workload, events in grouped.items():
        verify_a4132_consistency(report, workload, events)
    if args.preflight_only:
        print("A4.13.3 preflight passed: exact A4.13.2 inputs and fair Full-KV/Route-A event-level legal GQA groups validate; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    args.output_dir.mkdir(parents=True)
    artifacts = materialize(args.output_dir, {"a4132_report": args.a4132_report, **{f"{workload}_manifest": path for workload, path in manifests.items()}})
    rows = []
    for workload, events in grouped.items():
        all_phases = phase_rows(events)
        aggregate_full, aggregate_route = summarize(events, packed=False), summarize(events, packed=True)
        rows.append({
            "workload": workload,
            "all_observed_phases_aggregate": {
                "fair_full_kv_legal_gqa_reuse": aggregate_full,
                "route_a_packed_legal_gqa_reuse": aggregate_route,
                "route_a_vs_full_total_declared_transfer_byte_ratio": aggregate_route["total_declared_transfer_bytes"] / aggregate_full["total_declared_transfer_bytes"],
                "route_a_source_buffer_sensitivity": source_buffer_sensitivity(aggregate_route),
            },
            "by_software_trace_phase": all_phases,
            "route_a_admission_and_merge_terms": admission_and_merge(report, workload),
        })
    config = {
        "stage": "A4.13.3",
        "comparison": ["full_kv_legal_gqa_reuse", "route_a_packed_legal_gqa_reuse"],
        "page_tokens": PAGE_TOKENS,
        "page_payload_bytes": PAGE_BYTES,
        "gqa_group_size": GQA_GROUP,
        "declared_transfer_beat_bytes": SECTOR_BYTES,
        "source_buffer_candidates": ["S1_one_32KiB_page_source_buffer", "S2_two_32KiB_ping_pong_page_source_buffers"],
        "position_sidecar_bytes_per_packed_page_fetch": POSITION_SIDECAR_BYTES_PER_PAGE,
    }
    output = {
        "schema_version": SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "execution_classification": "exact scalar source/page event replay with event-level legal GQA grouping and declared page/256-B-beat/normalized-service-slot mapping; not physical HBM transaction, bandwidth, timing, PPA, or RTL evidence",
        "config": config,
        "config_hash": stable_hash(config),
        "input_artifacts": artifacts,
        "workload_rows": rows,
        "evidence_classes": {
            "direct_software_observation": ["source record counts, packed page state, cache position, phase, layer/KV/query-head membership", "event-level legal four-query-head GQA groups"],
            "deterministic_accounting": ["64-token page rounding", "512-B K+V words", "256-B declared transfer beats", "64-entry 8-B packed position sidecar", "S1 serialized and S2 ideal-overlap normalized service-slot formulae"],
            "declared_mapping_only": ["HBM-resident placement", "Full-KV page layout", "source-buffer streams/overlap", "P3 admission movement and partial merge interface"],
        },
        "semantic_guards": {
            "exact_accepted_a4132_report_bound": True,
            "a4131_manifest_hashes_bound_through_a4132": True,
            "full_and_route_a_use_identical_event_level_legal_gqa_groups": True,
            "a4132_packed_legal_gqa_payload_accounting_reproduced": True,
            "no_new_payload_organization_beyond_a4131_p3": True,
            "only_s1_single_page_and_s2_ping_pong_source_buffer_sensitivity": True,
            "no_pruning_admission_queue_execution_scheduler_or_metadata_contract_change": True,
            "no_measured_hbm_transaction_bandwidth_timing_area_energy_speedup_or_net_benefit_claim": True,
        },
        "boundaries": [
            "The 256-B transfer beat is a declared accounting granule, not a native HBM transaction, protocol burst, or controller configuration.",
            "Full-KV 64-token page rounding and Route-A HBM placement are declared mappings from scalar software traces, not a physical address layout or memory trace.",
            "Normalized service slots are not clock cycles. S2 is an ideal overlap lower bound and requires independent logical fill/consume progress without selecting ports or an SRAM macro.",
            "Position-sidecar and merge values are conservative declared interfaces; metadata traffic, allocation, DMA, physical ports, attention lane timing, bandwidth, area, energy, and PPA remain unresolved.",
        ],
    }
    path = args.output_dir / "a4133_packed_kv_hbm_realization_report.json"
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.13.3 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} workloads={len(rows)} source_buffer_candidates=2")


if __name__ == "__main__":
    main()
