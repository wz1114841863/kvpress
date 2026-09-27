#!/usr/bin/env python3
"""A4.13.4 frozen page-source reuse/merge action interface from A4.13.1 traces."""
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


SCHEMA = "kvzap-route-a4134-page-source-reuse-interface-1.0"
EXPECTED_A4133 = (
    "kvzap-route-a4133-packed-kv-hbm-realization-1.0",
    "fea9780d44238f5128008793a12e605e411a95355eaa44e4ad6f71f8b6a735f1",
)
SIDECAR_BYTES_PER_PAGE = PAGE_TOKENS * 8
PARTIAL_STATE_BYTES_FP32 = GQA_GROUP * (128 + 2) * 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.13.4 frozen page-source reuse/merge interface replay. Internal 256-B beats are not HBM transactions, bursts, timing, PPA, or RTL."
    )
    parser.add_argument("--a4133-report", type=Path, required=True, help="Exact accepted A4.13.3 report.")
    for workload in WORKLOADS:
        parser.add_argument(f"--{workload}-manifest", type=Path, required=True, help=f"Exact A4.13.1 {workload} manifest bound by A4.13.3.")
    parser.add_argument("--preflight-only", action="store_true", help="Validate exact inputs and action/beat conservation without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def ceil_div(value: int, divisor: int) -> int:
    return (value + divisor - 1) // divisor


def stat(values: list[int]) -> dict[str, int]:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "sum": 0}
    return {
        "count": len(ordered), "min": ordered[0],
        "p50": ordered[int((len(ordered) - 1) * .5)],
        "p95": ordered[int((len(ordered) - 1) * .95)],
        "p99": ordered[int((len(ordered) - 1) * .99)],
        "max": ordered[-1], "sum": sum(ordered),
    }


def read_a4133(path: Path) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != EXPECTED_A4133[1]:
        raise ValueError("A4.13.4 requires the exact accepted A4.13.3 report")
    report = json.loads(path.read_text(encoding="utf-8"))
    config = report.get("config", {})
    if report.get("schema_version") != EXPECTED_A4133[0] or report.get("status") != "complete":
        raise ValueError("A4.13.3 report is incomplete or incompatible")
    if (config.get("page_tokens"), config.get("page_payload_bytes"), config.get("gqa_group_size"), config.get("declared_transfer_beat_bytes"), config.get("source_buffer_candidates")) != (PAGE_TOKENS, PAGE_BYTES, GQA_GROUP, SECTOR_BYTES, ["S1_one_32KiB_page_source_buffer", "S2_two_32KiB_ping_pong_page_source_buffers"]):
        raise ValueError("A4.13.3 fixed page/GQA/source-buffer interface changed")
    if [row.get("workload") for row in report.get("workload_rows", [])] != list(WORKLOADS):
        raise ValueError("A4.13.3 workload ordering changed")
    return report


def read_bound_manifests(report: dict[str, Any], paths: dict[str, Path]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for workload, path in paths.items():
        expected = report.get("input_artifacts", {}).get(f"{workload}_manifest", {}).get("sha256")
        if not expected or not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"{workload}: manifest differs from A4.13.3-bound input")
        _manifest, events = read_manifest(path, workload)
        validate_events(events)
        groups = gqa_groups(events)
        if len(events) != len(groups) * GQA_GROUP:
            raise ValueError(f"{workload}: incomplete four-head legal GQA grouping")
        result[workload] = groups
    return result


def blank_actions() -> defaultdict[str, int]:
    return defaultdict(int)


