#!/usr/bin/env python3
"""Analyze C2 projections into C3 common, specific, and unresolved evidence.

This no-model analysis intentionally compares semantic availability and stated
meaning rather than cache layouts, resource values, or performance.  It marks
an invariant candidate only when every projection observes its prerequisite;
the candidate wording is restricted to the common abstraction and separately
records frontend-specific realization/order differences.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


C2_SCHEMA = "cross-frontend-c2-realization-adapters-1.0"
C3_SCHEMA = "cross-frontend-c3-commonality-matrix-1.0"
CORE_FIELDS = (
    "model_topology",
    "identity",
    "epoch",
    "decision",
    "visibility",
    "position_provenance",
    "traversal_order",
    "attention_binding",
)
FRONTENDS = (
    "kvzap_route_a_persistent_packed",
    "snapkv_one_shot_packed",
    "official_dms_dynamic_resident_slot",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="C3 no-model commonality analysis: classify C2 semantic projections as invariant candidates, frontend-specific fields, or unresolved boundaries.")
    parser.add_argument("--c2-report", type=Path, required=True)
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


def load_c2(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"C3 C2 report is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != C2_SCHEMA or value.get("status") != "complete":
        raise ValueError("C3 requires a completed C2 realization-adapters report")
    gate = value.get("c2_gate")
    required = ("c1_and_all_source_hashes_reverified", "three_frontend_specific_projections_written", "all_core_statuses_preserved_from_c1", "unknown_or_not_applicable_fields_remain_unfabricated")
    if not isinstance(gate, dict) or not all(gate.get(name) is True for name in required):
        raise ValueError("C3 requires all C2 semantic/provenance guards")
    return value


def field_matrix(c2: dict[str, Any]) -> dict[str, dict[str, Any]]:
    projections = c2.get("projections")
    if not isinstance(projections, dict) or set(projections) != set(FRONTENDS):
        raise ValueError("C3 requires exactly three C2 frontend projections")
    rows: dict[str, dict[str, Any]] = {}
    for field_name in CORE_FIELDS:
        cells: dict[str, Any] = {}
        for frontend in FRONTENDS:
            projection = projections[frontend]
            core = projection.get("core_fields") if isinstance(projection, dict) else None
            item = core.get(field_name) if isinstance(core, dict) else None
            if not isinstance(item, dict) or item.get("status") not in {"observed", "derived", "modeled", "unknown", "not_applicable"}:
                raise ValueError(f"C3 missing typed C2 field {frontend}.{field_name}")
            cells[frontend] = {"status": item["status"], "reason": item.get("reason"), "value": item.get("value")}
        statuses = {name: item["status"] for name, item in cells.items()}
        rows[field_name] = {
            "per_frontend": cells,
            "all_observed": all(status == "observed" for status in statuses.values()),
            "all_available": all(status in {"observed", "derived"} for status in statuses.values()),
            "statuses": statuses,
        }
    return rows


def invariant_candidates(matrix: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        {
            "name": "explicit_source_record_identity",
            "required_fields": ["identity"],
            "common_abstraction": "Every evaluated frontend exposes an explicit source_record_id associated with layer and KV head.",
            "non_invariant_detail": "KVzap/SnapKV use original logical positions; DMS uses an arrival serial, not a literal position.",
        },
        {
            "name": "explicit_epoch_and_decision_scope",
            "required_fields": ["epoch", "decision"],
            "common_abstraction": "Every evaluated frontend binds its retained/active control semantics to an explicit scope or epoch.",
            "non_invariant_detail": "KVzap has lifecycle/maturity, SnapKV only terminal prefill, and DMS a fixed decode controller contract; no common online timeline is inferred.",
        },
        {
            "name": "required_frontend_specific_traversal_order",
            "required_fields": ["traversal_order"],
            "common_abstraction": "Attention realization must preserve the frontend-specified source traversal order.",
            "non_invariant_detail": "This does not define one canonical order: DMS native slot/block order cannot be replaced by arrival order.",
        },
        {
            "name": "frontend_bound_semantic_comparator",
            "required_fields": ["attention_binding"],
            "common_abstraction": "Each frontend requires an explicit accepted semantic comparator for any later attention study.",
            "non_invariant_detail": "Comparators are distinct: KVzap same-mask dense, SnapKV prefill-tail, and DMS native FlashAttention replay.",
        },
    ]
    accepted: list[dict[str, Any]] = []
    for candidate in candidates:
        if all(matrix[field]["all_observed"] for field in candidate["required_fields"]):
            accepted.append(candidate)
    return accepted


def frontend_specific(c2: dict[str, Any]) -> list[dict[str, Any]]:
    projections = c2["projections"]
    return [
        {
            "frontend": "kvzap_route_a_persistent_packed",
            "realization_extension": projections["kvzap_route_a_persistent_packed"]["realization_extension"],
            "specific_mechanisms": ["hot/pending/packed lifecycle", "maturity and admission", "optional multi-source partial composition with one online-softmax merge"],
            "boundary": "These are KVzap Route-A realization mechanisms, not common C3 interface fields.",
        },
        {
            "frontend": "snapkv_one_shot_packed",
            "realization_extension": projections["snapkv_one_shot_packed"]["realization_extension"],
            "specific_mechanisms": ["terminal prefill action", "protected observation suffix compatibility mapping", "canonical static original-position packing"],
            "boundary": "No generated decode, online maturity, or native decode/cache semantics are observed.",
        },
        {
            "frontend": "official_dms_dynamic_resident_slot",
            "realization_extension": projections["official_dms_dynamic_resident_slot"]["realization_extension"],
            "specific_mechanisms": ["dynamic active slots", "delayed eviction/reuse", "required native logical-slot/block-table traversal"],
            "boundary": "DMS is not asserted to be a packed-cold source and its native order is not an order-invariance result.",
        },
    ]


def unresolved(matrix: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    unresolved_rows = [
        {
            "name": "literal_dms_original_position",
            "affected_field": "position_provenance",
            "reason": matrix["position_provenance"]["per_frontend"]["official_dms_dynamic_resident_slot"]["reason"],
        },
        {
            "name": "snapkv_generated_decode_and_online_lifecycle",
            "affected_fields": ["epoch", "decision", "visibility", "attention_binding"],
            "reason": "C2 retains terminal-prefill scope only; generated decode, maturity timing, native decode visibility, and native decode comparator remain unknown.",
        },
        {
            "name": "shared_physical_or_temporal_resource_contract",
            "affected_fields": ["all"],
            "reason": "No common source-ready/completion order, queue/backpressure, allocator, capacity, traffic, timing, or hardware interface is established by C0-C3.",
        },
        {
            "name": "universal_multi_source_composition",
            "affected_fields": ["visibility", "traversal_order"],
            "reason": "KVzap has accepted hot/pending/packed composition; SnapKV and DMS must not be artificially partitioned into sources.",
        },
    ]
    return unresolved_rows


def validate_analysis(matrix: dict[str, dict[str, Any]], invariants: list[dict[str, Any]], unresolved_rows: list[dict[str, Any]]) -> None:
    for candidate in invariants:
        if not all(matrix[field]["all_observed"] for field in candidate["required_fields"]):
            raise ValueError(f"C3 invariant {candidate['name']} lacks all-observed prerequisite")
    if matrix["position_provenance"]["all_observed"]:
        raise ValueError("C3 must not erase the DMS position-provenance unknown")
    if not any(row["name"] == "snapkv_generated_decode_and_online_lifecycle" for row in unresolved_rows):
        raise ValueError("C3 must retain SnapKV decode/lifecycle as unresolved")


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"C3 output directory already exists: {args.output_dir}")
    c2 = load_c2(args.c2_report)
    matrix = field_matrix(c2)
    invariants = invariant_candidates(matrix)
    specific = frontend_specific(c2)
    unresolved_rows = unresolved(matrix)
    validate_analysis(matrix, invariants, unresolved_rows)
    config = {"c2_report": str(args.c2_report)}
    report = {
        "schema_version": C3_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model semantic commonality classification over a completed C2 projection; not trace collection, measurement, or modeled hardware evidence",
        "c2_binding": {"path": str(args.c2_report), "sha256": sha256_file(args.c2_report), "schema_version": C2_SCHEMA},
        "core_field_matrix": matrix,
        "invariant_candidates": invariants,
        "frontend_specific_mechanisms": specific,
        "unresolved_boundaries": unresolved_rows,
        "c3_gate": {"c2_hash_and_required_guards_verified": True, "exactly_three_frontend_projections_compared": True, "invariants_have_all_observed_prerequisites": True, "frontend_specific_mechanisms_remain_explicit": True, "dms_literal_position_remains_unresolved": True, "snapkv_generated_decode_remains_unresolved": True, "raw_traces_or_tensor_payloads_opened": False, "model_or_runtime_loaded": False, "resource_or_hardware_interface_selected": False},
        "boundaries": ["C3 classifies semantic commonality only; an invariant candidate is not a common cache format, common source order, or hardware interface.", "Model topology values are not pooled; C3 does not create a cross-model resource envelope.", "An explicit source identity does not make DMS arrival serial an original token position.", "An explicit traversal requirement does not authorize reordering DMS native slots or splitting SnapKV/DMS into artificial sources.", "No capacity, allocator, traffic, latency, throughput, energy, area, acceleration, architecture, parameter-selection, or RTL conclusion follows."],
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "cross_frontend_c3_commonality_matrix_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"C3 cross-frontend commonality analysis passed: {output}")


if __name__ == "__main__":
    main()
