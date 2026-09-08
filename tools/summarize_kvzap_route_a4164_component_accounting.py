"""A4.1.7.13 offline component-accounting report from accepted A4.1 artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


A4164_SCHEMA = "kvzap-route-a4164-component-accounting-report-1.0"
ROUTE_PATH = "same_mask_route_a_external_storage_empty_source_elision"
DENSE_PATH = "same_mask_dense_replay"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.1.7.13 offline component-accounting report; no model execution and no timing claim.")
    p.add_argument("--paired-elision-manifest", type=Path, required=True, help="Completed A4161/A4155 paired Route-A measurement manifest.")
    p.add_argument("--three-path-manifest", type=Path, required=True, help="Completed A4162 three-path measurement manifest.")
    p.add_argument("--three-path-profiler-manifest", type=Path, required=True, help="Completed A4163 three-path profiler manifest.")
    p.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return p.parse_args()


def load_complete(path: Path, schema: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != schema or payload.get("status") != "complete":
        raise ValueError(f"not a completed {schema} artifact: {path}")
    return payload


def source_identity(manifest: dict[str, Any]) -> tuple[str, int]:
    source = manifest.get("replay_source", {})
    digest, count = source.get("event_file_sha256"), source.get("event_count")
    if not isinstance(digest, str) or not digest or not isinstance(count, int) or count <= 0:
        raise ValueError("artifact lacks replay event source identity")
    return digest, count


def require_true(manifest: dict[str, Any], names: tuple[str, ...]) -> None:
    guards = manifest.get("observational_guards", {})
    missing = [name for name in names if guards.get(name) is not True]
    if missing:
        raise ValueError(f"artifact lacks required guards: {missing}")


def path_result(summary: dict[str, Any], path: str) -> dict[str, Any]:
    for row in summary.get("results", []):
        if row.get("path") == path:
            return row
    raise ValueError(f"profiler summary lacks path {path}")


def reset_group(manifest: dict[str, Any], path: str) -> dict[str, Any]:
    for row in manifest.get("summary", {}).get("reset_run_aggregate_groups", []):
        if row.get("path") == path:
            return row
    raise ValueError(f"measurement lacks reset-run group {path}")


def positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def build_report(*, paired: dict[str, Any], three_path: dict[str, Any], profiler: dict[str, Any], profiler_summary: dict[str, Any]) -> dict[str, Any]:
    sources = [source_identity(item) for item in (paired, three_path, profiler)]
    if len(set(sources)) != 1:
        raise ValueError(f"artifact replay sources differ: {sources}")
    require_true(paired, ("a4154_empty_source_elision_semantics_certified", "execution_only_actual_numerical_guard_work_absent", "replay_mask_consumption_complete_each_reset_run"))
    require_true(three_path, ("same_mask_dense_guarded_vs_execution_only_certified", "all_layers_all_kv_heads_external_storage_substituted_each_route_a_reset_run", "execution_only_timed_token_digests_match_certificates"))
    require_true(profiler, ("a4162_three_path_measurement_verified", "route_a_source_partial_or_skip_accounting_matches_merge", "route_a_elided_pending_skip_observed", "profiler_token_digests_match_certificates"))
    route = path_result(profiler_summary, ROUTE_PATH)
    dense = path_result(profiler_summary, DENSE_PATH)
    account = route.get("source_phase_accounting", {})
    evaluations = positive_int(account.get("expected_attention_evaluations"), "expected attention evaluations")
    merge = positive_int(account.get("merge_calls"), "merge calls")
    if merge != evaluations:
        raise ValueError("merge calls differ from attention evaluations")
    by_source = account.get("by_source", {})
    rows = []
    actual_partials = 0
    decisions = 0
    for source in ("hot", "pending", "packed"):
        row = by_source.get(source, {})
        partial, skip, total = (positive_int(row.get("partial_attention_calls"), f"{source} partial"), int(row.get("empty_source_skip_calls", -1)), positive_int(row.get("total_source_decisions"), f"{source} total"))
        if skip < 0 or partial + skip != total or total != evaluations:
            raise ValueError(f"invalid {source} source accounting")
        actual_partials += partial; decisions += total
        rows.append({"source": source, "partial_attention_calls": partial, "empty_source_skip_calls": skip, "source_decisions": total})
    if decisions != evaluations * 3:
        raise ValueError("source decisions do not cover all three sources")
    generated = positive_int(route.get("generated_token_count"), "generated token count")
    dense_coverage = dense.get("phase_label_coverage", {})
    if positive_int(dense_coverage.get("expected_attention_evaluations"), "dense expected attention evaluations") != evaluations:
        raise ValueError("dense and Route-A profiler evaluation counts differ")
    for row in rows:
        row["partial_per_reported_generated_token"] = row["partial_attention_calls"] / generated
        row["skip_per_reported_generated_token"] = row["empty_source_skip_calls"] / generated
    route_group, dense_group, full_group = (reset_group(three_path, path) for path in (ROUTE_PATH, DENSE_PATH, "full_kv_bypass"))
    return {
        "replay_source": {"event_file_sha256": sources[0][0], "event_count": sources[0][1]},
        "fixed_request_generated_token_count": generated,
        "attention_accounting": {"expected_attention_evaluations": evaluations, "merge_calls": merge, "merge_per_reported_generated_token": merge / generated, "source_rows": rows, "all_three_source_decisions": decisions, "actual_route_a_partial_calls": actual_partials, "elided_empty_source_calls": decisions - actual_partials, "partial_call_reduction_fraction_from_three_source_unelided": (decisions - actual_partials) / decisions},
        "dense_vs_route_attention_structure": {"dense_tagged_attention_calls": positive_int(dense_coverage.get("tagged_attention_evaluations"), "dense tagged attention evaluations"), "route_actual_partial_calls": actual_partials, "route_partial_calls_per_dense_attention": actual_partials / evaluations, "route_merge_calls_per_dense_attention": merge / evaluations},
        "measured_reset_run_medians": {path: {"cuda_event_ms": group["cuda_event_ms_sum_per_reset_run"]["median"], "wall_ms": group["wall_ms_sum_per_reset_run"]["median"], "peak_allocated_bytes": group["peak_allocated_bytes_max_per_reset_run"]["median"], "peak_reserved_bytes": group["peak_reserved_bytes_max_per_reset_run"]["median"]} for path, group in ((ROUTE_PATH, route_group), (DENSE_PATH, dense_group), ("full_kv_bypass", full_group))},
        "boundaries": ["Counts are Python-reference software call/accounting observations for this fixed request, not hardware operations or traffic.", "Profiler ranges are intentionally excluded from arithmetic aggregation; reset-run timing distributions remain in A4162.", "Per-reported-generated-token normalization includes this runner's question-forward and multi-token bridge work; it is not a universal per-decode-step cost."],
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    paired = load_complete(args.paired_elision_manifest, "kvzap-route-a4155-empty-source-elision-paired-measurement-1.0")
    three_path = load_complete(args.three_path_manifest, "kvzap-route-a4162-cross-workload-three-path-measurement-1.0")
    profiler = load_complete(args.three_path_profiler_manifest, "kvzap-route-a4163-cross-workload-three-path-profiler-1.0")
    summary_path = args.three_path_profiler_manifest.parent / str(profiler.get("phase_summary"))
    profiler_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    report = build_report(paired=paired, three_path=three_path, profiler=profiler, profiler_summary=profiler_summary)
    config = {"paired_elision_manifest": str(args.paired_elision_manifest), "three_path_manifest": str(args.three_path_manifest), "three_path_profiler_manifest": str(args.three_path_profiler_manifest), "profiler_summary_sha256": __import__("hashlib").sha256(summary_path.read_bytes()).hexdigest()}
    args.output_dir.mkdir(parents=True)
    manifest = {"schema_version": A4164_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "report": report, "observational_guards": {"input_artifacts_complete": True, "replay_source_identity_equal": True, "input_semantic_and_execution_guards_verified": True, "route_a_source_partial_or_skip_accounting_matches_merge": True, "profiler_ranges_not_aggregated_as_latency": True}, "boundaries": report["boundaries"]}
    out = args.output_dir / "a4164_component_accounting_report.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.7.13 component-accounting report completed: {out}")


if __name__ == "__main__":
    main()
