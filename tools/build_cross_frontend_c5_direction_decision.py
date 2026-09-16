#!/usr/bin/env python3
"""Create the C5 evidence-bound Route-A direction decision memo.

C5 is a no-model archival decision.  It does not select a hardware parameter,
architecture specification, or RTL target.  It verifies the C0--C4 hash chain
and decides only whether the evidence supports keeping KVzap Route-A
persistent-packed as the research primary, versus promoting a common hardware
substrate.  The latter requires evidence that C0--C4 explicitly do not supply.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMAS = {
    "c0": "cross-frontend-c0-evidence-index-1.0",
    "c1": "cross-frontend-c1-semantic-descriptor-1.0",
    "c2": "cross-frontend-c2-realization-adapters-1.0",
    "c3": "cross-frontend-c3-commonality-matrix-1.0",
    "c4": "cross-frontend-c4-attention-primitive-study-1.0",
}
C5_SCHEMA = "cross-frontend-c5-hardware-direction-decision-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="C5 no-model direction decision: verify C0-C4 provenance and archive the Route-A primary-path decision without selecting hardware parameters.")
    parser.add_argument("--c0-report", type=Path, required=True)
    parser.add_argument("--c1-report", type=Path, required=True)
    parser.add_argument("--c2-report", type=Path, required=True)
    parser.add_argument("--c3-report", type=Path, required=True)
    parser.add_argument("--c4-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def git_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], check=False, capture_output=True, text=True)
    return result.stdout.strip() or "unknown"


def load_complete(path: Path, *, stage: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"C5 {stage} report is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMAS[stage] or value.get("status") != "complete":
        raise ValueError(f"C5 requires completed {stage} schema {SCHEMAS[stage]}")
    return value


def require_binding(report: dict[str, Any], key: str, path: Path, label: str) -> None:
    binding = report.get(key)
    if not isinstance(binding, dict) or binding.get("sha256") != sha256_file(path):
        raise ValueError(f"C5 {label} hash binding is absent or mismatched")


def verify_chain(paths: dict[str, Path], reports: dict[str, dict[str, Any]]) -> dict[str, str]:
    c0_gate = reports["c0"].get("c0_gate", {})
    if not all(c0_gate.get(name) is True for name in ("all_four_completed_sources_hash_bound", "archive_path_and_hash_bindings_verified", "required_semantic_and_claim_boundary_guards_verified")):
        raise ValueError("C5 C0 provenance gate failed")
    require_binding(reports["c1"], "c0_binding", paths["c0"], "C1->C0")
    require_binding(reports["c2"], "c1_binding", paths["c1"], "C2->C1")
    require_binding(reports["c3"], "c2_binding", paths["c2"], "C3->C2")
    require_binding(reports["c4"], "c2_binding", paths["c2"], "C4->C2")
    require_binding(reports["c4"], "c3_binding", paths["c3"], "C4->C3")
    c4_gate = reports["c4"].get("c4_gate", {})
    if not all(c4_gate.get(name) is True for name in ("c2_c3_and_source_hashes_reverified", "three_frontend_comparators_rechecked", "no_mandatory_multi_source_requirement", "dms_native_order_restriction_preserved", "c3_unresolved_boundaries_retained")):
        raise ValueError("C5 C4 comparator/commonality gate failed")
    return {stage: sha256_file(path) for stage, path in paths.items()}


def decide(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    c3 = reports["c3"]
    c4 = reports["c4"]
    specific = {row.get("frontend") for row in c3.get("frontend_specific_mechanisms", []) if isinstance(row, dict)}
    unresolved = {row.get("name") for row in c3.get("unresolved_boundaries", []) if isinstance(row, dict)}
    expected_specific = {"kvzap_route_a_persistent_packed", "snapkv_one_shot_packed", "official_dms_dynamic_resident_slot"}
    expected_unresolved = {"literal_dms_original_position", "snapkv_generated_decode_and_online_lifecycle", "shared_physical_or_temporal_resource_contract", "universal_multi_source_composition"}
    if specific != expected_specific or not expected_unresolved.issubset(unresolved):
        raise ValueError("C5 C3 classification boundary is incomplete")
    summary = c4.get("comparison_summary")
    if not isinstance(summary, dict) or summary.get("candidate_common_primitive") != "frontend-bound ordered variable-length source traversal under each frontend's accepted semantic comparator":
        raise ValueError("C5 C4 candidate common primitive drifted")
    not_established = set(summary.get("not_established", []))
    required_not_established = {"a common cache format", "a common source order", "mandatory multi-source composition", "scheduler/backpressure/temporal resource contract", "allocator/capacity/traffic/timing/hardware interface"}
    if not required_not_established.issubset(not_established):
        raise ValueError("C5 cannot promote a common substrate while C4 boundaries are incomplete")
    return {
        "primary_direction": "route_a_persistent_packed_backend",
        "decision": "retain_as_primary_research_and_architecture_path",
        "decision_basis": [
            "KVzap retains a distinct persistent-packed lifecycle: stable decision, hot window, maturity, pending staging, append-only packed cold state, and optional online-softmax composition.",
            "C3/C4 find only a frontend-bound semantic traversal abstraction, not a common cache format, source order, or mandatory multi-source realization.",
            "SnapKV and DMS are valuable boundary/workload evidence but their observed realizations remain one-shot prefill and dynamic resident-slot respectively.",
        ],
        "candidate_common_substrate": {
            "status": "semantic_abstraction_only_not_selected_as_hardware_direction",
            "abstraction": summary["candidate_common_primitive"],
            "reason": "The three frontends retain incompatible lifecycle/order/comparator details and unresolved physical/temporal contract fields.",
        },
        "cross_frontend_role": {
            "kvzap": "primary backend and architecture differentiation target",
            "snapkv": "one-shot-prefill semantic boundary and future workload-envelope contrast; not a decode lifecycle proof",
            "official_dms": "dynamic-resident decode boundary and native-order preservation contrast; not a packed-cold mapping",
        },
    }


def pre_rtl_checklist() -> list[dict[str, Any]]:
    return [
        {
            "name": "route_a_resource_contract_freeze",
            "required_before_architecture_spec": True,
            "status": "not_selected",
            "need": "Choose FIFO/PTE/page/bank/burst/merge precision/PE/scheduler/controller parameters only from a separately documented Route-A resource study.",
        },
        {
            "name": "route_a_workload_envelope_and_fallback",
            "required_before_architecture_spec": True,
            "status": "partial_existing_evidence_not_final",
            "need": "Keep Qwen/Llama descriptor rows separate, preserve Full-KV bypass, and establish the intended Route-A workload envelope without pooling fixed-request counts into hardware dimensions.",
        },
        {
            "name": "new_frontend_onboarding_rule",
            "required_before_architecture_spec": False,
            "status": "semantic_preconditions_defined",
            "need": "A future frontend must expose a stable decision/active-state semantics, explicit identity/order, and an accepted comparator; otherwise it remains a boundary case rather than a Route-A mapping.",
        },
        {
            "name": "unresolved_cross_frontend_fields",
            "required_before_architecture_spec": False,
            "status": "explicitly_retained",
            "need": "Do not fill SnapKV generated decode, DMS literal position, or common scheduler/backpressure fields merely to create a universal interface.",
        },
        {
            "name": "rtl_authorization",
            "required_before_architecture_spec": True,
            "status": "not_authorized",
            "need": "C5 is a research-direction memo only. A separate architecture-spec gate must freeze parameters and evidence boundaries before RTL.",
        },
    ]


def validate_decision(decision: dict[str, Any], checklist: list[dict[str, Any]]) -> None:
    if decision.get("primary_direction") != "route_a_persistent_packed_backend":
        raise ValueError("C5 only accepts the evidence-supported Route-A primary direction")
    common = decision.get("candidate_common_substrate", {})
    if common.get("status") != "semantic_abstraction_only_not_selected_as_hardware_direction":
        raise ValueError("C5 must not promote a common semantic abstraction into a hardware direction")
    rtl = [row for row in checklist if row.get("name") == "rtl_authorization"]
    if len(rtl) != 1 or rtl[0].get("status") != "not_authorized":
        raise ValueError("C5 must retain the pre-RTL gate")


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"C5 output directory already exists: {args.output_dir}")
    paths = {"c0": args.c0_report, "c1": args.c1_report, "c2": args.c2_report, "c3": args.c3_report, "c4": args.c4_report}
    reports = {stage: load_complete(path, stage=stage) for stage, path in paths.items()}
    hashes = verify_chain(paths, reports)
    decision = decide(reports)
    checklist = pre_rtl_checklist()
    validate_decision(decision, checklist)
    config = {stage + "_report": str(path) for stage, path in paths.items()}
    report = {
        "schema_version": C5_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model archival direction decision over C0-C4 trace-derived/functional provenance; not a measured or modeled hardware result",
        "c0_c4_bindings": {stage: {"path": str(path), "sha256": hashes[stage], "schema_version": SCHEMAS[stage]} for stage, path in paths.items()},
        "direction_decision": decision,
        "pre_rtl_checklist": checklist,
        "c5_gate": {"c0_c4_hash_chain_verified": True, "route_a_primary_direction_evidence_bound": True, "common_substrate_not_promoted_to_hardware_direction": True, "frontend_specific_boundaries_retained": True, "unresolved_cross_frontend_fields_retained": True, "hardware_parameter_selected": False, "architecture_spec_frozen": False, "rtl_authorized": False, "model_or_runtime_loaded": False},
        "boundaries": ["C5 selects only the research primary direction; it does not select a hardware configuration, architecture specification, or RTL target.", "The common substrate remains a semantic abstraction with frontend-specific comparator/order constraints, not a unified cache implementation.", "Route-A persistent-packed remains a hypothesis requiring its own separately frozen resource contract and workload-envelope evidence before architecture specification.", "SnapKV and DMS remain bounded portability/workload evidence; they neither prove a universal Route-A mapping nor need identical distributions."],
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "cross_frontend_c5_hardware_direction_decision_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"C5 cross-frontend direction decision passed: {output}")


if __name__ == "__main__":
    main()
