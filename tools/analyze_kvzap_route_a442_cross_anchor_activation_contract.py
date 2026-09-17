#!/usr/bin/env python3
"""No-model A4.4.2 cross-anchor activation-contract closeout.

The report SHA-binds completed Qwen A4.4.1 and Llama A4.4.0 artifacts.  It
checks the two anchors' contract predicates and trace integrity separately;
it deliberately emits no numerical pooling, common resource envelope, or
hardware parameter derivation.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a442-cross-anchor-activation-contract-1.0"
QWEN_SCHEMA = "kvzap-route-a441-qwen-deferred-activation-contract-1.0"
LLAMA_SCHEMA = "kvzap-route-a440-deferred-activation-contract-1.0"
WORKLOADS = ("retrieval", "summarization", "reasoning")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.4.2 no-model Qwen/Llama activation-contract closeout; no common hardware envelope or parameter selection."
    )
    parser.add_argument("--qwen-report", type=Path, required=True)
    parser.add_argument("--llama-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def read_completed_report(path: Path, *, expected_schema: str, anchor: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{anchor} report is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != expected_schema or value.get("status") != "complete":
        raise ValueError(f"{anchor} report is not a completed {expected_schema} artifact")
    if value.get("execution_classification") != "functional fixed-request activation/bypass evidence plus timestamp-free logical lifecycle events; no measured or modeled hardware result":
        raise ValueError(f"{anchor} report changed its required evidence classification")
    return value


def layer_count_for(report: dict[str, Any], *, anchor: str) -> int:
    if anchor == "qwen":
        count = int(report.get("model_structure", {}).get("layer_count", 0))
    else:
        count = len(report.get("per_workload", {}).get("retrieval", {}).get("activation_contract", {}).get("deferred_activation_summary", {}).get("layers", []))
    if count <= 0:
        raise ValueError(f"{anchor} report lacks a positive layer count")
    return count


def validate_trace(*, report_path: Path, entry: dict[str, Any], expected_layers: int, anchor: str, workload: str) -> dict[str, Any]:
    relative = entry.get("path")
    if not isinstance(relative, str):
        raise ValueError(f"{anchor}/{workload}: trace path is absent")
    path = report_path.parents[1] / relative
    if not path.is_file() or sha256_file(path) != entry.get("sha256"):
        raise ValueError(f"{anchor}/{workload}: post-commit trace hash does not match report")
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle]
    if len(events) != int(entry.get("event_count", -1)):
        raise ValueError(f"{anchor}/{workload}: post-commit trace event count differs from report")
    if {event.get("layer") for event in events} != set(range(expected_layers)):
        raise ValueError(f"{anchor}/{workload}: post-commit trace lacks complete layer coverage")
    if not events or any(event.get("timestamps_recorded") is not False or event.get("phase") != "decode" or event.get("input_token_count") != 1 for event in events):
        raise ValueError(f"{anchor}/{workload}: post-commit trace has unexpected timing or non-decode rows")
    return {"path": relative, "sha256": entry["sha256"], "event_count": len(events), "layer_count": expected_layers, "timestamps_recorded": False}


def validate_workload(*, report_path: Path, anchor: str, workload: str, row: dict[str, Any], layer_count: int) -> dict[str, Any]:
    bypass = row.get("benefit_bypass_contract")
    active = row.get("activation_contract")
    if not isinstance(bypass, dict) or not isinstance(active, dict):
        raise ValueError(f"{anchor}/{workload}: missing bypass or activation contract")
    if bypass.get("deferred_decode_steps") != 8 or active.get("deferred_decode_steps") != 1:
        raise ValueError(f"{anchor}/{workload}: does not retain D=8 bypass and D=1 activation branches")
    if bypass.get("generated_token_ids_equal_full_kv") is not True or active.get("forced_token_inputs_equal_full_kv") is not True:
        raise ValueError(f"{anchor}/{workload}: Full-KV token trajectory contract failed")
    bypass_layers = bypass.get("deferred_activation_summary", {}).get("layers", [])
    active_layers = active.get("deferred_activation_summary", {}).get("layers", [])
    if len(bypass_layers) != layer_count or len(active_layers) != layer_count:
        raise ValueError(f"{anchor}/{workload}: contract layer count differs from report structure")
    if {item.get("layer") for item in bypass_layers} != set(range(layer_count)) or {item.get("layer") for item in active_layers} != set(range(layer_count)):
        raise ValueError(f"{anchor}/{workload}: contract layer identifiers are incomplete")
    for item in bypass_layers:
        if item.get("activation_committed") or item.get("route_a_logical_state_exists_at_end") or item.get("mode_at_trace_end") != "full_kv_bypass" or item.get("full_kv_prefix_decode_calls") != 7 or item.get("native_cache_mutated_or_freed"):
            raise ValueError(f"{anchor}/{workload}: end-before-activation branch is not pure Full-KV")
    histories, mature_positions, journals, kv_heads = set(), set(), set(), set()
    for item in active_layers:
        event = item.get("activation_event")
        if not item.get("activation_committed") or not item.get("route_a_logical_state_exists_at_end") or item.get("mode_at_trace_end") != "route_a_active" or item.get("native_cache_mutated_or_freed") or not isinstance(event, dict):
            raise ValueError(f"{anchor}/{workload}: active branch did not retain Route-A state")
        if event.get("mode_before_commit") != "full_kv_bypass" or event.get("mode_after_commit") != "route_a_active" or event.get("activation_decode_call_after_full_prefix") != 1 or event.get("route_a_logical_state_existed_before_commit") or event.get("native_cache_mutated_or_freed_by_commit"):
            raise ValueError(f"{anchor}/{workload}: activation commit boundary is invalid")
        heads = event.get("heads")
        if not isinstance(heads, list) or not heads or event.get("journal_mask_decision_count_before_commit") != event.get("history_token_count") * len(heads):
            raise ValueError(f"{anchor}/{workload}: activation journal is incomplete")
        if int(event.get("history_token_count", 0)) <= 128 or int(event.get("matured_position_count", 0)) <= 0:
            raise ValueError(f"{anchor}/{workload}: activation did not cross hot-window maturity")
        histories.add(int(event["history_token_count"])); mature_positions.add(int(event["matured_position_count"])); journals.add(int(event["journal_mask_decision_count_before_commit"])); kv_heads.add(len(heads))
    post_calls = active.get("post_commit_policy_decode_call_count_by_layer", {})
    if set(map(int, post_calls)) != set(range(layer_count)) or set(post_calls.values()) != {6}:
        raise ValueError(f"{anchor}/{workload}: post-commit q_len=1 call contract is incomplete")
    guard_layers = active.get("same_mask_numerical_guard_work", {}).get("layers", [])
    if len(guard_layers) != layer_count or any(int(item.get("work_count", 0)) <= 0 for item in guard_layers):
        raise ValueError(f"{anchor}/{workload}: post-commit numerical guard work is incomplete")
    totals = active.get("activation_totals_over_layers_and_kv_heads", {})
    required = ("matured_kept_tokens", "matured_dropped_tokens", "pending_tokens_after_commit", "admitted_tokens", "hot_tokens_after_commit", "packed_tokens_after_commit", "logical_page_count_after_commit")
    if any(not isinstance(totals.get(key), int) or totals[key] < 0 for key in required) or totals["matured_kept_tokens"] <= 0 or totals["packed_tokens_after_commit"] <= 0:
        raise ValueError(f"{anchor}/{workload}: activation scalar totals are incomplete")
    trace = validate_trace(report_path=report_path, entry=row.get("post_commit_logical_trace", {}), expected_layers=layer_count, anchor=anchor, workload=workload)
    ulp = active.get("execution_dtype_ulp_breach_summary", {}).get("layers", [])
    return {
        "anchor": anchor,
        "workload": workload,
        "layer_count": layer_count,
        "kv_head_count_per_layer": sorted(kv_heads),
        "context_tokens": int(row["request"]["context_tokens"]),
        "activation_history_tokens_per_layer": sorted(histories),
        "matured_positions_per_layer": sorted(mature_positions),
        "journal_decisions_per_layer": sorted(journals),
        "bypass_branch": {"deferred_decode_steps": 8, "mode_at_end": "full_kv_bypass", "route_a_logical_state_constructed": False, "native_cache_mutated_or_freed": False, "generated_token_ids_equal_full_kv": True},
        "activation_branch": {"deferred_decode_steps": 1, "mode_before_commit": "full_kv_bypass", "mode_after_commit": "route_a_active", "commit_count_per_layer": 1, "pre_commit_route_a_logical_state": False, "native_cache_mutated_or_freed": False, "post_commit_q_len_one_calls_per_layer": 6, "forced_token_inputs_equal_full_kv": True, "same_mask_numerical_guard_work_per_layer_positive": True},
        "activation_logical_state_totals": {key: totals[key] for key in required},
        "post_commit_trace": trace,
        "record_only_ulp_breach_count": sum(int(item.get("breach_count", 0)) for item in ulp),
    }


def validate_anchor(*, path: Path, expected_schema: str, anchor: str) -> dict[str, Any]:
    report = read_completed_report(path, expected_schema=expected_schema, anchor=anchor)
    config = report.get("config", {})
    if config.get("fixed_new_tokens") != 8 or config.get("active_deferred_decode_steps") != 1 or config.get("bypass_deferred_decode_steps") != 8:
        raise ValueError(f"{anchor} report changed the fixed continuation or deferred-activation contract")
    rows = report.get("per_workload", {})
    if set(rows) != set(WORKLOADS):
        raise ValueError(f"{anchor} report does not contain the three required workloads")
    layers = layer_count_for(report, anchor=anchor)
    normalized = [validate_workload(report_path=path, anchor=anchor, workload=workload, row=rows[workload], layer_count=layers) for workload in WORKLOADS]
    return {"anchor": anchor, "report_path": str(path), "report_sha256": sha256_file(path), "report_schema": expected_schema, "layer_count": layers, "workload_rows": normalized}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    qwen = validate_anchor(path=args.qwen_report, expected_schema=QWEN_SCHEMA, anchor="qwen3_8b")
    llama = validate_anchor(path=args.llama_report, expected_schema=LLAMA_SCHEMA, anchor="llama31_8b_instruct")
    anchors = [qwen, llama]
    matrix = [
        {"anchor": row["anchor"], "workload": row["workload"], "bypass_pure_full_kv": True, "activation_commit_once": True, "pre_commit_route_a_state_absent": True, "native_cache_retained": True, "post_commit_route_a_active": True, "post_commit_same_mask_guard_work": True, "post_commit_trace_timestamp_free": True}
        for anchor in anchors for row in anchor["workload_rows"]
    ]
    if not all(all(value is True for key, value in row.items() if key not in {"anchor", "workload"}) for row in matrix):
        raise AssertionError("cross-anchor activation semantic invariant matrix is incomplete")
    config = {"qwen_report": str(args.qwen_report), "llama_report": str(args.llama_report), "comparison_rule": "contract_predicates_and_per_anchor_rows_only; no cross-model numeric pooling, averaging, min/max envelope, resource range, or parameter derivation"}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model archival contract decision over hash-checked functional and trace-derived inputs; not measured or modeled hardware evidence", "input_artifacts": {anchor["anchor"]: {key: anchor[key] for key in ("report_path", "report_sha256", "report_schema", "layer_count")} for anchor in anchors}, "anchor_rows": [row for anchor in anchors for row in anchor["workload_rows"]], "cross_anchor_semantic_invariant_matrix": matrix, "observational_guards": {"both_completed_reports_sha256_bound": True, "all_six_anchor_workload_rows_retained_separately": True, "bypass_pure_full_kv_each_row": True, "activation_commit_once_each_row": True, "pre_commit_route_a_state_absent_each_row": True, "native_cache_retained_each_row": True, "post_commit_same_mask_guard_work_each_row": True, "post_commit_traces_hash_checked_timestamp_free_each_row": True, "cross_model_numeric_pooling_or_parameter_derivation_absent": True, "no_hardware_parameter_selected": True}, "boundaries": ["A4.4.2 is a no-model archival decision over completed functional/trace-derived reports. It does not measure or model hardware.", "The six rows are deliberately not averaged, range-reduced, normalized into a common capacity/traffic envelope, or used to select FIFO/PTE/page/bank/burst/merge/PE/scheduler/controller parameters.", "Logical activation totals/pages remain reference-state accounting only; they are not allocator observations, physical capacity, HBM/DMA traffic, bursts, timing, latency, throughput, energy, area, hardware acceleration, architecture specification, or RTL evidence.", "Contract parity means the bounded activation/bypass semantics were observed under each anchor's own fixed continuation. It does not prove identical hardware needs, natural-generation behavior, general accuracy, or portability to arbitrary models or pruning frontends." ]}
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a442_cross_anchor_activation_contract_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.4.2 cross-anchor activation contract completed: {output}")


if __name__ == "__main__":
    main()
