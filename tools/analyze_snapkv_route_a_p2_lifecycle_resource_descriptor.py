#!/usr/bin/env python3
"""Describe the lifecycle/resource evidence exposed by accepted SnapKV P0/P1/P3.

This is deliberately a no-model contract study.  It does not turn absent
one-shot-prefill fields into zero-valued lifecycle, queue, or hardware facts.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kvpress.route_a_frontend_contract import SNAPKV_TERMINAL_EPOCH, sha256_file
from tools.analyze_kvzap_trace import get_git_commit, stable_hash
from tools.analyze_snapkv_route_a_p1_packed_opportunity import (
    P0_MANIFEST_NAME,
    P0_STREAM_NAME,
)
from tools.run_snapkv_route_a_p3_semantic_gate import (
    P1_REPORT_NAME,
    P3_SCHEMA,
    load_p3_inputs,
)


P2_SCHEMA = "route-a-snapkv-p2-lifecycle-resource-descriptor-1.0"
P3_MANIFEST_NAME = "snapkv_p3_semantic_manifest.json"
P2_REPORT_NAME = "snapkv_p2_lifecycle_resource_descriptor.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "P2 no-model SnapKV lifecycle/resource descriptor bound to completed P0/P1/P3; "
            "not a scheduler, timing, or hardware study."
        )
    )
    parser.add_argument("--p0-dir", type=Path, required=True, help="Completed SnapKV P0 directory only.")
    parser.add_argument("--p1-report", type=Path, required=True, help="Completed SnapKV P1 report JSON only.")
    parser.add_argument("--p3-dir", type=Path, required=True, help="Completed SnapKV P3 directory only.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def _require(value: Any, expected: Any, *, label: str) -> None:
    if value != expected:
        raise ValueError(f"{label} differs from the accepted SnapKV P2 contract: {value!r}")


def load_p2_inputs(
    p0_dir: Path, p1_report_path: Path, p3_dir: Path
) -> tuple[dict[str, Any], list[Any], dict[str, Any], dict[str, Any]]:
    """Load all completed prerequisites and reject an unbound P3 result."""
    p0, decisions, p1, _replay_masks = load_p3_inputs(p0_dir, p1_report_path)
    p3_path = p3_dir / P3_MANIFEST_NAME
    if not p3_path.is_file():
        raise FileNotFoundError("P2 requires the completed P3 semantic manifest")
    p3 = json.loads(p3_path.read_text(encoding="utf-8"))
    if p3.get("schema_version") != P3_SCHEMA or p3.get("status") != "complete":
        raise ValueError("P2 requires a complete SnapKV P3 manifest")
    provenance = p3.get("input_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("P3 manifest lacks input provenance")
    _require(
        provenance.get("p0_manifest_sha256"),
        sha256_file(p0_dir / P0_MANIFEST_NAME),
        label="P3 P0 manifest SHA-256",
    )
    _require(
        provenance.get("p0_terminal_stream_sha256"),
        sha256_file(p0_dir / P0_STREAM_NAME),
        label="P3 P0 terminal stream SHA-256",
    )
    _require(provenance.get("p1_report_sha256"), sha256_file(p1_report_path), label="P3 P1 report SHA-256")
    _require(provenance.get("p0_event_count"), len(decisions), label="P3 P0 event count")
    config = p3.get("config")
    if not isinstance(config, dict):
        raise ValueError("P3 manifest lacks config")
    _require(config.get("source_epoch"), SNAPKV_TERMINAL_EPOCH, label="P3 source epoch")
    _require(config.get("generated_token_forward_count"), 0, label="P3 generated-token forward count")
    guards = p3.get("observational_guards")
    if not isinstance(guards, dict):
        raise ValueError("P3 manifest lacks observational guards")
    required_true = (
        "p0_and_p1_sha256_bound_and_revalidated",
        "p1_native_score_ranked_gather_order_not_used",
        "all_qwen_layers_and_kv_heads_covered",
        "terminal_replay_consumed_exactly_once",
        "same_mask_dense_and_route_a_mask_digests_match",
        "fp32_same_mask_guard_enforced",
        "executed_dtype_ulp_breaches_recorded_not_selected",
        "p1_p64_hot_packed_state_matches_functional_route_a",
        "p3_prefill_tail_probes_do_not_replace_model_prefill_attention",
        "generated_token_forward_count_is_zero",
    )
    for field in required_true:
        _require(guards.get(field), True, label=f"P3 guard {field}")
    _require(guards.get("snapkv_native_cache_replacement_used"), False, label="P3 native cache replacement guard")
    _require(guards.get("route_a_predictor_scored_online"), False, label="P3 online predictor guard")
    return p0, decisions, p1, p3


def _field(
    name: str,
    status: str,
    evidence_classification: str,
    value: Any,
    evidence: str,
) -> dict[str, Any]:
    if status not in {"available", "unavailable"}:
        raise ValueError(f"unsupported P2 field status: {status}")
    return {
        "name": name,
        "status": status,
        "evidence_classification": evidence_classification,
        "value": value,
        "evidence": evidence,
    }


def build_descriptor(
    p0: dict[str, Any], decisions: list[Any], p1: dict[str, Any], p3: dict[str, Any]
) -> dict[str, Any]:
    """State which Route-A contract fields this one-shot frontend does and does not expose."""
    p1_p64 = next(row for row in p1["request_rows"] if row["page_tokens"] == 64)
    p3_state = p3["outcomes"]["same_mask_dense_vs_route_a_prefill_tail_probe"]["p1_p64_state_cross_check"]
    fields = [
        _field(
            "terminal_per_identity_action",
            "available",
            "trace-derived",
            {"decision_epoch": SNAPKV_TERMINAL_EPOCH, "event_count": len(decisions)},
            "P0 validated one terminal keep/drop action for every (layer, KV head, original position).",
        ),
        _field(
            "canonical_identity_and_append_order",
            "available",
            "trace-derived mapping",
            "original position order per (layer, KV head); native score-ranked gather order excluded",
            "P1 revalidated P0 then maps earlier keeps to append-only cold lists in original-position order.",
        ),
        _field(
            "protected_hot_suffix_mapping",
            "available",
            "trace-derived mapping",
            {"resident_window_tokens": p1_p64["resident_window"], "hot_slots": p1_p64["hot_slots"]},
            "P1 maps the P0 protected observation suffix to hot for this compatibility study; it is not a chosen hardware window.",
        ),
        _field(
            "static_packed_terminal_state",
            "available",
            "trace-derived mapping with declared accounting in P1",
            {
                "page_tokens_functional_probe": p3_state["page_tokens"],
                "cold_logical_kept_slots": p1_p64["cold_logical_kept_slots"],
                "cold_page_count": p1_p64["cold_page_count"],
            },
            "P1 static mapping and P3 P=64 state cross-check agree; this is not allocator or physical-capacity measurement.",
        ),
        _field(
            "same_mask_prefill_tail_semantics",
            "available",
            "functional with trace-derived terminal decisions",
            "all P3 layer/KV-head final-prefill probes passed their enforced FP32 same-mask guard",
            "P3 compares same-mask dense-cold and Route-A hot/pending/packed state without replacing model prefill attention.",
        ),
        _field(
            "online_decision_epochs_and_maturity_events",
            "unavailable",
            "not provided by the one-shot prefill source",
            None,
            "P0 exposes only prefill_terminal, so it contains no per-token epoch, maturity event time, or maturity ordering.",
        ),
        _field(
            "pending_arrival_service_and_occupancy",
            "unavailable",
            "not provided by the one-shot prefill source",
            None,
            "P3's terminal materialization has zero pending state; that is not evidence that a decode lifecycle has zero pending arrivals or occupancy.",
        ),
        _field(
            "generated_token_decision_and_decode_continuation",
            "unavailable",
            "not exercised",
            None,
            "P3 explicitly executes zero generated-token forwards because P0 supplies no action beyond context prefill.",
        ),
        _field(
            "native_snapkv_cache_replacement_semantics",
            "unavailable",
            "deliberately excluded",
            None,
            "P0/P3 leave native SnapKV score-ranked cache replacement unused; this is not native cache/decode validation.",
        ),
        _field(
            "source_ready_dispatch_completion_order",
            "unavailable",
            "not collected",
            None,
            "No source-ready, dispatch, arrival, completion, or overlap timestamps are present in a terminal prefill decision stream.",
        ),
        _field(
            "scheduler_backpressure_or_queue_state",
            "unavailable",
            "not collected",
            None,
            "No queue, service, contention, concurrency, or backpressure observation follows from the P0/P1/P3 evidence.",
        ),
        _field(
            "allocator_pool_or_physical_interface_fields",
            "unavailable",
            "not collected",
            None,
            "P1 declared accounting is not allocator behavior, and no pool/bank/burst/PTE/controller interface observation exists.",
        ),
        _field(
            "hardware_performance_or_cost_metrics",
            "unavailable",
            "not measured or modeled by P2",
            None,
            "P2 contains no traffic, cycles, latency, throughput, energy, area, or acceleration metric.",
        ),
    ]
    available = sum(row["status"] == "available" for row in fields)
    unavailable = len(fields) - available
    return {
        "field_statuses": fields,
        "summary": {
            "available_field_count": available,
            "unavailable_field_count": unavailable,
            "unavailable_values_are_not_zero": True,
            "source_lifecycle": "one-shot prefill terminal decision stream",
        },
        "eligibility": {
            "static_canonical_route_a_mapping": True,
            "bounded_prefill_same_mask_semantic_probe": True,
            "native_snapkv_cache_or_decode_semantics": False,
            "decode_lifecycle_or_pending_contract": False,
            "scheduler_or_backpressure_contract": False,
            "physical_resource_or_hardware_contract": False,
        },
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"P2 output directory already exists: {args.output_dir}")
    p0, decisions, p1, p3 = load_p2_inputs(args.p0_dir, args.p1_report, args.p3_dir)
    descriptor = build_descriptor(p0, decisions, p1, p3)
    report = {
        "schema_version": P2_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "execution_classification": "no-model provenance-backed lifecycle/resource field classification; not hardware modeled or measured evidence",
        "input_provenance": {
            "p0_manifest_path": str(args.p0_dir / P0_MANIFEST_NAME),
            "p0_manifest_sha256": sha256_file(args.p0_dir / P0_MANIFEST_NAME),
            "p0_terminal_stream_path": str(args.p0_dir / P0_STREAM_NAME),
            "p0_terminal_stream_sha256": sha256_file(args.p0_dir / P0_STREAM_NAME),
            "p1_report_path": str(args.p1_report),
            "p1_report_sha256": sha256_file(args.p1_report),
            "p3_manifest_path": str(args.p3_dir / P3_MANIFEST_NAME),
            "p3_manifest_sha256": sha256_file(args.p3_dir / P3_MANIFEST_NAME),
        },
        "source": {
            "request_id": p0["request_id"],
            "p0_decision_epoch": SNAPKV_TERMINAL_EPOCH,
            "p0_event_count": len(decisions),
            "p3_generated_token_forward_count": p3["config"]["generated_token_forward_count"],
        },
        "descriptor": descriptor,
        "source_sha256": {
            "p2_tool": sha256_file(Path(__file__)),
            "p1_tool": sha256_file(Path("tools/analyze_snapkv_route_a_p1_packed_opportunity.py")),
            "p3_tool": sha256_file(Path("tools/run_snapkv_route_a_p3_semantic_gate.py")),
            "frontend_contract": sha256_file(Path("kvpress/route_a_frontend_contract.py")),
        },
        "boundaries": [
            "P2 consumes completed P0/P1/P3 evidence only and performs no model execution, native SnapKV cache replacement, trace creation, or modification of its inputs.",
            "A field marked unavailable means the source did not provide or P0/P1/P3 did not exercise that evidence. It is not a zero-valued lifecycle, queue, traffic, or hardware quantity.",
            "P2 permits only static canonical mapping and bounded prefill same-mask semantic claims for this fixed source. It does not authorize native SnapKV decode, generated-token continuation, scheduler/backpressure, allocator, physical-interface, traffic, cycles, latency, throughput, energy, area, hardware specification, or RTL conclusions.",
            "P2 selects no FIFO depth, PTE width, bank/burst, merge precision, PE count, scheduler, controller timing, or other hardware parameter.",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / P2_REPORT_NAME).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"SnapKV P2 lifecycle/resource descriptor completed: {args.output_dir}")


if __name__ == "__main__":
    main()
