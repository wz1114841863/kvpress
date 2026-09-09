"""A4.1.7.17 no-model cross-horizon Route-A accounting report."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


A4168_SCHEMA = "kvzap-route-a4168-cross-horizon-accounting-report-1.0"
A4164_SCHEMA = "kvzap-route-a4164-component-accounting-report-1.0"
A4167_SCHEMA = "kvzap-route-a4167-long-horizon-three-path-profiler-1.0"
A4163_SCHEMA = "kvzap-route-a4163-cross-workload-three-path-profiler-1.0"
ROUTE_PATH = "same_mask_route_a_external_storage_empty_source_elision"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.7.17 offline cross-horizon source/page accounting; no model execution and no timing claim.")
    parser.add_argument("--h16-component-accounting", type=Path, required=True)
    parser.add_argument("--h32-three-path-profiler", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def load_complete(path: Path, schema: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != schema or payload.get("status") != "complete":
        raise ValueError(f"not a completed {schema} artifact: {path}")
    return payload


def require_true(manifest: dict[str, Any], names: tuple[str, ...]) -> None:
    missing = [name for name in names if manifest.get("observational_guards", {}).get(name) is not True]
    if missing:
        raise ValueError(f"artifact lacks required guards: {missing}")


def positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def route_result(summary: dict[str, Any]) -> dict[str, Any]:
    for row in summary.get("results", []):
        if row.get("path") == ROUTE_PATH:
            return row
    raise ValueError("profiler summary lacks Route-A external-storage/elision path")


def normalise_accounting(*, generated: int, accounting: dict[str, Any], page_guard: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    generated = positive_int(generated, "generated token count")
    merges = positive_int(accounting.get("merge_calls"), "merge calls")
    evaluations = positive_int(accounting.get("expected_attention_evaluations"), "attention evaluations")
    if merges != evaluations:
        raise ValueError("merge calls differ from attention evaluations")
    rows = []
    partials = skips = decisions = 0
    for name in ("hot", "packed", "pending"):
        row = accounting.get("by_source", {}).get(name)
        if row is None:
            row = next((item for item in accounting.get("source_rows", []) if item.get("source") == name), None)
        if not isinstance(row, dict):
            raise ValueError(f"missing {name} source accounting")
        partial = positive_int(row.get("partial_attention_calls"), f"{name} partial calls")
        skip = row.get("empty_source_skip_calls")
        total = positive_int(row.get("total_source_decisions", row.get("source_decisions")), f"{name} decisions")
        if not isinstance(skip, int) or skip < 0 or partial + skip != total or total != evaluations:
            raise ValueError(f"invalid {name} source accounting")
        partials += partial; skips += skip; decisions += total
        rows.append({"source": name, "partial_attention_calls": partial, "empty_source_skip_calls": skip, "source_decisions": total, "partial_per_reported_generated_token": partial / generated, "skip_per_reported_generated_token": skip / generated})
    if decisions != 3 * evaluations:
        raise ValueError("source decisions do not cover hot, packed, and pending for every merge")
    event_sha = source.get("event_file_sha256")
    event_count = source.get("event_count")
    if not isinstance(event_sha, str) or not event_sha or not isinstance(event_count, int) or event_count <= 0:
        raise ValueError("invalid source identity")
    page_fields = ("selected_layer_count", "selected_kv_head_count", "max_packed_page_count", "max_packed_full_page_count", "max_packed_tail_tokens", "page_witness_count")
    page = {name: positive_int(page_guard.get(name), name) for name in page_fields}
    if page["max_packed_full_page_count"] > page["max_packed_page_count"]:
        raise ValueError("full page count exceeds page count")
    return {"generated_token_count": generated, "replay_source": {"event_file_sha256": event_sha, "event_count": event_count}, "merge_calls": merges, "merge_per_reported_generated_token": merges / generated, "source_rows": rows, "actual_partial_calls": partials, "empty_source_skip_calls": skips, "partial_call_reduction_fraction_from_three_source_unelided": skips / decisions, "partial_calls_per_merge": partials / merges, "page_tail_coverage": page}


def h16_row(component: dict[str, Any]) -> dict[str, Any]:
    require_true(component, ("input_artifacts_complete", "replay_source_identity_equal", "input_semantic_and_execution_guards_verified", "route_a_source_partial_or_skip_accounting_matches_merge", "profiler_ranges_not_aggregated_as_latency"))
    profiler_path = Path(component["config"]["three_path_profiler_manifest"])
    profiler = load_complete(profiler_path, A4163_SCHEMA)
    require_true(profiler, ("profiler_token_digests_match_certificates", "route_a_source_partial_or_skip_accounting_matches_merge", "route_a_elided_pending_skip_observed", "phase_rows_coalesced"))
    summary = json.loads((profiler_path.parent / profiler["phase_summary"]).read_text(encoding="utf-8"))
    route = route_result(summary)
    report = component["report"]
    source = report["replay_source"]
    if profiler.get("replay_source", {}).get("event_file_sha256") != source.get("event_file_sha256"):
        raise ValueError("A4164 and its A4163 child source SHA-256 differ")
    return normalise_accounting(generated=report["fixed_request_generated_token_count"], accounting=report["attention_accounting"], page_guard=route["external_storage_guard"], source=source)


def h32_row(parent: dict[str, Any], parent_path: Path) -> dict[str, Any]:
    require_true(parent, ("a4166_long_horizon_measurement_verified", "a4163_child_complete", "child_source_sha_matches_a4165_and_a4166", "child_profiler_token_digests_match_certificates", "child_route_a_source_partial_or_skip_accounting_matches_merge", "child_phase_rows_coalesced", "profiler_is_separate_from_repeated_timing"))
    child_path = parent_path.parent / parent["a4163_child_manifest"]
    profiler = load_complete(child_path, A4163_SCHEMA)
    require_true(profiler, ("profiler_token_digests_match_certificates", "route_a_source_partial_or_skip_accounting_matches_merge", "route_a_elided_pending_skip_observed", "phase_rows_coalesced"))
    source = profiler["replay_source"]
    if source.get("event_file_sha256") != parent["config"].get("replay_event_file_sha256"):
        raise ValueError("A4167 parent and A4163 child source SHA-256 differ")
    summary = json.loads((child_path.parent / profiler["phase_summary"]).read_text(encoding="utf-8"))
    route = route_result(summary)
    return normalise_accounting(generated=route["generated_token_count"], accounting=route["source_phase_accounting"], page_guard=route["external_storage_guard"], source=source)


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    h16 = load_complete(args.h16_component_accounting, A4164_SCHEMA)
    h32 = load_complete(args.h32_three_path_profiler, A4167_SCHEMA)
    h16_accounting, h32_accounting = h16_row(h16), h32_row(h32, args.h32_three_path_profiler)
    if h16_accounting["generated_token_count"] >= h32_accounting["generated_token_count"]:
        raise ValueError("horizon order is not strictly increasing")
    config = {"h16_component_accounting": str(args.h16_component_accounting), "h32_three_path_profiler": str(args.h32_three_path_profiler), "h16_sha256": hashlib.sha256(args.h16_component_accounting.read_bytes()).hexdigest(), "h32_sha256": hashlib.sha256(args.h32_three_path_profiler.read_bytes()).hexdigest()}
    report = {"horizons": [{"label": "h16", **h16_accounting}, {"label": "h32", **h32_accounting}], "comparison": {"source_identity_equal_across_fresh_horizons": h16_accounting["replay_source"] == h32_accounting["replay_source"], "cross_horizon_source_identity_is_not_required": True, "partial_reduction_fraction_delta_h32_minus_h16": h32_accounting["partial_call_reduction_fraction_from_three_source_unelided"] - h16_accounting["partial_call_reduction_fraction_from_three_source_unelided"]}, "boundaries": ["This is an offline comparison of two independently collected fixed-request Python-reference accounting chains; source-mask identity across horizons is intentionally not required.", "Counts and page/tail witnesses are not hardware operations, HBM traffic, runtime, throughput, energy, area, or RTL evidence.", "No profiler time is aggregated or compared as latency; this report executes no model."]}
    args.output_dir.mkdir(parents=True)
    manifest = {"schema_version": A4168_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "report": report, "observational_guards": {"input_artifacts_complete": True, "h16_internal_provenance_verified": True, "h32_internal_provenance_verified": True, "fresh_horizon_sources_not_falsefully_equated": True, "source_partial_skip_merge_accounting_validated_per_horizon": True, "page_tail_coverage_validated_per_horizon": True, "profiler_ranges_not_aggregated_as_latency": True, "no_model_execution": True}, "boundaries": report["boundaries"]}
    output = args.output_dir / "a4168_cross_horizon_accounting_report.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.7.17 cross-horizon accounting report completed: {output}")


if __name__ == "__main__":
    main()
