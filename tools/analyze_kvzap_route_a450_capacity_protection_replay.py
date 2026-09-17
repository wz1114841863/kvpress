#!/usr/bin/env python3
"""A4.5.0 no-model logical Capacity Protection Contract replay.

This consumes the completed A4.4 activation snapshots and post-commit logical
traces.  At declared *logical* pending high-watermarks it moves a request once
from ROUTE_A_ACTIVE to PROTECTED_FULL_KV, freezes subsequent Route-A logical
mutation, and relies on the A4.4-retained native Full-KV state.  It is a
boundary replay, not a FIFO/capacity/timing/traffic model.
"""
from __future__ import annotations

import argparse
import gzip
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


SCHEMA = "kvzap-route-a450-capacity-protection-boundary-replay-1.0"
DEFAULT_HIGH_WATERMARKS = (256, 512, 1024, 2048, 4096, 8192)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.5.0 no-model logical capacity-protection boundary replay; no FIFO sizing, timing, or hardware result."
    )
    parser.add_argument("--qwen-report", type=Path, required=True)
    parser.add_argument("--llama-report", type=Path, required=True)
    parser.add_argument("--pending-high-watermarks", type=int, nargs="+", default=list(DEFAULT_HIGH_WATERMARKS), help="Declared logical per-layer pending boundary sensitivity points; not FIFO depths.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def pending_by_layer_from_activation(active_layers: list[dict[str, Any]]) -> dict[int, int]:
    return {
        int(layer["layer"]): sum(int(head["pending_tokens_after_commit"]) for head in layer["activation_event"]["heads"])
        for layer in active_layers
    }


def events_by_position(*, report_path: Path, trace: dict[str, Any], layer_count: int) -> list[tuple[int, list[dict[str, Any]]]]:
    path = report_path.parents[1] / str(trace["path"])
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle]
    groups: dict[int, list[dict[str, Any]]] = {}
    for event in events:
        groups.setdefault(int(event["start_position"]), []).append(event)
    ordered = sorted(groups.items())
    if not ordered or any({int(event["layer"]) for event in group} != set(range(layer_count)) for _position, group in ordered):
        raise ValueError("post-commit trace cannot be grouped into layer-complete logical append boundaries")
    return ordered


def layer_pending_before(group: list[dict[str, Any]]) -> dict[int, int]:
    return {int(event["layer"]): sum(int(head["pending_tokens_before_maturity"]) for head in event["heads"]) for event in group}


def layer_pending_after(group: list[dict[str, Any]]) -> dict[int, int]:
    return {int(event["layer"]): sum(int(head["pending_tokens_after_service"]) for head in event["heads"]) for event in group}


def replay_request(*, anchor: str, workload: str, report_path: Path, source_row: dict[str, Any], layer_count: int, high_watermark: int) -> dict[str, Any]:
    """Replay a request-global one-way protection policy at logical boundaries.

    The high-watermark is evaluated against the maximum selected-layer pending
    aggregate.  This is a deliberately conservative *control-plane* predicate;
    it neither asserts a physical FIFO organization nor proves that an actual
    controller can prevent within-append transient occupancy.
    """
    active = source_row["activation_contract"]
    activation_layers = active["deferred_activation_summary"]["layers"]
    pending = pending_by_layer_from_activation(activation_layers)
    if set(pending) != set(range(layer_count)):
        raise ValueError(f"{anchor}/{workload}: activation pending snapshot lacks layer coverage")
    trace = source_row["post_commit_logical_trace"]
    epochs = events_by_position(report_path=report_path, trace=trace, layer_count=layer_count)
    max_activation_pending = max(pending.values())
    initial = {
        "mode": "route_a_active",
        "native_full_kv_retained": True,
        "route_a_logical_state_exists": True,
        "pending_max_across_layers_after_activation_commit": max_activation_pending,
    }
    transition: dict[str, Any] | None = None
    consumed_epochs = 0
    boundary_records: list[dict[str, Any]] = []
    if max_activation_pending >= high_watermark:
        transition = {
            "from_mode": "route_a_active",
            "to_mode": "protected_full_kv",
            "boundary": "activation_commit_before_current_decode_append",
            "logical_position": int(epochs[0][0]),
            "trigger_pending_max_across_layers": max_activation_pending,
            "trigger_layer_count_at_or_above_high_watermark": sum(value >= high_watermark for value in pending.values()),
        }
    else:
        for position, group in epochs:
            before = layer_pending_before(group)
            maximum = max(before.values())
            boundary_records.append({"logical_position": position, "pending_max_across_layers_before_append": maximum})
            if maximum >= high_watermark:
                transition = {
                    "from_mode": "route_a_active",
                    "to_mode": "protected_full_kv",
                    "boundary": "post_commit_before_next_route_a_logical_append",
                    "logical_position": position,
                    "trigger_pending_max_across_layers": maximum,
                    "trigger_layer_count_at_or_above_high_watermark": sum(value >= high_watermark for value in before.values()),
                }
                break
            consumed_epochs += 1
            pending = layer_pending_after(group)
    mode_at_end = "protected_full_kv" if transition is not None else "route_a_active"
    return {
        "anchor": anchor,
        "workload": workload,
        "policy": {
            "high_watermark_scope": "maximum_per_selected_layer_aggregate_pending_tokens",
            "pending_high_watermark": high_watermark,
            "comparison": "greater_than_or_equal",
            "protection_mode": "protected_full_kv",
            "reentry_permitted": False,
            "post_protection_route_a_logical_admission_or_drop": "disabled_by_counterfactual_policy",
            "fallback_authority": "retained_native_full_kv",
        },
        "initial_route_a_active_state": initial,
        "transition": transition,
        "mode_at_trace_end": mode_at_end,
        "route_a_logical_epochs_consumed_before_protection": consumed_epochs,
        "route_a_logical_epochs_bypassed_after_protection": len(epochs) - consumed_epochs if transition is not None else 0,
        "total_post_commit_epochs_available": len(epochs),
        "boundary_pending_records_before_protection": boundary_records,
        "contract_predicates": {
            "pre_protection_route_a_active": True,
            "transition_is_one_way_when_triggered": True,
            "native_full_kv_retained_for_protection": True,
            "no_post_protection_route_a_logical_admission_or_drop": True,
            "no_reentry_within_bounded_trace": True,
            "counterfactual_only_not_actual_runtime_mode_switch": True,
        },
    }


