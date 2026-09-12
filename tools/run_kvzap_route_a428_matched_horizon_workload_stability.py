"""A4.2.8 matched-horizon three-workload logical-event stability pipeline."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.analyze_kvzap_route_a425_ordered_logical_schedule import (
    A424_SCHEMA, event_path, load_complete, load_events, require_true,
    validate_events, verify_manifest_event_summary,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


A428_SCHEMA = "kvzap-route-a428-matched-horizon-workload-stability-1.0"
SOURCE_SCHEMA = "kvzap-route-a41-replay-mask-source-1.0"
EXECUTION_SCHEMA = "kvzap-route-a4151-guard-elided-execution-semantic-gate-1.0"
ELISION_SCHEMA = "kvzap-route-a4154-empty-source-elision-semantic-gate-1.0"
SOURCES = ("hot", "pending", "packed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.2.8 matched-horizon three-workload Route-A logical-event study; no timing benchmark.")
    parser.add_argument("--presets", nargs="+", choices=("summarization", "retrieval", "reasoning"), default=["summarization", "retrieval", "reasoning"])
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--max-new-tokens", type=int, default=8, help="Shared declared cap; actual policy-call count is separately required to match.")
    parser.add_argument("--admission-budget", type=int, default=512)
    parser.add_argument("--target-layers", nargs="+", default=["all"])
    parser.add_argument("--target-kv-head", choices=("all",), default="all")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_child(script: str, args: list[str]) -> None:
    root = str(Path(__file__).resolve().parents[1])
    pythonpath = os.pathsep.join(x for x in (root, os.environ.get("PYTHONPATH", "")) if x)
    environment = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "PYTHONPATH": pythonpath}
    print(f"Running: {script}", flush=True)
    subprocess.run([sys.executable, script, *args], check=True, env=environment)


def policy_decode_calls(source: dict[str, Any]) -> int:
    values = set(source.get("policy_decode_call_count_by_layer", {}).values())
    if len(values) != 1 or not all(isinstance(value, int) and value >= 2 for value in values):
        raise ValueError("source lacks one consistent policy-decode-call count across layers")
    return values.pop()


def require_source(source: dict[str, Any], *, cap: int) -> int:
    if source.get("config", {}).get("max_new_tokens") != cap:
        raise ValueError("source declared max-new-tokens differs from matched child cap")
    rows = source.get("replay_event_coverage", {}).get("layers", [])
    if len(rows) != 36 or any(row.get("layer") != index or row.get("expected_kv_heads") != list(range(8)) or row.get("observed_kv_heads") != list(range(8)) or row.get("missing_kv_heads") or row.get("unexpected_kv_heads") for index, row in enumerate(rows)):
        raise ValueError("source does not cover all 36 layers and eight KV heads")
    return policy_decode_calls(source)


def percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    return sorted(values)[int((len(values) - 1) * fraction)]


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    combinations, fan_in = Counter(), Counter()
    records = {source: [] for source in SOURCES}
    pages, tails = [], []
    for event in events:
        active = []
        for decision in event["source_decisions"]:
            source = decision["source"]
            if decision["outcome"] == "partial":
                active.append(source); records[source].append(int(decision["record_count"]))
        combinations["+".join(active)] += 1
        fan_in[f"{len(active)}_active_sources"] += 1
        pages.append(int(event["packed_page_count"])); tails.append(int(event["packed_tail_tokens"]))
    count = len(events)
    if not count or sum(fan_in.values()) != count:
        raise ValueError("incomplete logical-event accounting")
    return {
        "event_count": count,
        "source_outcome_counts": {source: {"partial": len(records[source]), "skip": count - len(records[source])} for source in SOURCES},
        "source_record_count_distribution": {source: {"sample_count": len(values), "sum": sum(values), "p50": percentile(values, .5), "p95": percentile(values, .95), "max": max(values, default=None)} for source, values in records.items()},
        "fan_in_fractions": {key: value / count for key, value in sorted(fan_in.items())},
        "source_combination_fractions": {key: value / count for key, value in sorted(combinations.items())},
        "packed_page_witness_distribution": {"p50": percentile(pages, .5), "p95": percentile(pages, .95), "max": max(pages), "tail_p50": percentile(tails, .5), "tail_p95": percentile(tails, .95), "tail_max": max(tails)},
    }


def spread(rows: dict[str, dict[str, Any]], field: str) -> dict[str, dict[str, float]]:
    keys = sorted({key for row in rows.values() for key in row[field]})
    return {key: {"min": min(row[field].get(key, 0.0) for row in rows.values()), "max": max(row[field].get(key, 0.0) for row in rows.values()), "range": max(row[field].get(key, 0.0) for row in rows.values()) - min(row[field].get(key, 0.0) for row in rows.values())} for key in keys}


def read_a424(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], Path]:
    manifest = load_complete(path, A424_SCHEMA)
    require_true(manifest, ("trace_off_execution_only_verified", "trace_on_forced_logits_close", "trace_on_independent_tokens_equal_trace_off", "replay_consumption_complete_each_run", "all_layers_all_kv_heads_external_storage_substituted_each_run", "persistent_selected_native_cold_absent_each_run", "ordered_event_source_decisions_partition_merges", "ordered_event_all_layer_all_kv_head_coverage", "logical_event_has_no_timestamps"), "A424")
    path = event_path(path, manifest); events = load_events(path)
    validation = validate_events(events)
    verify_manifest_event_summary(manifest, validation)
    return manifest, events, path


def main() -> None:
    args = parse_args()
    if args.output_dir.exists(): raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if sorted(args.presets) != ["reasoning", "retrieval", "summarization"] or len(set(args.presets)) != 3: raise ValueError("A4.2.8 requires each of summarization, retrieval, and reasoning exactly once")
    if args.target_layers != ["all"] or args.target_kv_head != "all" or args.admission_budget != 512 or args.max_new_tokens < 2 or args.context_repetitions <= 0: raise ValueError("A4.2.8 requires all layers/heads, budget 512, cap >=2, and positive repetitions")
    args.output_dir.mkdir(parents=True)
    sources: dict[str, tuple[Path, dict[str, Any], int]] = {}
    common = ["--context-repetitions", str(args.context_repetitions), "--max-new-tokens", str(args.max_new_tokens), "--admission-budget", str(args.admission_budget), "--target-layers", "all", "--seed", str(args.seed)]
    for preset in args.presets:
        directory = args.output_dir / preset / "source"
        run_child("tools/collect_kvzap_route_a41_replay_source.py", ["--preset", preset, *common, "--require-all-kv-heads", "--output-dir", str(directory)])
        manifest = load_complete(directory / "a41_replay_mask_source_manifest.json", SOURCE_SCHEMA)
        sources[preset] = (directory, manifest, require_source(manifest, cap=args.max_new_tokens))
    observed = {value[2] for value in sources.values()}
    if len(observed) != 1: raise ValueError(f"matched declared cap produced unequal actual policy-decode-call counts: {sorted(observed)}")
    per_workload = {}
    for preset, (source_dir, source, calls) in sources.items():
        root = args.output_dir / preset
        child = ["--preset", preset, *common, "--target-kv-head", "all", "--device", args.device, "--replay-source-dir", str(source_dir)]
        execution = root / "execution_semantic"; elision = root / "elision_semantic"; ordered = root / "ordered_events"
        run_child("tools/run_kvzap_route_a4151_guard_elided_execution_semantic_gate.py", [*child, "--require-replay-event-coverage", "--output-dir", str(execution)])
        run_child("tools/run_kvzap_route_a4154_empty_source_elision_semantic_gate.py", [*child, "--require-cross-workload-source-coverage", "--route-a-execution-certification", str(execution / "a4151_guard_elided_execution_manifest.json"), "--output-dir", str(elision)])
        run_child("tools/run_kvzap_route_a424_ordered_logical_event_gate.py", [*child, "--route-a-execution-certification", str(execution / "a4151_guard_elided_execution_manifest.json"), "--output-dir", str(ordered)])
        execution_manifest = load_complete(execution / "a4151_guard_elided_execution_manifest.json", EXECUTION_SCHEMA)
        elision_manifest = load_complete(elision / "a4154_empty_source_elision_manifest.json", ELISION_SCHEMA)
        require_true(execution_manifest, ("replay_consumption_complete", "all_layers_all_kv_heads_external_storage_substituted", "persistent_selected_native_cold_absent", "forced_full_model_logits_close", "independent_greedy_tokens_equal_guarded", "required_replay_event_coverage_verified"), f"{preset} A4151")
        require_true(elision_manifest, ("replay_consumption_complete", "all_layers_all_kv_heads_external_storage_substituted", "persistent_selected_native_cold_absent", "forced_full_model_logits_close", "independent_greedy_tokens_equal_baseline", "empty_pending_source_skip_observed", "source_partial_or_skip_accounting_matches_merge"), f"{preset} A4154")
        manifest, events, event_file = read_a424(ordered / "a424_ordered_logical_event_manifest.json")
        per_workload[preset] = {"actual_policy_decode_calls": calls, "source_manifest_sha256": sha256(source_dir / "a41_replay_mask_source_manifest.json"), "source_event_sha256": sha256(source_dir / "replay_mask_events.npz"), "a424_manifest_sha256": sha256(ordered / "a424_ordered_logical_event_manifest.json"), "logical_event_sha256": sha256(event_file), "summary": summarize_events(events)}
    summaries = {preset: row["summary"] for preset, row in per_workload.items()}
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    result = {"schema_version": A428_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "per_workload": per_workload, "cross_workload": {"shared_actual_policy_decode_calls": observed.pop(), "fan_in_fraction_spread": spread(summaries, "fan_in_fractions"), "source_combination_fraction_spread": spread(summaries, "source_combination_fractions"), "interpretation": "Matched-cap, matched policy-decode-call fixed-request logical-event accounting only; no stability threshold, scheduler choice, or performance inference."}, "observational_guards": {"three_fresh_sources_collected": True, "shared_declared_max_new_tokens": True, "shared_actual_policy_decode_calls": True, "all_workloads_semantics_certified": True, "all_workloads_a424_event_guards_verified": True, "no_stability_threshold_selected": True}, "boundaries": ["Functional and timestamp-free logical-event evidence only; no quality benchmark, runtime, profiler, allocator, HBM, throughput, energy, area, hardware, or RTL claim.", "Matched actual policy-decode-call counts remove this specific horizon mismatch, but three fixed built-in requests do not establish a workload distribution or cross-model generality.", "Events contain invocation order and source decisions, not source completion/reduction arrival time, queue occupancy, backpressure, FIFO depth, cycles, latency, or placement benefit."]}
    output = args.output_dir / "a428_matched_horizon_workload_stability_report.json"; output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.2.8 matched-horizon workload stability completed: {output}")


if __name__ == "__main__": main()
