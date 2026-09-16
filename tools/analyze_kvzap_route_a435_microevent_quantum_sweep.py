#!/usr/bin/env python3
"""A4.3.5 no-model comparison of accepted micro-event quantum gates."""
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
SCHEMA = "kvzap-route-a435-microevent-quantum-sweep-1.0"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_source(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    config, guards, trace = data.get("config"), data.get("observational_guards"), data.get("lifecycle_transition_trace")
    if data.get("schema_version") != "kvzap-route-a40-policy-on-qwen-gate-1.7" or not isinstance(config, dict) or not isinstance(guards, dict) or not isinstance(trace, dict):
        raise ValueError(f"not an A4.3.4/A4.3.5 source: {path}")
    if config.get("preset") not in PRESETS or config.get("prefill_maturity_chunk_tokens") != 64 or config.get("admission_budget") not in QUANTA:
        raise ValueError(f"source lacks bounded chunk-64/Q contract: {path}")
    required = {"replay_mask_consumption_complete": True, "execution_dtype_close_enforced": True, "prefill_micro_event_trace_enabled": True, "trace_off_route_a_answer_equals_trace_on": True, "fake_key_attention_used": False, "model_cache_mutated_by_backend": False}
    if any(guards.get(key) != value for key, value in required.items()):
        raise ValueError(f"source semantic guard failed: {path}")
    trace_path = path.parent / str(trace.get("path"))
    if trace.get("prefill_maturity_chunk_tokens") != 64 or sha256(trace_path) != trace.get("sha256"):
        raise ValueError(f"source trace hash/contract failed: {path}")
    with gzip.open(trace_path, "rt", encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle if line.strip()]
    if not events:
        raise ValueError(f"empty source trace: {path}")
    last = {}
    for event in events:
        layer = event["layer"]
        if event.get("timestamps_recorded") is not False or event["start_position"] != last.get(layer, -1) + 1:
            raise ValueError("non-contiguous/timed lifecycle event")
        last[layer] = event["end_position"]
    return data, events


def summarize(events: list[dict[str, Any]]) -> dict[str, int]:
    rows = [row for event in events for row in event["heads"]]
    pending = sorted(int(row["pending_tokens_after_service"]) for row in rows)
    return {"logical_event_count": len(events), "prefill_event_count": sum(event["phase"] == "prefill" for event in events), "max_prefill_event_tokens": max(event["input_token_count"] for event in events if event["phase"] == "prefill"), "pending_p95": pending[min(len(pending) - 1, int((len(pending) - 1) * .95 + .999999))], "pending_max": max(pending), "admitted_tokens_total": sum(int(row["admitted_tokens"]) for row in rows), "packed_tokens_max": max(int(row["packed_tokens_after_service"]) for row in rows), "full_pages_max": max(int(row["packed_full_page_count_after_service"]) for row in rows)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.3.5 hash-bound micro-event Q={1,8,32} comparison; no timing/FIFO/hardware claim.")
    parser.add_argument("--policy-manifest", action="append", type=Path, required=True, help="Exactly nine A4.3.4/A4.3.5 manifests: three presets times Q=1,8,32.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_dir.exists() or len(args.policy_manifest) != 9:
        raise ValueError("A4.3.5 requires nine sources and a new output directory")
    sources = [(path, *load_source(path)) for path in args.policy_manifest]
    indexed = {(data["config"]["preset"], data["config"]["admission_budget"]): (path, data, events) for path, data, events in sources}
    if set(indexed) != {(preset, quantum) for preset in PRESETS for quantum in QUANTA}:
        raise ValueError("A4.3.5 requires every preset at Q=1,8,32 exactly once")
    rows = []
    for preset in sorted(PRESETS):
        hashes = {indexed[(preset, quantum)][1]["route_a_fast_path_answer_sha256"] for quantum in sorted(QUANTA)}
        if len(hashes) != 1:
            raise AssertionError(f"micro-event Q sweep changed batch Route-A answer for {preset}")
        rows.append({"preset": preset, "batch_route_answer_sha256_shared_across_quanta": next(iter(hashes)), "quantum_rows": [{"admission_budget": quantum, "manifest_path": str(indexed[(preset, quantum)][0]), "manifest_sha256": sha256(indexed[(preset, quantum)][0]), "lifecycle_trace": indexed[(preset, quantum)][1]["lifecycle_transition_trace"], "transition_summary": summarize(indexed[(preset, quantum)][2])} for quantum in sorted(QUANTA)]})
    config = {"policy_manifests": [{"path": str(path), "sha256": sha256(path)} for path in args.policy_manifest], "prefill_maturity_chunk_tokens": 64, "admission_budgets": sorted(QUANTA)}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model comparison of hash-bound functional/trace-derived micro-event states; not timing, FIFO, or hardware evidence", "per_workload_rows": rows, "architecture_spec_gate": {"eligible": False, "rtl_authorized": False, "reason": "The sweep selects no controller rate, FIFO depth, page/bank/burst parameter, or architecture."}, "boundaries": ["Q is a declared reference admission action, not a hardware service rate.", "No HBM traffic, latency, throughput, energy, area, capacity, page/bank/burst, or RTL claim follows."]}
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "a435_microevent_quantum_sweep_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.3.5 completed: {args.output_dir / 'a435_microevent_quantum_sweep_report.json'}")


if __name__ == "__main__":
    main()
