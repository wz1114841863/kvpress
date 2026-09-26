#!/usr/bin/env python3
"""A4.13.1 exactly-three-mapping payload envelope from scalar software traces."""
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

SCHEMA = "kvzap-route-a4131-payload-organization-envelope-1.0"
TRACE_SCHEMA = "kvzap-route-a4131-payload-access-trace-1.0"
EXPECTED_A4130 = ("kvzap-route-a4130-payload-interface-inventory-1.0", "d9138647361925baa7f76bac89d1a0b2247f9eb0d1ec6a2789b98dd9cea8d1d8")
WORKLOADS = ("retrieval", "summarization", "reasoning")
KV_BYTES, PAGE_TOKENS, LAYERS, KV_HEADS, MERGE_PARTIAL_SCALARS = 512, 64, 36, 8, 130


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.13.1 exactly-three-mapping payload organization envelope; not measured HBM traffic, PPA, timing, or RTL.")
    p.add_argument("--a4130-report", type=Path, required=True)
    for workload in WORKLOADS:
        p.add_argument(f"--{workload}-manifest", type=Path, required=True)
    p.add_argument("--preflight-only", action="store_true", help="Validate inputs and scalar trace conservation without output.")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def stat(values: list[int]) -> dict[str, int]:
    ordered = sorted(values)
    pick = lambda q: ordered[int((len(ordered) - 1) * q)] if ordered else 0
    return {"count": len(values), "min": ordered[0] if ordered else 0, "p50": pick(.5), "p95": pick(.95), "p99": pick(.99), "max": ordered[-1] if ordered else 0, "sum": sum(values)}