def add_actions(total: defaultdict[str, int], event: dict[str, Any], packed: bool) -> None:
    """Add one legal four-head GQA group; no timing/order is inferred."""
    if packed:
        hot, pending, packed_tokens, page_count, full_pages, _tail = source_state(event)
        source_records = {"hot": hot, "pending": pending, "packed": packed_tokens}
        nonempty_sources = sum(count > 0 for count in source_records.values())
        total["packed_payload_fill_actions"] += page_count
        total["packed_sidecar_fill_actions"] += page_count
        total["source_buffer_ready_actions"] += page_count
        total["packed_page_multicast_consume_actions"] += page_count * GQA_GROUP
        total["source_buffer_release_actions_after_all_four_consumers"] += page_count
        total["packed_full_page_fill_actions"] += full_pages
        total["packed_tail_page_fill_actions"] += page_count - full_pages
        total["packed_payload_internal_interface_beats"] += page_count * (PAGE_BYTES // SECTOR_BYTES)
        total["packed_sidecar_internal_interface_beats"] += page_count * ceil_div(SIDECAR_BYTES_PER_PAGE, SECTOR_BYTES)
        for source in ("hot", "pending"):
            records = source_records[source]
            total[f"{source}_direct_source_delivery_actions"] += int(records > 0)
            total[f"{source}_direct_source_records_shared_once_for_gqa"] += records
            total[f"{source}_direct_source_internal_interface_beats"] += records * ceil_div(WORD_BYTES, SECTOR_BYTES)
        useful_records = sum(source_records.values())
        total["logical_source_record_consumes_across_four_query_heads"] += useful_records * GQA_GROUP
        total["partial_state_initialize_actions"] += GQA_GROUP
        total["partial_state_record_update_actions"] += useful_records * GQA_GROUP
        total["partial_state_finalize_actions"] += GQA_GROUP
        total["cross_source_online_merge_actions"] += max(0, nonempty_sources - 1) * GQA_GROUP
        total["nonempty_source_groups"] += nonempty_sources
        return

    causal_tokens = int(event["cache_position"]) + 1
    page_count = ceil_div(causal_tokens, PAGE_TOKENS)
    full_pages = causal_tokens // PAGE_TOKENS
    total["full_kv_payload_fill_actions"] += page_count
    total["source_buffer_ready_actions"] += page_count
    total["full_kv_page_multicast_consume_actions"] += page_count * GQA_GROUP
    total["source_buffer_release_actions_after_all_four_consumers"] += page_count
    total["full_kv_full_page_fill_actions"] += full_pages
    total["full_kv_tail_page_fill_actions"] += page_count - full_pages
    total["full_kv_payload_internal_interface_beats"] += page_count * (PAGE_BYTES // SECTOR_BYTES)
    total["logical_source_record_consumes_across_four_query_heads"] += causal_tokens * GQA_GROUP
    total["partial_state_initialize_actions"] += GQA_GROUP
    total["partial_state_record_update_actions"] += causal_tokens * GQA_GROUP
    total["partial_state_finalize_actions"] += GQA_GROUP
    total["nonempty_source_groups"] += 1


def summarize(events: list[dict[str, Any]], packed: bool) -> dict[str, Any]:
    total = blank_actions()
    by_position: dict[tuple[str, int], defaultdict[str, int]] = defaultdict(blank_actions)
    for event in events:
        add_actions(total, event, packed)
        position_actions = by_position[(str(event["phase"]), int(event["cache_position"]))]
        add_actions(position_actions, event, packed)
    prefix = "packed" if packed else "full_kv"
    fills = total[f"{prefix}_payload_fill_actions"]
    if total["source_buffer_ready_actions"] != fills or total["source_buffer_release_actions_after_all_four_consumers"] != fills:
        raise ValueError("source-buffer lifecycle fill/ready/release conservation failed")
    if packed:
        beats = total["packed_payload_internal_interface_beats"] + total["packed_sidecar_internal_interface_beats"] + total["hot_direct_source_internal_interface_beats"] + total["pending_direct_source_internal_interface_beats"]
    else:
        beats = total["full_kv_payload_internal_interface_beats"]
    return {
        "legal_gqa_groups": len(events),
        "action_counts": dict(sorted(total.items())),
        "total_internal_interface_beats": beats,
        "per_observed_attention_position": {
            phase: {
                "observed_positions": len([key for key in by_position if key[0] == phase]),
                "page_fill_actions": stat([row[f"{prefix}_payload_fill_actions"] for key, row in by_position.items() if key[0] == phase]),
                "internal_interface_beats": stat([
                    (row["packed_payload_internal_interface_beats"] + row["packed_sidecar_internal_interface_beats"] + row["hot_direct_source_internal_interface_beats"] + row["pending_direct_source_internal_interface_beats"])
                    if packed else row["full_kv_payload_internal_interface_beats"]
                    for key, row in by_position.items() if key[0] == phase
                ]),
                "partial_state_record_update_actions": stat([row["partial_state_record_update_actions"] for key, row in by_position.items() if key[0] == phase]),
            }
            for phase in sorted({key[0] for key in by_position})
        },
    }


def phases(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        phase: {
            "observed_legal_gqa_groups": len(rows),
            "observed_unique_cache_positions": len({int(event["cache_position"]) for event in rows}),
            "full_kv_legal_gqa_actions": summarize(rows, packed=False),
            "route_a_packed_legal_gqa_actions": summarize(rows, packed=True),
        }
        for phase in sorted({str(event["phase"]) for event in events})
        for rows in [[event for event in events if str(event["phase"]) == phase]]
    }


def verify_a4133(report: dict[str, Any], workload: str, groups: list[dict[str, Any]]) -> None:
    prior = next(row for row in report["workload_rows"] if row["workload"] == workload)
    full = summarize(groups, packed=False)
    packed = summarize(groups, packed=True)
    old_full = prior["all_observed_phases_aggregate"]["fair_full_kv_legal_gqa_reuse"]
    old_packed = prior["all_observed_phases_aggregate"]["route_a_packed_legal_gqa_reuse"]
    if full["legal_gqa_groups"] != old_full["legal_gqa_reference_attention_groups"] or full["action_counts"]["full_kv_payload_fill_actions"] != old_full["page_fetches"] or full["total_internal_interface_beats"] != old_full["declared_256B_transfer_beats"]:
        raise ValueError(f"{workload}: Full-KV action interface does not reproduce A4.13.3")
    if packed["legal_gqa_groups"] != old_packed["legal_gqa_reference_attention_groups"] or packed["action_counts"]["packed_payload_fill_actions"] != old_packed["page_fetches"] or packed["total_internal_interface_beats"] != old_packed["declared_256B_transfer_beats"]:
        raise ValueError(f"{workload}: Route-A action interface does not reproduce A4.13.3")


def frozen_interface() -> dict[str, Any]:
    return {
        "packed_page_lifecycle": [
            {"state": "FILL", "action": "payload page and 512-B sidecar arrive at source-buffer interface"},
            {"state": "READY", "action": "page is retained until all four exact GQA consumers complete"},
            {"state": "CONSUMING", "action": "one packed page is multicast to four query-head consumers; each updates its partial state"},
            {"state": "MERGED", "action": "hot/pending/packed online-source partials are merged for each query head"},
            {"state": "RELEASE", "action": "permitted only after all four consumer completions and partial-state updates"},
        ],
        "hot_pending_direct_source": "Direct source records enter the same four-head fanout and pipeline-local partial states; they do not create a packed-page source-buffer lifecycle.",
        "partial_state": {
            "logical_placement": "pipeline-local from source initialization through final online merge",
            "four_query_head_interface_bytes_if_fp32": PARTIAL_STATE_BYTES_FP32,
            "spill_rule": "Any future register-file/SRAM spill must be explicitly counted in A4.13.5; it is not free in this contract.",
        },
        "source_buffer_candidates_frozen_from_a4133": [
            {"candidate": "S1_one_32KiB_page_source_buffer", "capacity_bytes": PAGE_BYTES, "fill_consume_overlap": False},
            {"candidate": "S2_two_32KiB_ping_pong_page_source_buffers", "capacity_bytes": 2 * PAGE_BYTES, "fill_consume_overlap": True},
        ],
        "symbolic_overlap_condition": {
            "S1": "T_page = T_fill + T_consume",
            "S2_steady_state": "T_page = max(T_fill, T_consume), with warm-up and drain retained",
            "full_hide_condition": "T_consume(current_page) >= T_fill(next_page)",
            "boundary": "T_fill and T_consume have no selected physical values in A4.13.4; A4.13.5 supplies target-profile service times.",
        },
        "internal_unit": {
            "name": "internal_interface_accounting_beat",
            "bytes": SECTOR_BYTES,
            "page_payload_beats": PAGE_BYTES // SECTOR_BYTES,
            "sidecar_beats": SIDECAR_BYTES_PER_PAGE // SECTOR_BYTES,
            "not_a_physical_hbm_transaction_or_burst": True,
        },
    }


def materialize(output_dir: Path, inputs: dict[str, Path]) -> dict[str, dict[str, str]]:
    folder = output_dir / "input_artifacts"
    folder.mkdir()
    artifacts: dict[str, dict[str, str]] = {}
    for label, source in inputs.items():
        target = folder / f"{label}_{source.name}"
        shutil.copyfile(source, target)
        artifacts[label] = {"source_path": str(source), "materialized_copy": str(target), "sha256": sha256_file(target)}
    return artifacts


def main() -> None:
    args = parse_args()
    report = read_a4133(args.a4133_report)
    manifests = {workload: getattr(args, f"{workload}_manifest") for workload in WORKLOADS}
    grouped = read_bound_manifests(report, manifests)
    for workload, groups in grouped.items():
        verify_a4133(report, workload, groups)
    if args.preflight_only:
        print("A4.13.4 preflight passed: exact A4.13.3 inputs, fair legal GQA groups, and page/beat action conservation validate; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    args.output_dir.mkdir(parents=True)
    artifacts = materialize(args.output_dir, {"a4133_report": args.a4133_report, **{f"{workload}_manifest": path for workload, path in manifests.items()}})
    rows = []
    for workload, groups in grouped.items():
        rows.append({
            "workload": workload,
            "all_observed_phases_aggregate": {
                "full_kv_legal_gqa_actions": summarize(groups, packed=False),
                "route_a_packed_legal_gqa_actions": summarize(groups, packed=True),
            },
            "by_software_trace_phase": phases(groups),
        })
    config = {
        "stage": "A4.13.4",
        "page_payload_bytes": PAGE_BYTES,
        "page_tokens": PAGE_TOKENS,
        "gqa_group_size": GQA_GROUP,
        "internal_interface_accounting_beat_bytes": SECTOR_BYTES,
        "sidecar_bytes_per_packed_page": SIDECAR_BYTES_PER_PAGE,
        "source_buffer_candidates": ["S1_one_32KiB_page_source_buffer", "S2_two_32KiB_ping_pong_page_source_buffers"],
        "partial_state_logical_placement": "pipeline-local",
        "partial_state_four_query_head_interface_bytes_if_fp32": PARTIAL_STATE_BYTES_FP32,
    }
    output = {
        "schema_version": SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "execution_classification": "exact scalar software source/page event replay with frozen action-level page-source/partial-merge interface; not physical HBM transactions/bursts, ports, timing, bandwidth, PPA, or RTL evidence",
        "config": config,
        "config_hash": stable_hash(config),
        "input_artifacts": artifacts,
        "frozen_datapath_interface": frozen_interface(),
        "workload_rows": rows,
        "evidence_classes": {
            "direct_software_observation": ["source record counts, packed page state, cache position, phase, and query/KV-head membership", "event-level exact four-query-head GQA groups"],
            "deterministic_accounting": ["page lifecycle action counts", "512-B K+V word to 256-B internal interface beat conversion", "four-head partial-state action counts", "source-buffer release after all four consumers"],
            "declared_mapping_only": ["pipeline-local partial-state placement", "S1/S2 capacities and symbolic overlap condition", "HBM-resident packed-page placement"],
        },
        "semantic_guards": {
            "exact_accepted_a4133_report_bound": True,
            "a4131_manifest_hashes_bound_through_a4133": True,
            "full_kv_and_route_a_use_identical_event_level_legal_gqa_groups": True,
            "full_kv_and_route_a_page_and_internal_beat_totals_reproduce_a4133": True,
            "packed_page_release_requires_all_four_consumers_and_partial_updates": True,
            "partial_state_spill_must_be_explicit_in_later_target_profile": True,
            "only_a4133_s1_s2_source_buffer_candidates": True,
            "internal_256B_unit_not_named_or_interpreted_as_physical_hbm_transaction_or_burst": True,
            "no_pruning_admission_queue_execution_scheduler_metadata_or_payload_organization_change": True,
            "no_physical_hbm_timing_bandwidth_utilization_area_energy_speedup_architecture_or_rtl_claim": True,
        },
        "boundaries": [
            "A4.13.4 records action requirements and symbolic overlap conditions only. It has no source issue timestamps, HBM request trace, controller, channel, native burst, or physical buffer-port observation.",
            "The 256-B internal interface/accounting beat is not an HBM transaction or burst. A4.13.5 must select target profile parameters before reporting such quantities.",
            "Pipeline-local partial state is a logical residency contract. Its eventual RF/SRAM implementation and any spill traffic remain for A4.13.5.",
            "S2 overlap is conditional on the explicit T_consume >= T_fill test; warm-up, drain, and any failure of that condition remain visible in A4.13.5.",
        ],
    }
    path = args.output_dir / "a4134_page_source_reuse_interface_report.json"
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.13.4 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} workloads={len(rows)} source_buffer_candidates=2")


if __name__ == "__main__":
    main()
