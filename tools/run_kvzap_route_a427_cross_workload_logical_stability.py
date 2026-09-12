"""A4.2.7 second-workload semantic event pipeline and no-model stability report."""
from __future__ import annotations

import argparse
import gzip
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
    A424_SCHEMA,
    _active_sources,
    event_path,
    load_complete,
    load_events,
    require_true,
    validate_events,
    verify_manifest_event_summary,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


A427_SCHEMA = "kvzap-route-a427-cross-workload-logical-stability-1.0"
SOURCE_SCHEMA = "kvzap-route-a41-replay-mask-source-1.0"
EXECUTION_SCHEMA = "kvzap-route-a4151-guard-elided-execution-semantic-gate-1.0"
ELISION_SCHEMA = "kvzap-route-a4154-empty-source-elision-semantic-gate-1.0"
SOURCES = ("hot", "pending", "packed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A4.2.7 fresh second-workload Route-A semantic/event stability pipeline; no timing benchmark."
    )
    parser.add_argument("--candidate-preset", choices=("retrieval",), default="retrieval")
    parser.add_argument("--reference-ordered-event-manifest", type=Path, required=True)
    parser.add_argument("--context-repetitions", type=int, default=12)
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--admission-budget", type=int, default=512)
    parser.add_argument("--target-layers", nargs="+", default=["all"])
    parser.add_argument("--target-kv-head", choices=("all",), default="all")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def child_command(*, script: str, args: list[str]) -> list[str]:
    return [sys.executable, script, *args]


def run_child(*, script: str, args: list[str]) -> None:
    print(f"Running: {script}", flush=True)
    repository_root = str(Path(__file__).resolve().parents[1])
    inherited_pythonpath = os.environ.get("PYTHONPATH", "")
    environment = {
        **os.environ,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONPATH": os.pathsep.join(value for value in (repository_root, inherited_pythonpath) if value),
    }
    subprocess.run(child_command(script=script, args=args), check=True, env=environment)


def source_combination_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    combinations = Counter()
    fan_in = Counter()
    for event in events:
        active = _active_sources(event)
        combinations["+".join(active)] += 1
        fan_in[f"{len(active)}_active_sources"] += 1
    count = len(events)
    if count <= 0 or sum(fan_in.values()) != count:
        raise ValueError("event fan-in accounting is incomplete")
    return {
        "event_count": count,
        "source_outcome_counts": {
            source: {"partial": sum(source in _active_sources(event) for event in events), "skip": sum(source not in _active_sources(event) for event in events)}
            for source in SOURCES
        },
        "fan_in_counts": dict(sorted(fan_in.items())),
        "fan_in_fractions": {name: value / count for name, value in sorted(fan_in.items())},
        "source_combination_counts": dict(sorted(combinations.items())),
        "source_combination_fractions": {name: value / count for name, value in sorted(combinations.items())},
    }