def read_rows(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_a4130(path: Path) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != EXPECTED_A4130[1]:
        raise ValueError("A4.13.1 requires exact accepted A4.13.0 report")
    report = json.loads(path.read_text(encoding="utf-8"))
    layout = report.get("deterministic_payload_layout", {})
    if report.get("schema_version") != EXPECTED_A4130[0] or report.get("status") != "complete" or (layout.get("kv_token_word_bytes"), layout.get("page_payload_bytes"), layout.get("logical_position_sidecar_bytes")) != (KV_BYTES, PAGE_TOKENS * KV_BYTES, PAGE_TOKENS * 8):
        raise ValueError("A4.13.0 payload interface is incompatible")
    return report


def read_manifest(path: Path, workload: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    config, guards = manifest.get("config", {}), manifest.get("observational_guards", {})
    required = ("payload_recorder_armed_on_prefill_armed_external_storage_path", "trace_off_trace_on_generated_token_ids_equal", "trace_on_same_mask_dense_generated_token_ids_equal", "a4131_token_digest_equals_accepted_a4112b", "replay_mask_consumption_complete_all_paths", "all_layers_all_kv_heads_external_storage_covered", "recorders_final_packed_pending_cold_state_unchanged", "no_drop_or_reorder_or_new_full_kv_fallback")
    if manifest.get("schema_version") != TRACE_SCHEMA or manifest.get("status") != "complete" or (config.get("preset"), config.get("window_size"), config.get("page_tokens"), config.get("admission_budget"), config.get("target_layers"), config.get("target_kv_head")) != (workload, 128, PAGE_TOKENS, 512, ["all"], "all") or not all(guards.get(k) is True for k in required):
        raise ValueError(f"{workload}: A4.13.1 trace manifest is incompatible")
    life, payload = manifest.get("lifecycle_transition_trace", {}), manifest.get("payload_access_trace", {})
    lp, pp = path.parent / life.get("path", ""), path.parent / payload.get("path", "")
    if life.get("schema_version") != "kvzap-route-a432-logical-lifecycle-transitions-1.0" or payload.get("schema_version") != "kvzap-route-a424-logical-attention-events-1.0" or not lp.is_file() or not pp.is_file() or sha256_file(lp) != life.get("sha256") or sha256_file(pp) != payload.get("sha256"):
        raise ValueError(f"{workload}: A4.13.1 trace hashes/schema mismatch")
    return manifest, read_rows(lp), read_rows(pp)


def validate_lifecycle(events: list[dict[str, Any]]) -> None:
    last: dict[int, int] = {}
    for index, event in enumerate(events):
        layer, start, end = int(event.get("layer", -1)), int(event.get("start_position", -1)), int(event.get("end_position", -2))
        if int(event.get("logical_transition_sequence", -1)) != index or event.get("timestamps_recorded") is not False or layer not in range(LAYERS) or end < start or int(event.get("input_token_count", -1)) != end - start + 1 or start != last.get(layer, -1) + 1:
            raise ValueError("invalid lifecycle sequence/position")
        last[layer] = end
        rows = event.get("heads", [])
        if [row.get("kv_head") for row in rows] != list(range(KV_HEADS)):
            raise ValueError("invalid lifecycle KV-head coverage")
        for row in rows:
            fields = ("pending_tokens_before_maturity", "matured_kept_tokens", "matured_dropped_tokens", "pending_tokens_after_maturity", "admitted_tokens", "pending_tokens_after_service", "packed_tokens_before", "packed_tokens_after_service", "packed_page_count_after_service", "packed_full_page_count_after_service", "packed_tail_tokens_after_service")
            if any(not isinstance(row.get(k), int) or row[k] < 0 for k in fields) or row["pending_tokens_after_maturity"] != row["pending_tokens_before_maturity"] + row["matured_kept_tokens"] or row["pending_tokens_after_service"] != row["pending_tokens_after_maturity"] - row["admitted_tokens"] or row["packed_tokens_after_service"] != row["packed_tokens_before"] + row["admitted_tokens"]:
                raise ValueError("invalid lifecycle conservation")
    if not events or set(last) != set(range(LAYERS)):
        raise ValueError("incomplete lifecycle coverage")


def validate_payload(events: list[dict[str, Any]]) -> None:
    covered: dict[int, set[int]] = defaultdict(set)
    for index, event in enumerate(events):
        layer, head = int(event.get("layer", -1)), int(event.get("kv_head", -1))
        rows = event.get("source_decisions", [])
        if int(event.get("logical_event_sequence", -1)) != index or event.get("merge_after_source_decisions") is not True or layer not in range(LAYERS) or head not in range(KV_HEADS) or not isinstance(event.get("query_head"), int) or not isinstance(event.get("cache_position"), int) or [row.get("source") for row in rows] != ["hot", "pending", "packed"] or any(not isinstance(row.get("record_count"), int) or row["record_count"] < 0 for row in rows):
            raise ValueError("invalid payload-access event")
        covered[layer].add(head)
    if not events or {layer: sorted(heads) for layer, heads in covered.items()} != {layer: list(range(KV_HEADS)) for layer in range(LAYERS)}:
        raise ValueError("incomplete payload-access coverage")


def final_packed(manifest: dict[str, Any]) -> dict[str, int]:
    layers = manifest["outcomes"]["external_storage_trace_on"]["final_state"]["layers"]
    tokens = pages = full = tail = 0
    if [row.get("layer") for row in layers] != list(range(LAYERS)):
        raise ValueError("invalid final layer coverage")
    for layer in layers:
        heads = layer.get("heads", [])
        if [row.get("kv_head") for row in heads] != list(range(KV_HEADS)):
            raise ValueError("invalid final KV-head coverage")
        for row in heads:
            tokens += int(row["packed_tokens"]); pages += int(row["packed_page_count"]); full += int(row["packed_full_page_count"]); tail += int(row["packed_tail_tokens"])
    if tokens != full * PAGE_TOKENS + tail or full > pages:
        raise ValueError("invalid final packed page conservation")
    return {"packed_tokens": tokens, "packed_pages": pages, "packed_full_pages": full, "packed_tail_tokens": tail}


def lifecycle_envelope(events: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    head_max: dict[tuple[int, int], int] = defaultdict(int); layer_max: dict[int, int] = defaultdict(int)
    admitted_epochs=[]; mature=0
    for event in events:
        total=0; admitted_epochs.append(int(event["admitted_tokens_total"]))
        for row in event["heads"]:
            key=(int(event["layer"]),int(row["kv_head"])); pending=int(row["pending_tokens_after_maturity"])
            head_max[key]=max(head_max[key],pending); total += pending; mature += int(row["matured_kept_tokens"])
        layer_max[int(event["layer"])]=max(layer_max[int(event["layer"])],total)
    final=final_packed(manifest); admitted=sum(admitted_epochs)
    if mature != admitted or admitted != final["packed_tokens"]:
        raise ValueError("zero-residual retained/admitted/final packed conservation failed")
    return {"admitted_retained_tokens":admitted,"admission_epoch_tokens":stat(admitted_epochs),"per_layer_kv_head_pending_peak_tokens":stat(list(head_max.values())),"isolated_per_layer_kv_head_pending_provision_tokens":sum(head_max.values()),"shared_per_layer_pending_provision_tokens":sum(layer_max.values()),"per_layer_shared_pending_peak_tokens":stat(list(layer_max.values())),"final_packed_state":final}


def attention_envelope(events: list[dict[str, Any]]) -> dict[str, Any]:
    visits={name:0 for name in ("hot","pending","packed")}; by_phase=defaultdict(lambda:{name:0 for name in visits}); by_position=defaultdict(int); cold_each=[]; hist=defaultdict(int); extra=0
    for event in events:
        source={row["source"]:int(row["record_count"]) for row in event["source_decisions"]}
        for name,count in source.items(): visits[name]+=count; by_phase[str(event["phase"])][name]+=count
        cold=source["pending"]+source["packed"]; cold_each.append(cold); by_position[(int(event["layer"]),int(event["cache_position"]))]+=cold
        nonempty=sum(count>0 for count in source.values()); hist[nonempty]+=1; extra += max(0,nonempty-1)
    cold=visits["pending"]+visits["packed"]
    return {"reference_attention_evaluations":len(events),"direct_logical_source_token_visits":visits,"direct_logical_cold_kv_token_visits":cold,"direct_logical_cold_kv_bytes_if_one_kv_word_per_visit":cold*KV_BYTES,"per_reference_query_head_evaluation_cold_visits":stat(cold_each),"per_layer_query_position_cold_visits":stat(list(by_position.values())),"by_phase_source_token_visits":dict(by_phase),"nonempty_source_count_histogram":{str(k):v for k,v in sorted(hist.items())},"direct_merge_event_count":len(events),"deterministic_merge_interface":{"additional_nonempty_source_partials_beyond_first":extra,"partial_tuple_scalar_elements":MERGE_PARTIAL_SCALARS,"partial_tuple_bytes_if_materialized_as_fp32":MERGE_PARTIAL_SCALARS*4,"additional_partial_tuple_interface_bytes_if_materialized_as_fp32":extra*MERGE_PARTIAL_SCALARS*4,"boundary":"Tuple bytes are interface accounting, not measured merge traffic, compute, bandwidth, timing, area, or energy."}}


def packing_envelope(life: dict[str, Any]) -> dict[str, Any]:
    final=life["final_packed_state"]; logical=final["packed_tokens"]*KV_BYTES; capacity=final["packed_pages"]*PAGE_TOKENS*KV_BYTES
    if not logical: raise ValueError("A4.13.1 requires nonempty packed payload")
    return {"final_packed_logical_kv_bytes":logical,"final_packed_page_payload_capacity_bytes":capacity,"final_packed_page_payload_utilization":logical/capacity,"final_packed_page_capacity_amplification":capacity/logical,"final_logical_position_sidecar_bytes":final["packed_tokens"]*8,"final_page_slot_position_sidecar_capacity_bytes":final["packed_pages"]*PAGE_TOKENS*8,"boundary":"Fixed final software page-slot accounting only; not physical allocation/macro or traffic."}


def candidates(life: dict[str, Any], attention: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tokens=life["admitted_retained_tokens"]; byte=tokens*KV_BYTES; pending=attention["direct_logical_source_token_visits"]["pending"]*KV_BYTES; packed=attention["direct_logical_source_token_visits"]["packed"]*KV_BYTES
    isolated=life["isolated_per_layer_kv_head_pending_provision_tokens"]*KV_BYTES; shared=life["shared_per_layer_pending_provision_tokens"]*KV_BYTES; stage=LAYERS*PAGE_TOKENS*KV_BYTES; chunks=sum(math.ceil(int(e["admitted_tokens_total"])/PAGE_TOKENS) for e in events if int(e["admitted_tokens_total"])>0)
    common={"admission_retained_kv_tokens":tokens,"one_kv_word_bytes":KV_BYTES,"direct_reference_attention_pending_logical_bytes":pending,"direct_reference_attention_packed_logical_bytes":packed}
    return [
        {"candidate":"P1_independent_pending_hbm_backing_to_packed_hbm","declared_mapping":"pending HBM write, pending HBM read for admission, packed HBM write; pending+packed logical source traversal maps to HBM reads","capacity_envelope":{"isolated_per_layer_kv_head_pending_bytes":isolated},"declared_admission_movement":{"hbm_pending_write_bytes":byte,"hbm_pending_read_bytes":byte,"hbm_packed_write_bytes":byte,"total_declared_hbm_bytes":3*byte},"declared_attention_mapping":{"hbm_pending_read_bytes":pending,"hbm_packed_read_bytes":packed,"total_declared_hbm_read_bytes":pending+packed},**common},
        {"candidate":"P2_layer_local_pending_sram_to_packed_hbm","declared_mapping":"shared layer-local pending SRAM write/read; packed HBM write; pending source maps SRAM and packed source maps HBM","capacity_envelope":{"shared_per_layer_pending_sram_bytes":shared},"declared_admission_movement":{"sram_pending_write_bytes":byte,"sram_pending_read_bytes":byte,"hbm_packed_write_bytes":byte,"total_declared_hbm_bytes":byte},"declared_attention_mapping":{"sram_pending_read_bytes":pending,"hbm_packed_read_bytes":packed,"total_declared_hbm_read_bytes":packed},**common},
        {"candidate":"P3_one_64token_sram_staging_page_with_pending_hbm_backing_to_packed_hbm","declared_mapping":"P1 HBM pending backing plus one 64-token SRAM staging page/layer; stage chunks admission without reordering/drop; pending+packed source maps to HBM reads","capacity_envelope":{"isolated_per_layer_kv_head_pending_hbm_bytes":isolated,"one_page_per_layer_sram_staging_bytes":stage,"staging_page_tokens":PAGE_TOKENS},"declared_admission_movement":{"hbm_pending_write_bytes":byte,"hbm_pending_read_bytes":byte,"sram_stage_write_bytes":byte,"sram_stage_read_bytes":byte,"hbm_packed_write_bytes":byte,"total_declared_hbm_bytes":3*byte,"total_declared_sram_stage_bytes":2*byte,"staging_fill_chunks":chunks},"declared_attention_mapping":{"hbm_pending_read_bytes":pending,"hbm_packed_read_bytes":packed,"total_declared_hbm_read_bytes":pending+packed},**common},
    ]


def materialize(output: Path, inputs: dict[str, Path]) -> dict[str, dict[str,str]]:
    folder=output/"input_artifacts"; folder.mkdir(); result={}
    for label,path in inputs.items():
        target=folder/f"{label}_{path.name}"; shutil.copyfile(path,target); result[label]={"source_path":str(path),"materialized_copy":str(target),"sha256":sha256_file(target)}
    return result


def main() -> None:
    args=parse_args(); read_a4130(args.a4130_report); parsed={w:read_manifest(getattr(args,f"{w}_manifest"),w) for w in WORKLOADS}
    for _manifest,life,payload in parsed.values(): validate_lifecycle(life); validate_payload(payload)
    if args.preflight_only:
        print("A4.13.1 preflight passed: exact A4.13.0 and all three guarded payload-access traces validate; no output created."); return
    if args.output_dir.exists(): raise FileExistsError(args.output_dir)
    args.output_dir.mkdir(parents=True); artifacts=materialize(args.output_dir,{"a4130_report":args.a4130_report,**{f"{w}_manifest":getattr(args,f"{w}_manifest") for w in WORKLOADS}})
    rows=[]
    for workload,(manifest,life_events,payload_events) in parsed.items():
        life=lifecycle_envelope(life_events,manifest); attention=attention_envelope(payload_events)
        rows.append({"workload":workload,"direct_software_lifecycle":life,"direct_software_payload_access":attention,"deterministic_page_accounting":packing_envelope(life),"declared_three_candidate_mappings":candidates(life,attention,life_events)})
    config={"stage":"A4.13.1","fixed_payload_word_bytes":KV_BYTES,"fixed_page_tokens":PAGE_TOKENS,"candidates":["P1_independent_pending_hbm_backing_to_packed_hbm","P2_layer_local_pending_sram_to_packed_hbm","P3_one_64token_sram_staging_page_with_pending_hbm_backing_to_packed_hbm"]}
    report={"schema_version":SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"execution_classification":"direct scalar lifecycle/source traversal observations plus exactly-three declared payload mappings; not measured HBM traffic, physical capacity, timing, PPA, or RTL","config":config,"config_hash":stable_hash(config),"input_artifacts":artifacts,"a4130_binding":{"sha256":EXPECTED_A4130[1],"payload_word_bytes":KV_BYTES,"page_tokens":PAGE_TOKENS},"workload_rows":rows,"evidence_classes":{"direct_software_observation":["lifecycle pending/admitted/final packed state","per-reference-attention source record counts","merge marker and nonempty source combinations"],"deterministic_accounting":["512-B word multiplication","64-token final page capacity/utilization","130-element reference partial tuple interface"],"declared_mapping_only":["P1/P2/P3 HBM/SRAM placement and movement","mapping logical source traversal to tier reads"]},"semantic_guards":{"exact_a4130_payload_interface_bound":True,"a4112b_external_storage_correctness_inherited_and_rechecked":True,"prefill_armed_payload_recorder_does_not_change_tokens_or_final_state":True,"all_layers_all_kv_heads_and_replay_complete":True,"original_mask_pruning_admission_and_commit_semantics_unchanged":True,"a410_queue_contract_not_retuned_or_reinterpreted_as_payload_capacity":True,"exactly_three_predeclared_payload_mappings":True,"no_drop_reorder_full_kv_fallback_queue_execution_or_scheduler_variant":True,"no_physical_traffic_timing_area_energy_or_net_benefit_claim":True},"boundaries":["Source record counts are logical software-reference traversals, not physical memory commands. Candidate tier traffic is an explicit mapping only.","Summed per-layer pending maxima form a candidate static provision envelope, not a measured allocator peak or simultaneous physical maximum.","Page capacity excludes PTE/address/burst/allocator/DMA/macro overhead.","Merge tuple interface bytes do not establish a physical merge transfer, compute count, latency, bandwidth, area, or energy."]}
    path=args.output_dir/"a4131_payload_organization_envelope_report.json"; path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"A4.13.1 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} workloads={len(rows)} candidates=3")


if __name__ == "__main__": main()