def source_rows(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))["per_workload"]


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    points = tuple(args.pending_high_watermarks)
    if not points or len(set(points)) != len(points) or any(point <= 0 for point in points):
        raise ValueError("pending high-watermarks must be unique positive integers")
    qwen = validate_anchor(path=args.qwen_report, expected_schema=QWEN_SCHEMA, anchor="qwen3_8b")
    llama = validate_anchor(path=args.llama_report, expected_schema=LLAMA_SCHEMA, anchor="llama31_8b_instruct")
    raw = {"qwen3_8b": source_rows(args.qwen_report), "llama31_8b_instruct": source_rows(args.llama_report)}
    anchors = (qwen, llama)
    rows = [
        replay_request(anchor=anchor["anchor"], workload=workload, report_path=Path(anchor["report_path"]), source_row=raw[anchor["anchor"]][workload], layer_count=anchor["layer_count"], high_watermark=point)
        for anchor in anchors for workload in WORKLOADS for point in points
    ]
    if len(rows) != len(anchors) * len(WORKLOADS) * len(points):
        raise AssertionError("capacity-protection replay row count is incomplete")
    config = {"qwen_report": str(args.qwen_report), "llama_report": str(args.llama_report), "pending_high_watermarks": list(points), "policy": "request-global one-way Route-A-active to protected-Full-KV transition at logical per-layer pending boundaries; no re-entry"}
    report = {
        "schema_version": SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model trace-derived logical-boundary counterfactual over hash-checked A4.4 inputs; not a measured or modeled hardware result",
        "input_artifacts": {anchor["anchor"]: {key: anchor[key] for key in ("report_path", "report_sha256", "report_schema", "layer_count")} for anchor in anchors},
        "replay_rows": rows,
        "observational_guards": {
            "both_a44_reports_and_post_commit_traces_validated_before_replay": True,
            "all_anchor_workload_high_watermark_rows_retained_separately": True,
            "protection_uses_retained_native_full_kv_not_route_a_state_deletion": True,
            "one_way_no_reentry_policy_explicit": True,
            "post_protection_route_a_logical_admission_or_drop_disabled_by_policy": True,
            "no_model_loaded": True,
            "no_hardware_parameter_selected": True,
        },
        "boundaries": [
            "High-watermarks are declared logical sensitivity points over maximum per-layer aggregate pending tokens. They are not observed FIFO depths, capacities, overflow thresholds, service rates, or resource selections.",
            "The replay observes scalar A4.4 state at logical boundaries only. It cannot prove a real controller prevents a within-append transient, switches a native attention implementation, or preserves full-model outputs after protection.",
            "PROTECTED_FULL_KV is a counterfactual control state relying on the native cache retained by A4.4. It performs no modeled deallocation, DMA/HBM transfer, physical traffic, timing, latency, throughput, energy, area, hardware acceleration, architecture specification, or RTL action.",
            "Qwen and Llama rows are separate. The report has no cross-model average, common envelope, or hardware parameter derivation. A later model-on protection semantic gate remains required before any resource model treats this policy as validated runtime behavior.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a450_capacity_protection_boundary_replay_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.5.0 capacity-protection boundary replay completed: {output}")


if __name__ == "__main__":
    main()