def read_accepted_a424(path: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    manifest = load_complete(path, A424_SCHEMA)
    require_true(manifest, (
        "trace_off_execution_only_verified", "trace_on_forced_logits_close",
        "trace_on_independent_tokens_equal_trace_off", "replay_consumption_complete_each_run",
        "all_layers_all_kv_heads_external_storage_substituted_each_run",
        "persistent_selected_native_cold_absent_each_run", "ordered_event_source_decisions_partition_merges",
        "ordered_event_all_layer_all_kv_head_coverage", "logical_event_has_no_timestamps",
    ), "A424")
    events_file = event_path(path, manifest)
    events = load_events(events_file)
    validation = validate_events(events)
    if validation["event_count"] != manifest.get("logical_event_artifact", {}).get("event_count"):
        raise ValueError("A424 event-file count differs from manifest")
    verify_manifest_event_summary(manifest, validation)
    return manifest, {"validation": validation, "summary": source_combination_summary(events)}, events_file


def policy_scope(manifest: dict[str, Any]) -> dict[str, Any]:
    config = manifest.get("config", {})
    return {
        "model_name": config.get("model_name"),
        "model_revision": config.get("model_revision"),
        "predictor_name": config.get("predictor_name"),
        "predictor_revision": config.get("predictor_revision"),
        "threshold": config.get("threshold"),
        "window_size": config.get("window_size"),
        "page_tokens": config.get("page_tokens"),
        "admission_budget": config.get("admission_budget"),
        "max_new_tokens": config.get("max_new_tokens"),
        "target_layers": config.get("target_layers"),
        "target_kv_head": config.get("target_kv_head"),
    }


def verify_source_coverage(source_manifest: dict[str, Any]) -> None:
    coverage = source_manifest.get("replay_event_coverage", {})
    rows = coverage.get("layers", [])
    if coverage.get("layer_count") != 36 or len(rows) != 36:
        raise ValueError("candidate replay source lacks 36-layer coverage")
    for expected_layer, row in enumerate(rows):
        if row.get("layer") != expected_layer or row.get("missing_kv_heads") or row.get("unexpected_kv_heads"):
            raise ValueError("candidate replay source lacks exact KV-head coverage")
        if row.get("expected_kv_heads") != list(range(8)) or row.get("observed_kv_heads") != list(range(8)):
            raise ValueError("candidate replay source does not cover all eight KV heads")


def observed_source_decode_horizon(source_manifest: dict[str, Any]) -> int:
    counts = source_manifest.get("policy_decode_call_count_by_layer", {})
    if not isinstance(counts, dict) or len(counts) != 36:
        raise ValueError("candidate replay source lacks per-layer decode-call accounting")
    values = set(counts.values())
    if len(values) != 1 or not all(isinstance(value, int) for value in values):
        raise ValueError("candidate replay source has inconsistent per-layer decode horizon")
    horizon = values.pop()
    if horizon < 2:
        raise ValueError("candidate replay source horizon is too short for A424")
    return horizon


def validate_semantic_source_contract(
    source_manifest: dict[str, Any], *, declared_max_new_tokens: int
) -> int:
    """Bind the replay source to the child CLI contract without equating calls and cap.

    `max_new_tokens` bounds generated tokens, whereas the collector records only
    q_len=1 policy attention calls. They can differ for a multi-token question
    and when generation stops at EOS. Complete consumption is consequently
    checked by A4151/A4154/A424, not by an equality assertion here.
    """
    configured = source_manifest.get("config", {}).get("max_new_tokens")
    if configured != declared_max_new_tokens:
        raise ValueError("semantic replay source max-new-tokens differs from child configuration")
    return observed_source_decode_horizon(source_manifest)


def compare(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    ref_scope, candidate_scope = policy_scope(reference["manifest"]), policy_scope(candidate["manifest"])
    ref_horizon = ref_scope.pop("max_new_tokens")
    candidate_horizon = candidate_scope.pop("max_new_tokens")
    if ref_scope != candidate_scope:
        raise ValueError("reference and candidate A424 non-horizon policy scopes differ")
    ref_summary, candidate_summary = reference["summary"], candidate["summary"]
    source_rates = {}
    for source in SOURCES:
        ref_rate = ref_summary["source_outcome_counts"][source]["partial"] / ref_summary["event_count"]
        candidate_rate = candidate_summary["source_outcome_counts"][source]["partial"] / candidate_summary["event_count"]
        source_rates[source] = {
            "reference_partial_fraction": ref_rate,
            "candidate_partial_fraction": candidate_rate,
            "candidate_minus_reference_partial_fraction": candidate_rate - ref_rate,
        }

    def fraction_deltas(key: str) -> dict[str, Any]:
        names = sorted(set(ref_summary[key]) | set(candidate_summary[key]))
        return {
            name: {
                "reference_fraction": ref_summary[key].get(name, 0.0),
                "candidate_fraction": candidate_summary[key].get(name, 0.0),
                "candidate_minus_reference_fraction": candidate_summary[key].get(name, 0.0) - ref_summary[key].get(name, 0.0),
            }
            for name in names
        }

    return {
        "common_non_horizon_policy_scope": ref_scope,
        "declared_effective_horizons": {"reference_max_new_tokens": ref_horizon, "candidate_max_new_tokens": candidate_horizon},
        "reference": reference["summary"],
        "candidate": candidate["summary"],
        "partial_source_fraction_deltas": source_rates,
        "fan_in_fraction_deltas": fraction_deltas("fan_in_fractions"),
        "source_combination_fraction_deltas": fraction_deltas("source_combination_fractions"),
        "interpretation": "This reports fixed-request event-structure differences only. It intentionally defines no stability threshold, no scheduler decision, and no performance interpretation.",
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.candidate_preset != "retrieval" or args.target_layers != ["all"] or args.target_kv_head != "all":
        raise ValueError("A4.2.7 requires retrieval with all layers and all KV heads")
    if args.admission_budget != 512 or args.max_new_tokens < 32 or args.context_repetitions <= 0:
        raise ValueError("A4.2.7 requires budget 512, horizon >=32, and positive context repetitions")
    reference_manifest, reference, reference_events = read_accepted_a424(args.reference_ordered_event_manifest)
    args.output_dir.mkdir(parents=True)
    horizon_probe_dir = args.output_dir / "horizon_probe_source"
    source_dir = args.output_dir / "source"
    execution_dir = args.output_dir / "execution_semantic"
    elision_dir = args.output_dir / "elision_semantic"
    candidate_dir = args.output_dir / "ordered_events"
    source_common = ["--preset", args.candidate_preset, "--context-repetitions", str(args.context_repetitions),
                     "--max-new-tokens", str(args.max_new_tokens), "--admission-budget", str(args.admission_budget),
                     "--target-layers", "all", "--seed", str(args.seed)]
    run_child(script="tools/collect_kvzap_route_a41_replay_source.py", args=[
        *source_common, "--require-all-kv-heads", "--output-dir", str(horizon_probe_dir)
    ])
    horizon_probe_manifest = load_complete(horizon_probe_dir / "a41_replay_mask_source_manifest.json", SOURCE_SCHEMA)
    verify_source_coverage(horizon_probe_manifest)
    semantic_max_new_tokens = observed_source_decode_horizon(horizon_probe_manifest)
    semantic_source_common = ["--preset", args.candidate_preset, "--context-repetitions", str(args.context_repetitions),
                              "--max-new-tokens", str(semantic_max_new_tokens), "--admission-budget", str(args.admission_budget),
                              "--target-layers", "all", "--seed", str(args.seed)]
    run_child(script="tools/collect_kvzap_route_a41_replay_source.py", args=[
        *semantic_source_common, "--require-all-kv-heads", "--output-dir", str(source_dir)
    ])
    source_manifest = load_complete(source_dir / "a41_replay_mask_source_manifest.json", SOURCE_SCHEMA)
    verify_source_coverage(source_manifest)
    semantic_source_policy_decode_calls = validate_semantic_source_contract(
        source_manifest, declared_max_new_tokens=semantic_max_new_tokens
    )
    common = ["--preset", args.candidate_preset, "--context-repetitions", str(args.context_repetitions),
              "--max-new-tokens", str(semantic_max_new_tokens), "--admission-budget", str(args.admission_budget),
              "--target-layers", "all", "--target-kv-head", "all", "--seed", str(args.seed)]
    run_child(script="tools/run_kvzap_route_a4151_guard_elided_execution_semantic_gate.py", args=[
        *common, "--require-replay-event-coverage", "--device", args.device, "--replay-source-dir", str(source_dir),
        "--output-dir", str(execution_dir),
    ])
    run_child(script="tools/run_kvzap_route_a4154_empty_source_elision_semantic_gate.py", args=[
        *common, "--require-cross-workload-source-coverage", "--device", args.device, "--replay-source-dir", str(source_dir),
        "--route-a-execution-certification", str(execution_dir / "a4151_guard_elided_execution_manifest.json"),
        "--output-dir", str(elision_dir),
    ])
    run_child(script="tools/run_kvzap_route_a424_ordered_logical_event_gate.py", args=[
        *common, "--device", args.device, "--replay-source-dir", str(source_dir),
        "--route-a-execution-certification", str(execution_dir / "a4151_guard_elided_execution_manifest.json"),
        "--output-dir", str(candidate_dir),
    ])
    execution_manifest = load_complete(execution_dir / "a4151_guard_elided_execution_manifest.json", EXECUTION_SCHEMA)
    require_true(execution_manifest, (
        "all_layers_all_kv_heads_external_storage_substituted", "forced_full_model_logits_close",
        "independent_greedy_tokens_equal_guarded", "persistent_selected_native_cold_absent",
        "replay_consumption_complete", "required_replay_event_coverage_verified",
    ), "candidate A4151")
    elision_manifest = load_complete(elision_dir / "a4154_empty_source_elision_manifest.json", ELISION_SCHEMA)
    require_true(elision_manifest, (
        "all_layers_all_kv_heads_external_storage_substituted", "empty_pending_source_skip_observed",
        "forced_full_model_logits_close", "independent_greedy_tokens_equal_baseline",
        "persistent_selected_native_cold_absent", "replay_consumption_complete",
        "required_cross_workload_source_coverage_verified", "source_partial_or_skip_accounting_matches_merge",
    ), "candidate A4154")
    candidate_manifest_path = candidate_dir / "a424_ordered_logical_event_manifest.json"
    candidate_manifest, candidate, candidate_events = read_accepted_a424(candidate_manifest_path)
    report = compare(
        {"manifest": reference_manifest, **reference},
        {"manifest": candidate_manifest, **candidate},
    )
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items() if key != "output_dir"}
    config.update({
        "candidate_source_collection_max_new_tokens": args.max_new_tokens,
        "candidate_horizon_probe_policy_decode_calls": semantic_max_new_tokens,
        "candidate_semantic_max_new_tokens": semantic_max_new_tokens,
        "candidate_semantic_source_policy_decode_calls": semantic_source_policy_decode_calls,
        "reference_ordered_event_manifest_sha256": sha256(args.reference_ordered_event_manifest),
        "reference_logical_event_sha256": sha256(reference_events),
        "candidate_ordered_event_manifest": str(candidate_manifest_path),
        "candidate_ordered_event_manifest_sha256": sha256(candidate_manifest_path),
        "candidate_logical_event_sha256": sha256(candidate_events),
    })
    result = {
        "schema_version": A427_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "children": {
            "horizon_probe_source": "horizon_probe_source/a41_replay_mask_source_manifest.json",
            "source": "source/a41_replay_mask_source_manifest.json",
            "execution": "execution_semantic/a4151_guard_elided_execution_manifest.json",
            "elision": "elision_semantic/a4154_empty_source_elision_manifest.json",
            "candidate_ordered_events": "ordered_events/a424_ordered_logical_event_manifest.json",
        },
        "report": report,
        "observational_guards": {
            "reference_a424_semantic_event_guards_verified": True,
            "candidate_horizon_probe_source_collected": True,
            "candidate_fresh_source_collected": True,
            "candidate_execution_semantics_certified": True,
            "candidate_elision_semantics_certified": True,
            "candidate_a424_semantic_event_guards_verified": True,
            "all_layers_all_kv_heads_covered_both_workloads": True,
            "common_non_horizon_policy_scope_equal_across_workloads": True,
            "candidate_semantic_source_declared_cap_matches_children": True,
            "candidate_semantic_source_policy_decode_calls_recorded": True,
            "no_stability_threshold_selected": True,
        },
        "boundaries": [
            "This is a fixed-request functional/logical-event cross-workload comparison. It is not a quality benchmark, runtime measurement, hardware trace, or architecture specification.",
            "The independent retrieval source is intentionally distinct from the summarization source. A caller-cap probe selects the semantic child max-new-tokens value; the separately collected semantic source records its actual q_len=1 policy-decode-call count. Those values are intentionally not equated because collector generation and EOS can change the count. A4151/A4154/A424 replay-complete gates, rather than this wrapper, verify exact event consumption; comparisons are normalized by each stream's event count.",
            "Event-composition differences do not reveal source service/completion order, reduction arrival, buffer occupancy, backpressure, FIFO depth, cycles, latency, throughput, HBM traffic, energy, area, or scheduler/placement benefit.",
            "No stability threshold, hardware parameter, scheduler, controller timing, final placement, acceleration, or RTL readiness is selected.",
        ],
    }
    output = args.output_dir / "a427_cross_workload_logical_stability_report.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.2.7 cross-workload logical stability pipeline completed: {output}")


if __name__ == "__main__":
    main()
