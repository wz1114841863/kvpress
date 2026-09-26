#!/usr/bin/env python3
"""A4.13.2 packed-cold HBM traffic accounting; no hardware measurement."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4132-packed-cold-hbm-traffic-1.0"
TRACE_SCHEMA = "kvzap-route-a4131-payload-access-trace-1.0"
EXPECTED_A4131 = ("kvzap-route-a4131-payload-organization-envelope-1.0", "ba6ec8291d213317e953dd0ac3a050524cf10a327705c6390fe652531a98950c")
WORKLOADS = ("retrieval", "summarization", "reasoning")
LAYERS, KV_HEADS, GQA_GROUP, WORD_BYTES, PAGE_TOKENS, SECTOR_BYTES = 36, 8, 4, 512, 64, 256
PAGE_BYTES = WORD_BYTES * PAGE_TOKENS


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.13.2 fixed-baseline packed-cold HBM traffic accounting. All traffic is declared mapping/accounting, not measured HBM bandwidth, PPA, timing, or RTL.")
    p.add_argument("--a4131-report", type=Path, required=True)
    for workload in WORKLOADS:
        p.add_argument(f"--{workload}-manifest", type=Path, required=True)
    p.add_argument("--preflight-only", action="store_true", help="Validate exact input reports and event-level GQA reuse eligibility without output.")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def read_rows(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_a4131(path: Path) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != EXPECTED_A4131[1]:
        raise ValueError("A4.13.2 requires exact accepted A4.13.1 report")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != EXPECTED_A4131[0] or report.get("status") != "complete":
        raise ValueError("A4.13.1 report is incomplete or incompatible")
    names = [row["candidate"] for row in report.get("workload_rows", [{}])[0].get("declared_three_candidate_mappings", [])]
    if names != ["P1_independent_pending_hbm_backing_to_packed_hbm", "P2_layer_local_pending_sram_to_packed_hbm", "P3_one_64token_sram_staging_page_with_pending_hbm_backing_to_packed_hbm"]:
        raise ValueError("A4.13.1 candidate set changed")
    return report


def read_manifest(path: Path, workload: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    config, guards = manifest.get("config", {}), manifest.get("observational_guards", {})
    needed = ("payload_recorder_armed_on_prefill_armed_external_storage_path", "trace_off_trace_on_generated_token_ids_equal", "trace_on_same_mask_dense_generated_token_ids_equal", "a4131_token_digest_equals_accepted_a4112b", "replay_mask_consumption_complete_all_paths", "all_layers_all_kv_heads_external_storage_covered", "recorders_final_packed_pending_cold_state_unchanged", "no_drop_or_reorder_or_new_full_kv_fallback")
    fixed = (workload, 128, PAGE_TOKENS, 512, ["all"], "all")
    observed = (config.get("preset"), config.get("window_size"), config.get("page_tokens"), config.get("admission_budget"), config.get("target_layers"), config.get("target_kv_head"))
    payload = manifest.get("payload_access_trace", {})
    trace_path = path.parent / payload.get("path", "")
    if manifest.get("schema_version") != TRACE_SCHEMA or manifest.get("status") != "complete" or observed != fixed or not all(guards.get(k) is True for k in needed) or payload.get("schema_version") != "kvzap-route-a424-logical-attention-events-1.0" or not trace_path.is_file() or sha256_file(trace_path) != payload.get("sha256"):
        raise ValueError(f"{workload}: payload-access manifest incompatible")
    return manifest, read_rows(trace_path)


def source_state(event: dict[str, Any]) -> tuple[int, int, int, int, int, int]:
    rows = event.get("source_decisions", [])
    if [row.get("source") for row in rows] != ["hot", "pending", "packed"]:
        raise ValueError("source order changed")
    counts = {row["source"]: int(row["record_count"]) for row in rows}
    page_count, full_count, tail = int(event.get("packed_page_count", -1)), int(event.get("packed_full_page_count", -1)), int(event.get("packed_tail_tokens", -1))
    # The reference represents an exactly full final page as ``full == pages``
    # and ``tail == 0``.  A nonempty tail therefore ranges 1..63 rather than
    # being forced to contain a duplicate 64-token full page.
    if any(value < 0 for value in (*counts.values(), page_count, full_count, tail)) or full_count > page_count or (page_count == 0 and tail != 0) or tail >= PAGE_TOKENS:
        raise ValueError("invalid packed page state")
    if counts["packed"] != full_count * PAGE_TOKENS + tail:
        raise ValueError("packed source count/page state disagree")
    return counts["hot"], counts["pending"], counts["packed"], page_count, full_count, tail


def validate_events(events: list[dict[str, Any]]) -> None:
    covered: dict[int, set[int]] = defaultdict(set)
    for index, event in enumerate(events):
        layer, head, query, position = (int(event.get(k, -1)) for k in ("layer", "kv_head", "query_head", "cache_position"))
        if int(event.get("logical_event_sequence", -1)) != index or event.get("merge_after_source_decisions") is not True or layer not in range(LAYERS) or head not in range(KV_HEADS) or query not in range(KV_HEADS * GQA_GROUP) or position < 0:
            raise ValueError("payload event sequence/dimensions invalid")
        if query // GQA_GROUP != head:
            raise ValueError("query head does not map to declared GQA KV head")
        source_state(event); covered[layer].add(head)
    if not events or {layer: sorted(heads) for layer, heads in covered.items()} != {layer: list(range(KV_HEADS)) for layer in range(LAYERS)}:
        raise ValueError("payload event layer/KV-head coverage incomplete")


def metric(events: list[dict[str, Any]]) -> dict[str, int]:
    useful = transfer = full = page_requests = full_pages = tail_pages = 0
    hot = pending = packed = 0
    for event in events:
        hot_count, pending_count, packed_count, page_count, full_count, _tail = source_state(event)
        hot += hot_count; pending += pending_count; packed += packed_count
        useful += (hot_count + pending_count + packed_count) * WORD_BYTES
        transfer += (hot_count + pending_count) * WORD_BYTES + page_count * PAGE_BYTES
        full += (int(event["cache_position"]) + 1) * WORD_BYTES
        page_requests += page_count; full_pages += full_count; tail_pages += page_count - full_count
    return {"event_count": len(events), "full_kv_hbm_bytes_no_reuse": full, "packed_useful_kv_bytes": useful, "packed_page_rounded_hbm_bytes": transfer, "hot_useful_bytes": hot * WORD_BYTES, "pending_useful_bytes": pending * WORD_BYTES, "packed_useful_bytes": packed * WORD_BYTES, "packed_page_requests": page_requests, "packed_full_page_requests": full_pages, "packed_tail_page_requests": tail_pages}


def gqa_groups(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[int, int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        groups[(int(event["layer"]), int(event["kv_head"]), int(event["cache_position"]), str(event["phase"]))].append(event)
    representatives=[]
    for (layer, head, position, phase), rows in groups.items():
        if len(rows) != GQA_GROUP:
            raise ValueError("GQA reuse group does not contain exactly four query-head events")
        queries=sorted(int(row["query_head"]) for row in rows)
        if queries != list(range(head * GQA_GROUP, (head + 1) * GQA_GROUP)):
            raise ValueError("GQA reuse query-head members invalid")
        signatures=[source_state(row) for row in rows]
        if any(sig != signatures[0] for sig in signatures[1:]):
            raise ValueError("GQA group source/page state differs; reuse cannot be claimed")
        representatives.append(rows[0])
    return representatives


def final_residency(manifest: dict[str, Any]) -> dict[str, int | float]:
    layers=manifest["outcomes"]["external_storage_trace_on"]["final_state"]["layers"]
    if [row.get("layer") for row in layers] != list(range(LAYERS)):
        raise ValueError("final state layer coverage invalid")
    packed_tokens=packed_pages=pending=0
    for layer in layers:
        heads=layer.get("heads", [])
        if [row.get("kv_head") for row in heads] != list(range(KV_HEADS)):
            raise ValueError("final state head coverage invalid")
        for row in heads:
            packed_tokens += int(row["packed_tokens"]); packed_pages += int(row["packed_page_count"]); pending += int(row["pending_tokens"])
    if pending:
        raise ValueError("A4.13.2 requires zero final pending residual")
    final_lengths=[]
    # Each selected layer observes the same request length; use its last observed source position.
    return {"packed_tokens":packed_tokens,"packed_pages":packed_pages,"final_pending_tokens":pending}


def residency_from_events(events: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, int | float]:
    finals=final_residency(manifest)
    final_positions: dict[int,int] = defaultdict(lambda:-1)
    for event in events: final_positions[int(event["layer"])] = max(final_positions[int(event["layer"])], int(event["cache_position"]))
    if set(final_positions) != set(range(LAYERS)) or len(set(final_positions.values())) != 1:
        raise ValueError("final causal length differs across layers")
    final_tokens=next(iter(final_positions.values()))+1
    full=final_tokens*LAYERS*KV_HEADS*WORD_BYTES
    hot=LAYERS*KV_HEADS*min(128,final_tokens)*WORD_BYTES
    packed_logical=int(finals["packed_tokens"])*WORD_BYTES
    packed_slots=int(finals["packed_pages"])*PAGE_BYTES
    route=hot+packed_slots
    return {"final_causal_tokens_per_layer":final_tokens,"full_kv_resident_payload_bytes":full,"route_a_hot_resident_payload_bytes":hot,"route_a_packed_logical_payload_bytes":packed_logical,"route_a_packed_page_slot_payload_bytes":packed_slots,"route_a_final_pending_payload_bytes":0,"route_a_total_resident_payload_bytes":route,"route_a_vs_full_resident_payload_ratio":route/full,"route_a_logical_position_sidecar_bytes":int(finals["packed_tokens"])*8,"route_a_page_slot_position_sidecar_capacity_bytes":int(finals["packed_pages"])*PAGE_TOKENS*8}


def row_for_workload(workload: str, a4131: dict[str, Any]) -> dict[str, Any]:
    row=next(item for item in a4131["workload_rows"] if item["workload"]==workload)
    p3=next(item for item in row["declared_three_candidate_mappings"] if item["candidate"].startswith("P3_"))
    return {"p3":p3,"merge":row["direct_software_payload_access"]["deterministic_merge_interface"]}


def accounting(workload: str, events: list[dict[str, Any]], manifest: dict[str, Any], a4131: dict[str, Any]) -> dict[str, Any]:
    no_reuse=metric(events); groups=gqa_groups(events); reuse=metric(groups); residency=residency_from_events(events,manifest); prior=row_for_workload(workload,a4131)
    if no_reuse["event_count"] != reuse["event_count"] * GQA_GROUP:
        raise ValueError("GQA event reduction is not exactly four-way")
    sector=lambda n: math.ceil(n/SECTOR_BYTES)
    def baseline(name: str, data: dict[str,int]) -> dict[str,Any]:
        if name == "full_kv_hbm_no_reuse":
            full_bytes=data["full_kv_hbm_bytes_no_reuse"]
            return {"baseline":name,"reference_attention_evaluations":data["event_count"],"useful_kv_bytes":full_bytes,"declared_hbm_transferred_bytes":full_bytes,"declared_256B_accounting_sectors":sector(full_bytes),"useful_bytes_per_transferred_byte":1.0,"packed_page_requests":0,"packed_full_page_requests":0,"packed_tail_page_requests":0,"average_packed_bytes_per_page_request":0,"source_bytes":{"full_kv":full_bytes}}
        transferred=data["full_kv_hbm_bytes_no_reuse"] if name=="full_kv_hbm_no_reuse" else data["packed_page_rounded_hbm_bytes"]
        useful=data["full_kv_hbm_bytes_no_reuse"] if name=="full_kv_hbm_no_reuse" else data["packed_useful_kv_bytes"]
        return {"baseline":name,"reference_attention_evaluations":data["event_count"],"useful_kv_bytes":useful,"declared_hbm_transferred_bytes":transferred,"declared_256B_accounting_sectors":sector(transferred),"useful_bytes_per_transferred_byte":useful/transferred if transferred else 1.0,"packed_page_requests":data["packed_page_requests"],"packed_full_page_requests":data["packed_full_page_requests"],"packed_tail_page_requests":data["packed_tail_page_requests"],"average_packed_bytes_per_page_request":(data["packed_page_rounded_hbm_bytes"]-data["hot_useful_bytes"]-data["pending_useful_bytes"])/data["packed_page_requests"] if data["packed_page_requests"] else 0,"source_bytes":{"hot":data["hot_useful_bytes"],"pending":data["pending_useful_bytes"],"packed_useful":data["packed_useful_bytes"]}}
    return {"workload":workload,"resident_capacity_accounting":residency,"full_kv_hbm_baseline":baseline("full_kv_hbm_no_reuse",no_reuse),"packed_no_hardware_reuse":baseline("packed_no_hardware_reuse",no_reuse),"packed_legal_gqa_reuse":baseline("packed_legal_gqa_reuse",reuse),"gqa_reuse_accounting":{"gqa_group_size":GQA_GROUP,"event_level_groups_validated":reuse["event_count"],"hbm_bytes_avoided_vs_packed_no_reuse":no_reuse["packed_page_rounded_hbm_bytes"]-reuse["packed_page_rounded_hbm_bytes"],"hbm_byte_ratio_vs_packed_no_reuse":reuse["packed_page_rounded_hbm_bytes"]/no_reuse["packed_page_rounded_hbm_bytes"],"minimum_packed_page_source_buffer_bytes":PAGE_BYTES,"four_query_head_partial_tuple_interface_bytes_if_fp32":GQA_GROUP*(128+2)*4,"boundary":"Reuse is accepted only for four event-level-equal source/page states. Buffer and partial-tuple sizes are interfaces, not selected SRAM/ports/physical transfers."},"p3_admission_staging_mapping_carried_from_a4131":prior["p3"],"merge_interface_carried_from_a4131":prior["merge"],"metadata_traffic":"not modeled: A4.12 supplies metadata resource accounting, not a physical metadata traffic trace"}


def materialize(output: Path, files: dict[str,Path]) -> dict[str,dict[str,str]]:
    folder=output/"input_artifacts"; folder.mkdir(); result={}
    for label,path in files.items():
        target=folder/f"{label}_{path.name}"; shutil.copyfile(path,target); result[label]={"source_path":str(path),"materialized_copy":str(target),"sha256":sha256_file(target)}
    return result


def main() -> None:
    args=parse_args(); a4131=read_a4131(args.a4131_report); parsed={w:read_manifest(getattr(args,f"{w}_manifest"),w) for w in WORKLOADS}
    for _manifest,events in parsed.values(): validate_events(events); gqa_groups(events)
    if args.preflight_only:
        print("A4.13.2 preflight passed: exact A4.13.1 and all event-level legal GQA reuse groups validated; no output created."); return
    if args.output_dir.exists(): raise FileExistsError(args.output_dir)
    args.output_dir.mkdir(parents=True)
    artifacts=materialize(args.output_dir,{"a4131_report":args.a4131_report,**{f"{w}_manifest":getattr(args,f"{w}_manifest") for w in WORKLOADS}})
    config={"stage":"A4.13.2","baselines":["full_kv_hbm_no_reuse","packed_no_hardware_reuse","packed_legal_gqa_reuse"],"gqa_group_size":GQA_GROUP,"kv_word_bytes":WORD_BYTES,"packed_page_tokens":PAGE_TOKENS,"packed_page_bytes":PAGE_BYTES,"declared_accounting_sector_bytes":SECTOR_BYTES,"payload_organization":"A4.13.1 P3 carried reference only; no new P4/P5"}
    report={"schema_version":SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"execution_classification":"exact scalar software source/page trace replay plus three fixed declared HBM accounting baselines; not measured HBM transactions/bandwidth, traffic, timing, PPA, or RTL","config":config,"config_hash":stable_hash(config),"input_artifacts":artifacts,"workload_rows":[accounting(w,*parsed[w],a4131) for w in WORKLOADS],"evidence_classes":{"direct_software_observation":["source token counts and packed page state per reference attention evaluation","cache position, query/KV-head GQA membership","final external-storage packed/pending state"],"deterministic_accounting":["full causal K/V byte baseline","64-token page rounding","event-level four-query-head reuse grouping","256-B accounting sector count"],"declared_mapping_only":["all named HBM bytes and source-buffer interface","P3 admission/staging movement carried from A4.13.1"]},"semantic_guards":{"exact_a4131_inputs_bound":True,"three_baselines_only_not_new_architecture_variants":True,"gqa_reuse_requires_event_level_identical_four_head_groups":True,"packed_cold_remains_hbm_resident_in_accounting":True,"p2_not_promoted_as_default":True,"no_pruning_admission_queue_execution_scheduler_or_metadata_contract_change":True,"no_measured_hbm_traffic_bandwidth_timing_area_energy_or_net_benefit_claim":True},"boundaries":["The 256-B accounting sector is a reporting granule, not a selected HBM protocol or native transaction count.","Full-KV and packed bytes are explicit accounting mappings from software scalar traces. They are not profiler measurements or physical memory traffic.","GQA reuse requires a local streaming source/page buffer and four consumer partial states; this report provides interface sizes only, not SRAM macro, port, scheduling, cycle, or energy evidence.","Metadata traffic, page-table/handle width, burst protocol, physical allocation, DMA, and merge transfers remain unresolved for later A4.13 physicalization."]}
    path=args.output_dir/"a4132_packed_cold_hbm_traffic_report.json"; path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"A4.13.2 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} workloads={len(report['workload_rows'])} baselines=3")


if __name__ == "__main__": main()
