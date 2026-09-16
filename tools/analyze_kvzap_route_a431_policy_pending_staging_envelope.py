#!/usr/bin/env python3
"""A4.3.1 bounded policy-on pending-staging snapshot envelope.

Consumes accepted Route-A policy-on manifests only.  The comparison snapshots
are functional/trace-derived state observations; they are not FIFO occupancy,
service-time, allocator, or hardware measurements.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a431-policy-pending-staging-envelope-1.0"
POLICY_SCHEMA = "kvzap-route-a40-policy-on-qwen-gate-1.4"
REQUIRED_PRESETS = {"retrieval", "summarization", "reasoning"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[int], quantile: float) -> int:
    if not values:
        raise ValueError("cannot summarize an empty pending-state vector")
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * quantile + 0.999999999))
    return ordered[index]


def load_policy_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"policy manifest is absent: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != POLICY_SCHEMA:
        raise ValueError(f"unexpected policy manifest schema: {path}")
    config = data.get("config")
    guards = data.get("observational_guards")
    if not isinstance(config, dict) or not isinstance(guards, dict):
        raise ValueError(f"policy manifest is missing config/guards: {path}")
    if config.get("preset") not in REQUIRED_PRESETS:
        raise ValueError(f"policy manifest has no bounded A4.3.1 preset: {path}")
    if config.get("target_layers") != ["all"] or config.get("target_kv_head") != "all":
        raise ValueError(f"policy manifest is not all-layer/all-KV-head: {path}")
    if config.get("require_single_visible_cuda_device") is not True:
        raise ValueError(f"policy manifest lacks the single-visible-CUDA-device gate: {path}")
    cuda_environment = data.get("cuda_environment")
    if not isinstance(cuda_environment, dict) or cuda_environment.get("visible_cuda_device_count") != 1:
        raise ValueError(f"policy manifest does not prove single-visible-device execution: {path}")
    if config.get("admission_budget") != 1 or config.get("require_pending_nonempty") is not True:
        raise ValueError(f"policy manifest is not the bounded pending-staging probe: {path}")
    if config.get("with_same_mask_dense_baseline") is not True or config.get("replay_dense_mask_for_route_a") is not True:
        raise ValueError(f"policy manifest lacks paired same-mask replay: {path}")
    required_guards = ("selected_head_original_attention_called_during_policy_decode", "replay_mask_consumption_complete", "fake_key_attention_used", "model_cache_mutated_by_backend")
    expected = (False, True, False, False)
    if tuple(guards.get(name) for name in required_guards) != expected:
        raise ValueError(f"policy manifest lacks required Route-A semantic guards: {path}")
    comparisons = data.get("comparisons")
    if not isinstance(comparisons, list) or not comparisons:
        raise ValueError(f"policy manifest has no comparison snapshots: {path}")
    return data


def summarize_comparisons(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    if any(not isinstance(row.get("pending_tokens"), int) or row["pending_tokens"] < 0 for row in comparisons):
        raise ValueError("comparison pending-token snapshot is invalid")
    values = [int(row["pending_tokens"]) for row in comparisons]
    per_layer: dict[int, list[int]] = {}
    per_layer_head: dict[tuple[int, int], list[int]] = {}
    for row, value in zip(comparisons, values):
        layer, head = int(row["layer"]), int(row["kv_head"])
        per_layer.setdefault(layer, []).append(value)
        per_layer_head.setdefault((layer, head), []).append(value)
    active = [value for value in values if value > 0]
    return {
        "comparison_snapshot_count": len(values),
        "pending_nonempty_snapshot_count": len(active),
        "pending_nonempty_snapshot_fraction": len(active) / len(values),
        "pending_tokens_snapshot_p50": percentile(values, 0.50),
        "pending_tokens_snapshot_p95": percentile(values, 0.95),
        "pending_tokens_snapshot_max": max(values),
        "per_layer_snapshot_max": {str(layer): max(layer_values) for layer, layer_values in sorted(per_layer.items())},
        "per_layer_kv_head_snapshot_max": [
            {"layer": layer, "kv_head": head, "pending_tokens_snapshot_max": max(head_values)}
            for (layer, head), head_values in sorted(per_layer_head.items())
        ],
        "overflow_observation": "not_observable: no finite FIFO capacity or service/completion timing is instantiated by this functional reference",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.3.1 no-model bounded policy-on pending-staging snapshot envelope; no FIFO sizing or hardware claim."
    )
    parser.add_argument("--policy-manifest", type=Path, action="append", required=True, help="Accepted all-layer/all-head paired policy-on manifest; provide retrieval, summarization, and reasoning once each.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if len(args.policy_manifest) != 3:
        raise ValueError("A4.3.1 requires exactly three policy manifests")
    manifests = [load_policy_manifest(path) for path in args.policy_manifest]
    by_preset = {str(data["config"]["preset"]): (path, data) for path, data in zip(args.policy_manifest, manifests)}
    if set(by_preset) != REQUIRED_PRESETS or len(by_preset) != 3:
        raise ValueError("A4.3.1 requires one distinct retrieval, summarization, and reasoning manifest")
    common_keys = ("model_name", "model_revision", "predictor_name", "predictor_revision", "threshold", "window_size", "page_tokens", "admission_budget", "max_new_tokens", "seed", "target_layers", "target_kv_head", "with_same_mask_dense_baseline", "replay_dense_mask_for_route_a", "require_single_visible_cuda_device")
    reference = manifests[0]["config"]
    if any(any(data["config"].get(key) != reference.get(key) for key in common_keys) for data in manifests[1:]):
        raise ValueError("A4.3.1 policy manifests have inconsistent bounded reference inputs")
    reference_cuda_environment = manifests[0]["cuda_environment"]
    if any(data["cuda_environment"] != reference_cuda_environment for data in manifests[1:]):
        raise ValueError("A4.3.1 policy manifests have inconsistent single-device CUDA environments")
    workload_rows = []
    for preset in sorted(REQUIRED_PRESETS):
        path, data = by_preset[preset]
        workload_rows.append({
            "preset": preset,
            "request_id": data["request_id"],
            "request_content_hash": data["request_content_hash"],
            "manifest_path": str(path),
            "manifest_sha256": sha256(path),
            "pending_snapshot_summary": summarize_comparisons(data["comparisons"]),
        })
    maxima = [row["pending_snapshot_summary"]["pending_tokens_snapshot_max"] for row in workload_rows]
    config = {"policy_manifests": [{"path": str(path), "sha256": sha256(path)} for path in args.policy_manifest]}
    report = {
        "schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config),
        "execution_classification": "no-model aggregation of completed policy-on functional/trace-derived pending-state snapshots; not a FIFO occupancy, hardware, or performance result",
        "shared_functional_reference_inputs": {key: reference[key] for key in common_keys},
        "shared_cuda_environment": reference_cuda_environment,
        "per_workload_pending_snapshot_rows": workload_rows,
        "bounded_snapshot_envelope": {
            "workload_count": 3,
            "pending_tokens_snapshot_max_min": min(maxima),
            "pending_tokens_snapshot_max_max": max(maxima),
            "interpretation": "Observed maximum pending tokens at Route-A attention-comparison snapshots over three bounded policy-on requests; not a finite FIFO depth or workload-distribution bound.",
        },
        "overflow_boundary": "No physical FIFO capacity, source service/completion order, or overflow policy is instantiated; neither absence nor presence of hardware overflow is observed.",
        "architecture_spec_gate": {"eligible": False, "rtl_authorized": False, "reason": "Pending-state snapshots narrow only a functional evidence gap; finite FIFO sizing still needs an explicit target/service contract."},
        "observational_guards": {"three_distinct_workloads_preserved": True, "all_layer_all_kv_head_policy_on_verified": True, "paired_same_mask_replay_verified": True, "pending_nonempty_each_workload_verified": True, "no_fifo_depth_selected": True, "no_hardware_performance_claim": True},
        "boundaries": [
            "Pending-token values are Route-A Python-reference comparison snapshots, not queue occupancy sampled at admission arrival or completion.",
            "No finite FIFO capacity, overflow policy, service rate, source completion order, or controller timing is measured or inferred.",
            "No Python runtime, allocator, profiler, byte/cycle proxy, HBM traffic, latency, throughput, energy, area, acceleration, architecture specification, or RTL conclusion follows.",
        ],
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "a431_policy_pending_staging_envelope_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.3.1 completed: {output}")


if __name__ == "__main__":
    main()
