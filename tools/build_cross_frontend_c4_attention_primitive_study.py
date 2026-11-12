#!/usr/bin/env python3
"""Build C4 comparator-bound source-traversal reports from completed evidence.

C4 does not execute model attention.  It revalidates the already accepted,
frontend-specific functional comparators and records the narrow traversal
contract each comparator supports.  The resulting common primitive is an
abstraction for later study, not a shared cache format, source ordering rule,
or hardware interface.
"""
from __future__ import annotations

from kvpress.research.cross_frontend import snap_field_rows, build_kvzap, build_snap, build_dms, validate_reports

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


C2_SCHEMA = "cross-frontend-c2-realization-adapters-1.0"
C3_SCHEMA = "cross-frontend-c3-commonality-matrix-1.0"
C4_SCHEMA = "cross-frontend-c4-attention-primitive-study-1.0"
QWEN_SCHEMA = "kvzap-route-a4214-core-contract-closure-1.0"
SNAP_SCHEMA = "route-a-snapkv-p2-lifecycle-resource-descriptor-1.0"
DMS_SCHEMA = "route-a-dms-m4-active-resident-attention-gate-1.0"
UNRESOLVED_REQUIRED = {
    "literal_dms_original_position",
    "snapkv_generated_decode_and_online_lifecycle",
    "shared_physical_or_temporal_resource_contract",
    "universal_multi_source_composition",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="C4 no-model comparator-bound attention primitive study: recheck accepted traversal evidence for KVzap, SnapKV, and DMS.")
    parser.add_argument("--c2-report", type=Path, required=True)
    parser.add_argument("--c3-report", type=Path, required=True)
    parser.add_argument("--qwen-core-contract", type=Path, required=True)
    parser.add_argument("--snapkv-terminal-prefill", type=Path, required=True)
    parser.add_argument("--official-dms-active-resident", type=Path, required=True)
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


def load_complete(path: Path, *, schema: str, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"C4 required {label} is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != schema or value.get("status") != "complete":
        raise ValueError(f"C4 required {label} completed schema {schema}, got {value.get('schema_version')!r}/{value.get('status')!r}")
    return value


def require_c3_binding(c2_path: Path, c2: dict[str, Any], c3: dict[str, Any]) -> None:
    c2_binding = c3.get("c2_binding")
    if not isinstance(c2_binding, dict) or c2_binding.get("sha256") != sha256_file(c2_path):
        raise ValueError("C4 C3 report does not bind the supplied C2 report")
    gate = c3.get("c3_gate")
    required = ("c2_hash_and_required_guards_verified", "exactly_three_frontend_projections_compared", "invariants_have_all_observed_prerequisites", "dms_literal_position_remains_unresolved", "snapkv_generated_decode_remains_unresolved")
    if not isinstance(gate, dict) or not all(gate.get(name) is True for name in required):
        raise ValueError("C4 requires accepted C3 commonality guards")
    names = {row.get("name") for row in c3.get("unresolved_boundaries", []) if isinstance(row, dict)}
    if not UNRESOLVED_REQUIRED.issubset(names):
        raise ValueError("C4 must retain all C3 unresolved boundaries")
    if c2.get("c2_gate", {}).get("all_core_statuses_preserved_from_c1") is not True:
        raise ValueError("C4 requires C2 status-preservation gate")


def verify_c2_source(c2: dict[str, Any], label: str, path: Path) -> dict[str, Any]:
    record = c2.get("source_bindings", {}).get(label)
    if not isinstance(record, dict) or record.get("sha256") != sha256_file(path):
        raise ValueError(f"C4 source differs from C2 binding for {label}")
    return record












def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"C4 output directory already exists: {args.output_dir}")
    c2 = load_complete(args.c2_report, schema=C2_SCHEMA, label="C2 report")
    c3 = load_complete(args.c3_report, schema=C3_SCHEMA, label="C3 report")
    qwen = load_complete(args.qwen_core_contract, schema=QWEN_SCHEMA, label="KVzap core")
    snap = load_complete(args.snapkv_terminal_prefill, schema=SNAP_SCHEMA, label="SnapKV P2")
    dms = load_complete(args.official_dms_active_resident, schema=DMS_SCHEMA, label="DMS M4")
    require_c3_binding(args.c2_report, c2, c3)
    source_bindings = {
        "kvzap_qwen_core_contract": verify_c2_source(c2, "kvzap_qwen_core_contract", args.qwen_core_contract),
        "snapkv_terminal_prefill": verify_c2_source(c2, "snapkv_terminal_prefill", args.snapkv_terminal_prefill),
        "official_dms_active_resident": verify_c2_source(c2, "official_dms_active_resident", args.official_dms_active_resident),
    }
    reports = {
        "kvzap_route_a_persistent_packed": build_kvzap(qwen),
        "snapkv_one_shot_packed": build_snap(snap),
        "official_dms_dynamic_resident_slot": build_dms(dms),
    }
    validate_reports(reports, c3)
    comparison = {
        "candidate_common_primitive": "frontend-bound ordered variable-length source traversal under each frontend's accepted semantic comparator",
        "supported_by_all_three": "A single ordered source is sufficient for the bounded SnapKV and DMS evidence; KVzap additionally permits optional hot/pending/packed composition.",
        "not_established": ["a common cache format", "a common source order", "mandatory multi-source composition", "source splitting/merge placement outside KVzap", "scheduler/backpressure/temporal resource contract", "allocator/capacity/traffic/timing/hardware interface"],
    }
    config = {"c2_report": str(args.c2_report), "c3_report": str(args.c3_report), "qwen_core_contract": str(args.qwen_core_contract), "snapkv_terminal_prefill": str(args.snapkv_terminal_prefill), "official_dms_active_resident": str(args.official_dms_active_resident)}
    report = {
        "schema_version": C4_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model revalidation of prior trace-derived/functional comparator evidence; not a new attention execution, measurement, or modeled hardware study",
        "c2_binding": {"path": str(args.c2_report), "sha256": sha256_file(args.c2_report), "schema_version": C2_SCHEMA},
        "c3_binding": {"path": str(args.c3_report), "sha256": sha256_file(args.c3_report), "schema_version": C3_SCHEMA},
        "source_bindings": source_bindings,
        "per_frontend_source_traversal_reports": reports,
        "comparison_summary": comparison,
        "c4_gate": {"c2_c3_and_source_hashes_reverified": True, "three_frontend_comparators_rechecked": True, "every_frontend_has_declared_source_cardinality_and_order": True, "no_mandatory_multi_source_requirement": True, "dms_native_order_restriction_preserved": True, "c3_unresolved_boundaries_retained": True, "raw_traces_or_tensor_payloads_opened": False, "model_or_runtime_loaded": False, "new_attention_execution_performed": False, "resource_or_hardware_interface_selected": False},
        "boundaries": ["C4 rechecks completed comparator evidence and does not rerun model attention or create a new functional measurement.", "The common primitive is semantic and frontend-bound: it does not specify one cache format, physical source layout, or reorderable source order.", "KVzap optional multi-source composition is not imposed on SnapKV or DMS.", "SnapKV generated decode and native decode semantics remain unobserved; DMS literal original position remains unobserved.", "No allocator, capacity, traffic, latency, throughput, energy, area, acceleration, architecture, parameter-selection, or RTL conclusion follows."],
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "cross_frontend_c4_attention_primitive_study_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"C4 cross-frontend attention primitive study passed: {output}")


if __name__ == "__main__":
    main()
