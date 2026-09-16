#!/usr/bin/env python3
"""A4.3.2 no-model aggregation of untimed Route-A lifecycle transitions."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a432-policy-lifecycle-transition-envelope-1.0"
POLICY_SCHEMA = "kvzap-route-a40-policy-on-qwen-gate-1.6"
TRACE_SCHEMA = "kvzap-route-a432-logical-lifecycle-transitions-1.0"
PRESETS = {"retrieval", "summarization", "reasoning"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[int], quantile: float) -> int:
    if not values:
        raise ValueError("cannot summarize an empty transition vector")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * quantile + 0.999999999))]


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"policy manifest is absent: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    config, guards, trace = data.get("config"), data.get("observational_guards"), data.get("lifecycle_transition_trace")
    if data.get("schema_version") != POLICY_SCHEMA or not isinstance(config, dict) or not isinstance(guards, dict) or not isinstance(trace, dict):
        raise ValueError(f"manifest lacks A4.3.2 schema/config/trace: {path}")
    expected = {
        "target_layers": ["all"], "target_kv_head": "all", "admission_budget": 1,
        "with_same_mask_dense_baseline": True, "replay_dense_mask_for_route_a": True,
        "require_pending_nonempty": True, "require_single_visible_cuda_device": True,
        "record_lifecycle_transitions": True, "max_executed_dtype_ulps": 16.0,
        "execution_dtype_ulp_mode": "record_only", "execution_dtype_close_mode": "quantization_aware_enforce",
        "ulp_breach_sample_limit": 32,
    }
    if config.get("preset") not in PRESETS or any(config.get(key) != value for key, value in expected.items()):
        raise ValueError(f"manifest lacks A4.3.2 bounded functional contract: {path}")
    if data.get("cuda_environment", {}).get("visible_cuda_device_count") != 1:
        raise ValueError(f"manifest lacks single-visible-device provenance: {path}")
    required_guards = {
        "replay_mask_consumption_complete": True, "execution_dtype_close_enforced": True,
        "lifecycle_transition_trace_enabled": True, "trace_off_route_a_answer_equals_trace_on": True,
        "fake_key_attention_used": False, "model_cache_mutated_by_backend": False,
    }
    if any(guards.get(key) != value for key, value in required_guards.items()):
        raise ValueError(f"manifest lacks A4.3.2 semantic guards: {path}")
    if trace.get("schema_version") != TRACE_SCHEMA or not isinstance(trace.get("path"), str) or trace.get("sha256") is None:
        raise ValueError(f"manifest lifecycle trace descriptor is invalid: {path}")
    return data


def load_events(manifest_path: Path, trace: dict[str, Any]) -> list[dict[str, Any]]:
    path = manifest_path.parent / str(trace["path"])
    if sha256(path) != trace["sha256"]:
        raise ValueError(f"lifecycle trace hash mismatch: {path}")
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle if line.strip()]
    if not events:
        raise ValueError(f"lifecycle trace is empty: {path}")
    last_end: dict[int, int] = {}
    for expected, event in enumerate(events):
        if event.get("logical_transition_sequence") != expected or event.get("timestamps_recorded") is not False:
            raise ValueError("lifecycle trace ordering/timestamp contract failed")
        layer, start, end, count, heads = event.get("layer"), event.get("start_position"), event.get("end_position"), event.get("input_token_count"), event.get("heads")
        if not all(isinstance(value, int) and value >= 0 for value in (layer, start, end, count)) or end != start + count - 1 or count <= 0 or not isinstance(heads, list) or not heads:
            raise ValueError("lifecycle trace dimensions are invalid")
        if layer in last_end and start != last_end[layer] + 1:
            raise ValueError("lifecycle trace positions are non-contiguous within a layer")
        last_end[layer] = end
        for head, row in enumerate(heads):
            required = ("pending_tokens_before_maturity", "matured_kept_tokens", "pending_tokens_after_maturity", "admitted_tokens", "pending_tokens_after_service", "packed_tokens_before", "packed_tokens_after_service")
            if row.get("kv_head") != head or any(not isinstance(row.get(key), int) or row[key] < 0 for key in required):
                raise ValueError("lifecycle trace head state is invalid")
            if row["pending_tokens_after_maturity"] != row["pending_tokens_before_maturity"] + row["matured_kept_tokens"] or row["pending_tokens_after_service"] != row["pending_tokens_after_maturity"] - row["admitted_tokens"] or row["packed_tokens_after_service"] != row["packed_tokens_before"] + row["admitted_tokens"]:
                raise ValueError("lifecycle trace conservation failed")
    return events


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    heads = [row for event in events for row in event["heads"]]
    post_maturity = [row["pending_tokens_after_maturity"] for row in heads]
    post_service = [row["pending_tokens_after_service"] for row in heads]
    return {
        "logical_transition_event_count": len(events),
        "head_transition_row_count": len(heads),
        "phase_event_count": {phase: sum(event["phase"] == phase for event in events) for phase in ("prefill", "multi_token", "decode")},
        "matured_kept_tokens_total": sum(row["matured_kept_tokens"] for row in heads),
        "admitted_tokens_total": sum(row["admitted_tokens"] for row in heads),
        "pending_after_maturity_p50": percentile(post_maturity, 0.50),
        "pending_after_maturity_p95": percentile(post_maturity, 0.95),
        "pending_after_maturity_max": max(post_maturity),
        "pending_after_service_p50": percentile(post_service, 0.50),
        "pending_after_service_p95": percentile(post_service, 0.95),
        "pending_after_service_max": max(post_service),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.3.2 no-model policy-on lifecycle-transition envelope; no FIFO/timing/hardware claim.")
    parser.add_argument("--policy-manifest", action="append", type=Path, required=True, help="Three distinct A4.3.2 policy-on manifests: retrieval, summarization, reasoning.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_dir.exists() or len(args.policy_manifest) != 3:
        raise ValueError("A4.3.2 requires exactly three manifests and a new output directory")
    loaded = [(path, load_manifest(path)) for path in args.policy_manifest]
    by_preset = {data["config"]["preset"]: (path, data) for path, data in loaded}
    if set(by_preset) != PRESETS or len(by_preset) != 3:
        raise ValueError("A4.3.2 requires one distinct manifest per preset")
    reference = loaded[0][1]["config"]
    common = ("model_name", "model_revision", "predictor_name", "predictor_revision", "threshold", "window_size", "page_tokens", "admission_budget", "max_new_tokens", "seed", "target_layers", "target_kv_head", "require_single_visible_cuda_device", "record_lifecycle_transitions", "max_executed_dtype_ulps", "execution_dtype_ulp_mode", "execution_dtype_close_mode", "ulp_breach_sample_limit")
    if any(any(data["config"].get(key) != reference.get(key) for key in common) for _, data in loaded[1:]):
        raise ValueError("A4.3.2 manifests have inconsistent reference inputs")
    cuda = loaded[0][1]["cuda_environment"]
    if any(data["cuda_environment"] != cuda for _, data in loaded[1:]):
        raise ValueError("A4.3.2 manifests have inconsistent single-device environments")
    rows = []
    for preset in sorted(PRESETS):
        path, data = by_preset[preset]
        events = load_events(path, data["lifecycle_transition_trace"])
        rows.append({"preset": preset, "manifest_path": str(path), "manifest_sha256": sha256(path), "lifecycle_trace": data["lifecycle_transition_trace"], "transition_summary": summarize(events)})
    maxima = [row["transition_summary"]["pending_after_service_max"] for row in rows]
    config = {"policy_manifests": [{"path": str(path), "sha256": sha256(path)} for path in args.policy_manifest]}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model aggregation of policy-on functional/trace-derived logical lifecycle transitions; not FIFO occupancy, service timing, or hardware evidence", "shared_functional_reference_inputs": {key: reference[key] for key in common}, "shared_cuda_environment": cuda, "per_workload_transition_rows": rows, "bounded_transition_envelope": {"workload_count": 3, "pending_after_service_max_min": min(maxima), "pending_after_service_max_max": max(maxima), "interpretation": "Post-service pending state under the declared budget-one Route-A reference append action; not a finite FIFO depth, arrival/completion queue observation, or hardware service rate."}, "architecture_spec_gate": {"eligible": False, "rtl_authorized": False, "reason": "Logical lifecycle transitions close no target-specific FIFO/service contract and select no resource parameter."}, "observational_guards": {"three_distinct_workloads_preserved": True, "trace_off_answer_equals_trace_on_verified": True, "all_layer_all_kv_head_trace_verified": True, "no_fifo_depth_selected": True, "no_hardware_performance_claim": True}, "boundaries": ["Transitions occur at Python-reference append calls; no admission arrival, source completion, queue sampling time, or physical service interval is observed.", "Budget one is a declared functional reference action, not a FIFO drain rate or controller implementation.", "No allocator/HBM traffic, latency, throughput, energy, area, hardware parameter, architecture specification, or RTL conclusion follows."]}
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a432_policy_lifecycle_transition_envelope_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.3.2 completed: {path}")


if __name__ == "__main__":
    main()
