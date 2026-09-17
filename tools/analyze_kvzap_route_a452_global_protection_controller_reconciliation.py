#!/usr/bin/env python3
"""A4.5.2 no-model reconciliation of local and request-global protection.

This closes the semantic gap between A4.5.0's request-global counterfactual
and A4.5.1's executable layer-local fallback primitive.  It derives only a
logical controller observation/effect boundary; it does not install a global
controller, model capacity, traffic, or timing.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import (
    LLAMA_SCHEMA,
    QWEN_SCHEMA,
    WORKLOADS,
    sha256_file,
    validate_anchor,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a452-global-protection-controller-reconciliation-1.0"
A450_SCHEMA = "kvzap-route-a450-capacity-protection-boundary-replay-1.0"
A451_SCHEMA = "kvzap-route-a451-capacity-protection-semantic-gate-1.0"
HIGH_WATERMARK = 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.5.2 no-model reconciliation of request-global and layer-local capacity protection; no controller implementation or hardware result."
    )
    parser.add_argument("--qwen-a44-report", type=Path, required=True)
    parser.add_argument("--llama-a44-report", type=Path, required=True)
    parser.add_argument("--a450-report", type=Path, required=True)
    parser.add_argument("--qwen-a451-report", type=Path, required=True)
    parser.add_argument("--llama-a451-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def read_completed(path: Path, *, schema: str, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != schema or value.get("status") != "complete":
        raise ValueError(f"{label} is not a completed {schema} artifact")
    return value


def activation_pending_by_layer(source_row: dict[str, Any], *, layer_count: int, label: str) -> dict[int, int]:
    layers = source_row["activation_contract"]["deferred_activation_summary"]["layers"]
    if {int(row["layer"]) for row in layers} != set(range(layer_count)):
        raise ValueError(f"{label}: activation snapshot lacks contiguous layer coverage")
    pending = {
        int(row["layer"]): sum(int(head["pending_tokens_after_commit"]) for head in row["activation_event"]["heads"])
        for row in layers
    }
    if any(value < 0 for value in pending.values()):
        raise ValueError(f"{label}: activation pending is negative")
    return pending


def a450_witness(a450: dict[str, Any], *, anchor: str, workload: str, anchor_sha256: str) -> dict[str, Any]:
    artifact = a450.get("input_artifacts", {}).get(anchor, {})
    if artifact.get("report_sha256") != anchor_sha256:
        raise ValueError(f"{anchor}/{workload}: A4.5.0 does not bind the supplied A4.4 report")
    rows = [
        row for row in a450.get("replay_rows", [])
        if row.get("anchor") == anchor and row.get("workload") == workload
        and row.get("policy", {}).get("pending_high_watermark") == HIGH_WATERMARK
    ]
    if len(rows) != 1:
        raise ValueError(f"{anchor}/{workload}: missing unique A4.5.0 C={HIGH_WATERMARK} row")
    row = rows[0]
    transition = row.get("transition")
    if row.get("mode_at_trace_end") != "protected_full_kv" or not isinstance(transition, dict):
        raise ValueError(f"{anchor}/{workload}: A4.5.0 lacks a protected-Full-KV witness")
    if transition.get("boundary") != "activation_commit_before_current_decode_append":
        raise ValueError(f"{anchor}/{workload}: A4.5.0 C={HIGH_WATERMARK} witness is not activation-boundary")
    return row


def reconcile_workload(*, anchor: str, workload: str, layer_count: int, source_row: dict[str, Any], a450_row: dict[str, Any], a451_row: dict[str, Any]) -> dict[str, Any]:
    """Reconcile a hash-bound global witness with actual local protection.

    The current decode epoch visits layers in numeric order.  Once the first
    local observation crosses the watermark, lower-numbered layers have
    already completed that epoch and cannot be retrospectively re-routed.  A
    request-global all-layer action is consequently specified only for the
    next decode epoch; this is a declared logical controller contract, not a
    timing model or an implementation claim.
    """
    pending = activation_pending_by_layer(source_row, layer_count=layer_count, label=f"{anchor}/{workload}")
    expected = {layer for layer, value in pending.items() if value >= HIGH_WATERMARK}
    if not expected:
        raise ValueError(f"{anchor}/{workload}: A4.5.0 C={HIGH_WATERMARK} witness has no local crossing")
    global_transition = a450_row["transition"]
    if int(global_transition["trigger_pending_max_across_layers"]) != max(pending.values()):
        raise ValueError(f"{anchor}/{workload}: A4.5.0 global maximum differs from A4.4 activation snapshot")
    if int(global_transition["trigger_layer_count_at_or_above_high_watermark"]) != len(expected):
        raise ValueError(f"{anchor}/{workload}: A4.5.0 crossing layer count differs from A4.4 activation snapshot")

    contract = a451_row.get("protection_contract", {})
    if contract.get("forced_token_inputs_equal_full_kv") is not True or contract.get("execution_scope") != "layer-local attention-hook primitive; not a request-global controller":
        raise ValueError(f"{anchor}/{workload}: A4.5.1 does not retain the bounded layer-local functional contract")
    actual_layers = contract.get("deferred_activation_summary", {}).get("layers", [])
    if {int(row.get("layer", -1)) for row in actual_layers} != set(range(layer_count)):
        raise ValueError(f"{anchor}/{workload}: A4.5.1 summary lacks contiguous layer coverage")
    actual: set[int] = set()
    for row in actual_layers:
        layer = int(row["layer"])
        event = row.get("capacity_protection_event")
        if event is None:
            if row.get("mode_at_trace_end") != "route_a_active" or layer in expected:
                raise ValueError(f"{anchor}/{workload}: unexpected unprotected A4.5.1 layer")
            continue
        actual.add(layer)
        if layer not in expected or not row.get("capacity_protection_committed") or row.get("mode_at_trace_end") != "protected_full_kv":
            raise ValueError(f"{anchor}/{workload}: invalid A4.5.1 protected layer")
        if event.get("boundary") != "activation_commit_before_current_route_a_logical_append":
            raise ValueError(f"{anchor}/{workload}: A4.5.1 transition is not activation-boundary local protection")
        if int(event.get("aggregate_pending_tokens_at_transition", -1)) != pending[layer] or int(event.get("pending_high_watermark", -1)) != HIGH_WATERMARK:
            raise ValueError(f"{anchor}/{workload}: A4.5.1 pending trigger differs from A4.4 snapshot")
        if int(row.get("protected_native_attention_calls", 0)) <= 0 or row.get("route_a_logical_state_next_position_at_end") != event.get("route_a_state_next_position_frozen"):
            raise ValueError(f"{anchor}/{workload}: A4.5.1 native fallback/frozen-state guard failed")
    if actual != expected:
        raise ValueError(f"{anchor}/{workload}: actual A4.5.1 protected set differs from C={HIGH_WATERMARK} source set")

    first = min(expected)
    return {
        "anchor": anchor,
        "workload": workload,
        "layer_count": layer_count,
        "pending_high_watermark": HIGH_WATERMARK,
        "activation_pending_by_layer": {str(layer): pending[layer] for layer in range(layer_count)},
        "a450_request_global_counterfactual": {
            "transition_boundary": global_transition["boundary"],
            "trigger_pending_max_across_layers": int(global_transition["trigger_pending_max_across_layers"]),
            "layers_at_or_above_high_watermark": len(expected),
        },
        "a451_actual_layer_local_primitive": {
            "protected_layer_indices": sorted(actual),
            "protected_layer_count": len(actual),
            "source_threshold_set_matches_actual": True,
            "transition_boundary": "activation_commit_before_current_route_a_logical_append",
            "native_fallback_and_frozen_state_guarded": True,
        },
        "reconciled_request_global_controller_contract": {
            "observation_order": "increasing_selected_layer_index within the activation decode epoch",
            "first_trigger_observation_layer": first,
            "layers_completed_before_trigger_observation": first,
            "current_epoch_retroactive_reroute_permitted": False,
            "request_global_latch_boundary": "after first layer-complete activation observation at or above high watermark",
            "all_layer_global_protection_effective_boundary": "next_decode_epoch_after_completion_of_current_activation_epoch",
            "all_selected_layers_covered_at_effective_boundary": layer_count,
            "reentry_permitted": False,
            "execution_status": "declared reconciliation contract only; not model-on global-controller execution",
        },
    }


def anchor_rows(*, anchor: str, a44_path: Path, a44_schema: str, a450: dict[str, Any], a451_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    a44 = validate_anchor(path=a44_path, expected_schema=a44_schema, anchor=anchor)
    a44_raw = read_completed(a44_path, schema=a44_schema, label=f"{anchor} A4.4 report")
    a451 = read_completed(a451_path, schema=A451_SCHEMA, label=f"{anchor} A4.5.1 report")
    if a451.get("config", {}).get("anchor") != anchor or int(a451.get("config", {}).get("pending_high_watermark", -1)) != HIGH_WATERMARK:
        raise ValueError(f"{anchor}: A4.5.1 anchor or high-watermark contract differs")
    if a451.get("provenance", {}).get("anchor_report_sha256") != a44["report_sha256"] or a451.get("provenance", {}).get("a450_report_sha256") != sha256_file_pathless(a450):
        raise ValueError(f"{anchor}: A4.5.1 provenance does not bind supplied A4.4/A4.5.0 reports")
    if not all(value is True for value in a451.get("observational_guards", {}).values()):
        raise ValueError(f"{anchor}: A4.5.1 observational guard is not true")
    rows = [
        reconcile_workload(
            anchor=anchor, workload=workload, layer_count=a44["layer_count"],
            source_row=a44_raw["per_workload"][workload],
            a450_row=a450_witness(a450, anchor=anchor, workload=workload, anchor_sha256=a44["report_sha256"]),
            a451_row=a451["per_workload"][workload],
        )
        for workload in WORKLOADS
    ]
    return a44, rows


def sha256_file_pathless(value: dict[str, Any]) -> str:
    """Use the exact parsed source bytes attached by ``main`` rather than a reserialization."""
    digest = value.get("_a452_source_sha256")
    if not isinstance(digest, str):
        raise AssertionError("A4.5.0 source digest was not attached before validation")
    return digest


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    a450 = read_completed(args.a450_report, schema=A450_SCHEMA, label="A4.5.0 report")
    a450["_a452_source_sha256"] = sha256_file(args.a450_report)
    qwen, qwen_rows = anchor_rows(anchor="qwen3_8b", a44_path=args.qwen_a44_report, a44_schema=QWEN_SCHEMA, a450=a450, a451_path=args.qwen_a451_report)
    llama, llama_rows = anchor_rows(anchor="llama31_8b_instruct", a44_path=args.llama_a44_report, a44_schema=LLAMA_SCHEMA, a450=a450, a451_path=args.llama_a451_report)
    rows = qwen_rows + llama_rows
    if len(rows) != 2 * len(WORKLOADS) or any(row["a451_actual_layer_local_primitive"]["source_threshold_set_matches_actual"] is not True for row in rows):
        raise AssertionError("A4.5.2 reconciliation rows are incomplete")
    config = {
        "qwen_a44_report": str(args.qwen_a44_report), "llama_a44_report": str(args.llama_a44_report),
        "a450_report": str(args.a450_report), "qwen_a451_report": str(args.qwen_a451_report),
        "llama_a451_report": str(args.llama_a451_report), "pending_high_watermark": HIGH_WATERMARK,
        "controller_scope": "request-global latch for next decode epoch, reconciled with current-epoch layer-local primitive; no global controller implementation",
    }
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "execution_classification": "no-model trace-derived controller-semantic reconciliation over hash-checked A4.4/A4.5.0/A4.5.1 artifacts; not measured or modeled hardware evidence",
        "input_artifacts": {
            "qwen3_8b_a44": {key: qwen[key] for key in ("report_path", "report_sha256", "report_schema", "layer_count")},
            "llama31_8b_instruct_a44": {key: llama[key] for key in ("report_path", "report_sha256", "report_schema", "layer_count")},
            "a450": {"report_path": str(args.a450_report), "report_sha256": sha256_file(args.a450_report), "report_schema": A450_SCHEMA},
            "qwen3_8b_a451": {"report_path": str(args.qwen_a451_report), "report_sha256": sha256_file(args.qwen_a451_report), "report_schema": A451_SCHEMA},
            "llama31_8b_instruct_a451": {"report_path": str(args.llama_a451_report), "report_sha256": sha256_file(args.llama_a451_report), "report_schema": A451_SCHEMA},
        },
        "anchor_workload_rows": rows,
        "observational_guards": {
            "all_six_rows_hash_bound_to_a44_a450_a451": True,
            "a450_request_global_counterfactual_is_not_relabelled_as_actual_current_epoch_global_execution": True,
            "actual_a451_local_protection_sets_equal_a44_c1024_sets_each_row": True,
            "local_native_fallback_and_frozen_state_guards_retained_each_row": True,
            "next_epoch_global_effect_boundary_explicit_each_row": True,
            "no_cross_anchor_numeric_pooling_or_hardware_parameter_derivation": True,
            "no_model_loaded": True,
            "no_hardware_parameter_selected": True,
        },
        "boundaries": [
            "A4.5.2 derives a logical controller observation/effect contract only. It does not implement, schedule, or time a request-global controller, barrier, broadcast, or native-attention switch.",
            "The next-decode-epoch effective boundary is a semantic non-retroactivity rule inferred from ordered layer execution, not a measured controller latency, cycle count, queue delay, or throughput result.",
            "C=1024 remains a hash-bound logical probe, not a FIFO depth/capacity, overflow threshold, service rate, page/bank/burst selection, or hardware parameter.",
            "Rows remain anchor/workload-specific. The report contains no pooled numeric envelope and no allocator, physical capacity, HBM/DMA traffic, burst, timing, latency, throughput, energy, area, architecture specification, or RTL evidence.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a452_global_protection_controller_reconciliation_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.5.2 global-protection controller reconciliation completed: {output}")


if __name__ == "__main__":
    main()
