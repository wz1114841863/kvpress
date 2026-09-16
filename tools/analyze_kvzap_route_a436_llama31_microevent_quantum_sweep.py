#!/usr/bin/env python3
"""No-model comparison of the nine conditioned Llama A4.3.6 sources."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

PRESETS = {"retrieval", "summarization", "reasoning"}
QUANTA = {1, 8, 32}
SOURCE_SCHEMA = "kvzap-route-a436-llama31-microevent-gate-1.0"
SCHEMA = "kvzap-route-a436-llama31-microevent-quantum-sweep-1.0"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(events: list[dict[str, Any]]) -> dict[str, int]:
    rows = [row for event in events for row in event["heads"]]
    pending = sorted(int(row["pending_tokens_after_service"]) for row in rows)
    return {
        "logical_event_count": len(events),
        "prefill_event_count": sum(event["phase"] == "prefill" for event in events),
        "max_prefill_event_tokens": max(event["input_token_count"] for event in events if event["phase"] == "prefill"),
        "pending_p95": pending[min(len(pending) - 1, int((len(pending) - 1) * .95 + .999999))],
        "pending_max": max(pending),
        "admitted_tokens_total": sum(int(row["admitted_tokens"]) for row in rows),
        "packed_tokens_max": max(int(row["packed_tokens_after_service"]) for row in rows),
        "full_pages_max": max(int(row["packed_full_page_count_after_service"]) for row in rows),
    }


def load_source(path: Path, *, m0_sha256: str, m1_sha256: str, m51_sha256: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    config, provenance, guards, trace = data.get("config"), data.get("provenance"), data.get("observational_guards"), data.get("lifecycle_transition_trace")
    if data.get("schema_version") != SOURCE_SCHEMA or data.get("status") != "complete" or not all(isinstance(value, dict) for value in (config, provenance, guards, trace)):
        raise ValueError(f"not a completed A4.3.6 source: {path}")
    if config.get("preset") not in PRESETS or config.get("admission_budget") not in QUANTA or config.get("prefill_maturity_chunk_tokens") != 64 or config.get("fixed_new_tokens") != 8:
        raise ValueError(f"source lacks bounded Llama micro-event contract: {path}")
    if provenance != {"m0_manifest_sha256": m0_sha256, "m1_manifest_sha256": m1_sha256, "m51_report_sha256": m51_sha256, "m41_non_strict_summarization_context_retained": True}:
        raise ValueError(f"source provenance differs from supplied Llama prerequisites: {path}")
    required = {"m0_m1_m51_hash_bound": True, "m41_non_strict_summarization_context_retained": True, "all_32_layers_all_8_kv_heads_covered_dense_trace_off_and_microevent": True, "online_dense_mask_replayed_exactly_once_by_both_route_a_paths": True, "same_mask_numerical_guard_work_executed_by_all_paths": True, "record_only_ulp_context_not_a_strict_pass": True, "fixed_dense_token_trajectory_forced_in_route_a": True, "trace_off_route_a_tokens_equal_trace_on_microevent": True, "prefill_micro_event_trace_enabled": True, "logical_events_have_no_timestamps": True, "fake_key_attention_used": False, "model_cache_mutated_by_backend": False}
    if any(guards.get(key) != value for key, value in required.items()):
        raise ValueError(f"source guard failed: {path}")
    trace_path = path.parent / str(trace.get("path"))
    if trace.get("prefill_maturity_chunk_tokens") != 64 or sha256(trace_path) != trace.get("sha256"):
        raise ValueError(f"source trace hash/contract failed: {path}")
    with gzip.open(trace_path, "rt", encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle if line.strip()]
    if not events:
        raise ValueError(f"empty source trace: {path}")
    last: dict[int, int] = {}
    for event in events:
        layer = int(event["layer"])
        if event.get("timestamps_recorded") is not False or int(event["start_position"]) != last.get(layer, -1) + 1:
            raise ValueError(f"non-contiguous or timed lifecycle event: {path}")
        last[layer] = int(event["end_position"])
    return data, events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.3.6 hash-bound Llama Q={1,8,32} micro-event comparison; no timing/FIFO/hardware claim.")
    parser.add_argument("--m0-manifest", type=Path, required=True)
    parser.add_argument("--m1-manifest", type=Path, required=True)
    parser.add_argument("--m51-report", type=Path, required=True)
    parser.add_argument("--policy-manifest", action="append", type=Path, required=True, help="Exactly nine A4.3.6 sources: three presets times Q=1,8,32.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_dir.exists() or len(args.policy_manifest) != 9:
        raise ValueError("A4.3.6 requires nine sources and a new output directory")
    hashes = {"m0_manifest_sha256": sha256(args.m0_manifest), "m1_manifest_sha256": sha256(args.m1_manifest), "m51_report_sha256": sha256(args.m51_report)}
    sources = [(path, *load_source(path, m0_sha256=hashes["m0_manifest_sha256"], m1_sha256=hashes["m1_manifest_sha256"], m51_sha256=hashes["m51_report_sha256"])) for path in args.policy_manifest]
    indexed = {(data["config"]["preset"], data["config"]["admission_budget"]): (path, data, events) for path, data, events in sources}
    if set(indexed) != {(preset, quantum) for preset in PRESETS for quantum in QUANTA}:
        raise ValueError("A4.3.6 requires every preset at Q=1,8,32 exactly once")
    rows = []
    for preset in sorted(PRESETS):
        batch_hashes = {indexed[(preset, quantum)][1]["route_a_trace_off_generated_token_ids_sha256"] for quantum in QUANTA}
        dense_hashes = {indexed[(preset, quantum)][1]["dense_generated_token_ids_sha256"] for quantum in QUANTA}
        if len(batch_hashes) != 1 or len(dense_hashes) != 1 or batch_hashes != dense_hashes:
            raise AssertionError(f"Llama micro-event Q sweep changed the conditioned dense/Route-A token trajectory for {preset}")
        rows.append({"preset": preset, "conditioned_dense_and_trace_off_token_ids_sha256_shared_across_quanta": next(iter(batch_hashes)), "quantum_rows": [{"admission_budget": quantum, "manifest_path": str(indexed[(preset, quantum)][0]), "manifest_sha256": sha256(indexed[(preset, quantum)][0]), "lifecycle_trace": indexed[(preset, quantum)][1]["lifecycle_transition_trace"], "transition_summary": summarize(indexed[(preset, quantum)][2])} for quantum in sorted(QUANTA)]})
    config = {"m0_manifest": {"path": str(args.m0_manifest), "sha256": hashes["m0_manifest_sha256"]}, "m1_manifest": {"path": str(args.m1_manifest), "sha256": hashes["m1_manifest_sha256"]}, "m51_report": {"path": str(args.m51_report), "sha256": hashes["m51_report_sha256"]}, "policy_manifests": [{"path": str(path), "sha256": sha256(path)} for path in args.policy_manifest], "prefill_maturity_chunk_tokens": 64, "fixed_new_tokens": 8, "admission_budgets": sorted(QUANTA)}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model comparison of hash-bound fixed-continuation functional/trace-derived Llama micro-event states; not timing, FIFO, or hardware evidence", "per_workload_rows": rows, "observational_guards": {"all_nine_sources_hash_and_semantic_guards_verified": True, "m41_non_strict_summarization_context_retained": True, "conditioned_dense_and_trace_off_token_trajectory_shared_across_quanta": True, "logical_events_have_no_timestamps": True}, "architecture_spec_gate": {"eligible": False, "rtl_authorized": False, "reason": "This conditioned Llama sweep selects no controller rate, FIFO depth, page/bank/burst parameter, or architecture."}, "boundaries": ["The fixed continuation is a functional conditioning mechanism, not natural-generation or serving evidence.", "The retained record-only ULP context is not a strict numerical pass and does not select merge precision.", "Q is a declared reference action count, not a hardware service rate. No HBM traffic, latency, throughput, energy, area, capacity, page/bank/burst, or RTL claim follows."]}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "a436_llama31_microevent_quantum_sweep_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.3.6 Llama quantum sweep completed: {args.output_dir / 'a436_llama31_microevent_quantum_sweep_report.json'}")


if __name__ == "__main__":
    main()
