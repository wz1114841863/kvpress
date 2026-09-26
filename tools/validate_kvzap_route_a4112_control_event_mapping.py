#!/usr/bin/env python3
"""Validate A4.11.2's trace-on Route-A lifecycle-to-model mapping.

This validator consumes scalar lifecycle records emitted before the Route-A
prefill append.  It preserves the distinction between software observations
and A4.10's declared hardware-model fields; it never invents queue, port,
micro-op, or commit events that the reference does not expose.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kvpress.route_a_attention import RouteALifecycleTransitionRecorder
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash
from tools.validate_kvzap_route_a4110_semantic_matrix import WORKLOADS, validate_a410
from tools.validate_kvzap_route_a4111_measurement_matrix import SCHEMA as A4111_SCHEMA, validate_a4110


SCHEMA = "kvzap-route-a4112-trace-on-control-event-mapping-1.0"
POLICY_TRACE_SCHEMA = "kvzap-route-a40-policy-on-qwen-gate-1.6"
STABLE_FIELDS = (
    "model_name", "model_revision", "predictor_name", "predictor_revision",
    "threshold", "window_size", "page_tokens", "admission_budget",
    "context_repetitions", "max_new_tokens", "seed", "rtol", "atol",
    "max_executed_dtype_ulps", "target_layers", "target_kv_head",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.11.2 trace-on Route-A lifecycle-to-A4.10 mapping validator; no timing or hardware-service claim."
    )
    parser.add_argument("--a410-report", type=Path, required=True)
    parser.add_argument("--a4110-report", type=Path, required=True)
    parser.add_argument("--a4111-report", type=Path, required=True)
    for workload in WORKLOADS:
        parser.add_argument(f"--{workload}-manifest", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true", help="Validate immutable trace-on inputs without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return payload


def read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"lifecycle transition file is missing: {path}")
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("lifecycle transition file must contain nonempty JSON objects")
    return rows


def require_digest(value: Any, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label} is not a SHA-256 digest")


def expected_heads(manifest: dict[str, Any]) -> dict[int, list[int]]:
    coverage = manifest.get("policy_coverage", {}).get("layers", [])
    result = {int(row["layer"]): list(row["selected_kv_heads"]) for row in coverage}
    if not result or any(not heads for heads in result.values()):
        raise ValueError("trace manifest lacks selected layer/KV-head coverage")
    return result


def validate_lifecycle_events(events: list[dict[str, Any]], *, selected_layers: list[int], selected_heads: dict[int, list[int]], window: int) -> dict[str, Any]:
    """Audit scalar lifecycle records and return only honest software summaries."""
    by_layer: dict[int, list[dict[str, Any]]] = defaultdict(list)
    pending_after_maturity_max = 0
    pending_after_service_max = 0
    matured_kept_total = 0
    matured_dropped_total = 0
    admitted_total = 0
    packed_tokens_max = 0
    prefill_pending_seen = False
    for sequence, event in enumerate(events):
        if event.get("logical_transition_sequence") != sequence or event.get("timestamps_recorded") is not False:
            raise ValueError("lifecycle transition ordering/timestamp contract is invalid")
        layer = event.get("layer")
        if not isinstance(layer, int) or layer not in selected_layers:
            raise ValueError("lifecycle transition contains an undeclared layer")
        phase = event.get("phase")
        start, end, count = event.get("start_position"), event.get("end_position"), event.get("input_token_count")
        if phase not in {"prefill", "multi_token", "decode"} or not isinstance(start, int) or not isinstance(end, int) or not isinstance(count, int) or count <= 0 or end != start + count - 1:
            raise ValueError("lifecycle transition dimensions are invalid")
        heads = event.get("heads")
        if not isinstance(heads, list) or [row.get("kv_head") for row in heads] != selected_heads[layer]:
            raise ValueError(f"layer {layer}: lifecycle KV-head coverage/order is invalid")
        for row in heads:
            keys = (
                "hot_tokens_before", "pending_tokens_before_maturity", "matured_kept_tokens",
                "matured_dropped_tokens", "pending_tokens_after_maturity", "admitted_tokens",
                "pending_tokens_after_service", "packed_tokens_before", "packed_tokens_after_service",
                "packed_page_count_after_service", "packed_full_page_count_after_service",
                "packed_tail_tokens_after_service",
            )
            if any(not isinstance(row.get(key), int) or row[key] < 0 for key in keys):
                raise ValueError("lifecycle transition scalar state is invalid")
            if row["pending_tokens_after_maturity"] != row["pending_tokens_before_maturity"] + row["matured_kept_tokens"]:
                raise ValueError("lifecycle maturity conservation failed")
            if row["pending_tokens_after_service"] != row["pending_tokens_after_maturity"] - row["admitted_tokens"]:
                raise ValueError("lifecycle admission conservation failed")
            if row["packed_tokens_after_service"] != row["packed_tokens_before"] + row["admitted_tokens"]:
                raise ValueError("lifecycle packed-state conservation failed")
            matured_kept_total += row["matured_kept_tokens"]
            matured_dropped_total += row["matured_dropped_tokens"]
            admitted_total += row["admitted_tokens"]
            pending_after_maturity_max = max(pending_after_maturity_max, row["pending_tokens_after_maturity"])
            pending_after_service_max = max(pending_after_service_max, row["pending_tokens_after_service"])
            packed_tokens_max = max(packed_tokens_max, row["packed_tokens_after_service"])
            prefill_pending_seen = prefill_pending_seen or (phase == "prefill" and row["pending_tokens_after_maturity"] > 0)
        by_layer[layer].append(event)
    if sorted(by_layer) != selected_layers:
        raise ValueError("lifecycle trace lacks an observed selected layer")
    for layer in selected_layers:
        rows = by_layer[layer]
        if rows[0]["phase"] != "prefill" or rows[0]["start_position"] != 0 or rows[0]["input_token_count"] <= window:
            raise ValueError(f"layer {layer}: trace was not armed before prefill/pending creation")
        previous_end = None
        for row in rows:
            if previous_end is not None and row["start_position"] != previous_end + 1:
                raise ValueError(f"layer {layer}: lifecycle positions are not contiguous")
            previous_end = row["end_position"]
    if not prefill_pending_seen or matured_kept_total <= 0:
        raise ValueError("trace did not observe prefill-created retained pending state")
    return {
        "transition_event_count": len(events),
        "observed_layers": selected_layers,
        "prefill_trace_armed_before_pending_creation": True,
        "software_maturity_arrival_tokens": matured_kept_total,
        "software_maturity_dropped_tokens": matured_dropped_total,
        "software_admission_service_tokens": admitted_total,
        "software_pending_after_maturity_max_per_head": pending_after_maturity_max,
        "software_pending_after_service_max_per_head": pending_after_service_max,
        "software_packed_tokens_max_per_head": packed_tokens_max,
    }


def validate_a4111(report: dict[str, Any]) -> None:
    if report.get("schema_version") != A4111_SCHEMA or report.get("status") != "complete":
        raise ValueError("A4.11.1 trace-off measurement matrix is incomplete or incompatible")
    guards = report.get("observational_guards", {})
    required = (
        "a4110_trace_off_semantics_verified_before_measurement",
        "full_kv_bypass_same_mask_dense_and_external_route_a_paths_measured",
        "same_mask_dense_and_external_route_a_generated_tokens_equal",
        "all_layers_all_kv_heads_external_storage_and_replay_consumption_verified",
    )
    if not all(guards.get(name) is True for name in required):
        raise ValueError("A4.11.1 measurement guards are incomplete")


def answer_relations(manifest: dict[str, Any], dense: dict[str, Any]) -> dict[str, bool]:
    """Record path-output relations without promoting the dense comparator to a hard gate."""
    return {
        "full_kv_route_a_answer_equal": manifest["full_kv_bypass_answer_sha256"] == manifest["route_a_fast_path_answer_sha256"],
        "same_mask_dense_route_a_answer_equal": dense["answer_sha256"] == manifest["route_a_fast_path_answer_sha256"],
    }


def validate_trace_manifest(manifest: dict[str, Any], workload: str, manifest_path: Path, semantic_config: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != POLICY_TRACE_SCHEMA:
        raise ValueError(f"{workload}: expected trace schema {POLICY_TRACE_SCHEMA}")
    config = manifest.get("config", {})
    if config.get("preset") != workload or config.get("input_jsonl") is not None:
        raise ValueError(f"{workload}: trace must use the named built-in preset")
    if any(config.get(name) != semantic_config.get(name) for name in STABLE_FIELDS):
        raise ValueError(f"{workload}: trace semantic configuration differs from A4.11.0")
    if config.get("record_lifecycle_transitions") is not True or config.get("prefill_maturity_chunk_tokens", 0) != 0:
        raise ValueError(f"{workload}: A4.11.2 requires prefill-armed lifecycle tracing at actual model-call append granularity")
    if config.get("execution_dtype_ulp_mode") != "record_only" or config.get("execution_dtype_close_mode") != "quantization_aware_enforce":
        raise ValueError(f"{workload}: trace executed-dtype contract differs from A4.11.0")
    guards = manifest.get("observational_guards", {})
    expected_guards = {
        "route_a_mask_source": "replayed_dense_mask",
        "replay_mask_consumption_complete": True,
        "lifecycle_transition_trace_enabled": True,
        "prefill_micro_event_trace_enabled": False,
        "trace_off_route_a_answer_equals_trace_on": True,
        "selected_head_original_attention_called_during_policy_decode": False,
        "dms_press_used": False,
        "masked_key_indices_created": False,
        "fake_key_attention_used": False,
        "model_cache_mutated_by_backend": False,
    }
    if any(guards.get(name) != value for name, value in expected_guards.items()):
        raise ValueError(f"{workload}: trace-on Route-A semantic guards are incomplete")
    dense = manifest.get("same_mask_dense_kvzap")
    if not isinstance(dense, dict) or dense.get("pairing_mode") != "replayed_dense_mask" or dense.get("original_mask_digest_matches_route_a") is not True:
        raise ValueError(f"{workload}: same-mask dense comparator is absent or unpaired")
    require_digest(manifest.get("full_kv_bypass_answer_sha256"), f"{workload}: Full-KV answer")
    require_digest(manifest.get("route_a_fast_path_answer_sha256"), f"{workload}: Route-A answer")
    require_digest(dense.get("answer_sha256"), f"{workload}: dense answer")
    control_plane = manifest.get("control_plane", {})
    if not isinstance(control_plane.get("full_kv_bypass"), str) or "no Route-A backend" not in control_plane["full_kv_bypass"]:
        raise ValueError(f"{workload}: Full-KV bypass boundary is not explicit")
    if not isinstance(control_plane.get("same_mask_dense_kvzap"), str) or "no pending FIFO" not in control_plane["same_mask_dense_kvzap"]:
        raise ValueError(f"{workload}: same-mask dense is not a lightweight non-queue comparator")
    trace = manifest.get("lifecycle_transition_trace", {})
    if trace.get("schema_version") != RouteALifecycleTransitionRecorder.SCHEMA or trace.get("prefill_maturity_chunk_tokens") != 0:
        raise ValueError(f"{workload}: lifecycle trace metadata is incompatible")
    relative = trace.get("path")
    if not isinstance(relative, str) or Path(relative).is_absolute() or Path(relative).name != relative:
        raise ValueError(f"{workload}: lifecycle trace path is invalid")
    trace_path = manifest_path.parent / relative
    if sha256_file(trace_path) != trace.get("sha256"):
        raise ValueError(f"{workload}: lifecycle trace hash differs from manifest")
    selected = expected_heads(manifest)
    layers = sorted(selected)
    summary = validate_lifecycle_events(read_jsonl_gz(trace_path), selected_layers=layers, selected_heads=selected, window=int(config["window_size"]))
    return {
        "request_id": manifest.get("request_id"),
        "request_content_hash": manifest.get("request_content_hash"),
        "trace_manifest": str(manifest_path),
        "trace_manifest_sha256": sha256_file(manifest_path),
        "lifecycle_trace": str(trace_path),
        "lifecycle_trace_sha256": trace["sha256"],
        **answer_relations(manifest, dense),
        "selected_layer_count": len(layers),
        "selected_kv_head_count": sum(map(len, selected.values())),
        "software_lifecycle_summary": summary,
    }


def validate_inputs(args: argparse.Namespace) -> dict[str, Any]:
    a410 = read_json(args.a410_report, "A4.10 report")
    a410_config = validate_a410(a410)
    a4110 = read_json(args.a4110_report, "A4.11.0 report")
    semantic_config = validate_a4110(a4110)
    a4111 = read_json(args.a4111_report, "A4.11.1 report")
    validate_a4111(a4111)
    rows = []
    for workload in WORKLOADS:
        path = getattr(args, f"{workload}_manifest")
        rows.append({"workload": workload, **validate_trace_manifest(read_json(path, f"{workload} trace manifest"), workload, path, semantic_config)})
    return {
        "a410_report": str(args.a410_report), "a410_report_sha256": sha256_file(args.a410_report), "a410_fixed_config": a410_config,
        "a4110_report": str(args.a4110_report), "a4110_report_sha256": sha256_file(args.a4110_report),
        "a4111_report": str(args.a4111_report), "a4111_report_sha256": sha256_file(args.a4111_report),
        "stable_policy_config": semantic_config, "workloads": rows,
    }


def mapping_contract() -> dict[str, dict[str, str]]:
    return {
        "modeled_arrival": {"mapping": "direct_software_scalar", "software_source": "matured_kept_tokens", "boundary": "retained-token maturity is an arrival input, not a hardware atomic-group timestamp"},
        "modeled_queue_staging_watermark": {"mapping": "direct_software_scalar", "software_source": "pending_tokens_after_maturity and pending_tokens_after_service", "boundary": "per-head Route-A pending state is not a bank FIFO or shared hardware staging occupancy"},
        "modeled_ready_group": {"mapping": "no_direct_software_correspondent", "boundary": "reference exposes no transaction-ready publication event"},
        "modeled_micro_op_done": {"mapping": "no_direct_software_correspondent", "boundary": "reference has no separately observable internal metadata micro-op completion"},
        "modeled_single_commit": {"mapping": "no_direct_software_correspondent", "boundary": "reference records before/after logical admission state, not ownership/FIFO publish"},
        "bank_read_port": {"mapping": "no_direct_software_correspondent", "boundary": "no bank-port model is executed by the software reference"},
        "bank_write_port": {"mapping": "no_direct_software_correspondent", "boundary": "no bank-port model is executed by the software reference"},
        "rmw_lane": {"mapping": "no_direct_software_correspondent", "boundary": "no RMW-lane model is executed by the software reference"},
        "cross_bank_commit_coordination": {"mapping": "no_direct_software_correspondent", "boundary": "no cross-bank coordination is executed by the software reference"},
    }


def main() -> None:
    args = parse_args()
    checked = validate_inputs(args)
    if args.preflight_only:
        print("A4.11.2 preflight passed: prefill-armed Route-A traces and honest A4.10 mapping inputs validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    config = {"stage": "A4.11.2", "workloads": list(WORKLOADS), "execution": "trace-on Route-A lifecycle only; Full-KV bypass and same-mask dense remain lightweight control/comparator paths"}
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "input_artifacts": checked, "software_to_a410_mapping": mapping_contract(),
        "control_path_scope": {
            "full_kv_bypass": "bypass/control boundary only; no Route-A lifecycle trace",
            "same_mask_dense_replay": "same-mask semantic comparator only; no Route-A queue/pending trace",
            "route_a_trace_on_replay": "prefill-armed Route-A lifecycle source for maturity/admission/pending scalar observation",
        },
        "semantic_guards": {
            "a410_parameters_and_execution_variant_remain_hash_bound": True,
            "a4110_semantic_and_a4111_trace_off_prerequisites_passed": True,
            "route_a_trace_is_armed_before_prefill_pending_creation": True,
            "route_a_trace_preserves_replayed_mask_and_trace_off_answer": True,
            "full_kv_bypass_and_dense_paths_are_lightweight_boundary_comparators": True,
            "same_mask_dense_route_a_answer_relation_recorded_not_required": True,
            "unmapped_modeled_fields_are_explicit_not_synthesized": True,
            "no_timing_allocator_or_hardware_service_claim": True,
        },
        "boundaries": [
            "This trace begins before Route-A prefill append and records scalar reference lifecycle state; it is deliberately untimed and is not a performance measurement.",
            "Matured retained-token counts and per-head pending state are software observations that can feed a declared A4.10 input mapping. They are not atomic-group timestamps, hardware FIFO occupancy, or shared staging depth.",
            "Ready-group, micro-op done, ownership/FIFO publication, bank ports, RMW lanes, and cross-bank commit coordination have no direct software event here and remain explicitly unmapped declared-model fields.",
            "This does not calibrate A4.10 cycles, queue depths, credit latency, throughput, HBM traffic, energy, area, architecture, or RTL.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a4112_trace_on_control_event_mapping_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.11.2 complete: {path} sha256={sha256_file(path)} workloads={len(WORKLOADS)}")


if __name__ == "__main__":
    main()
