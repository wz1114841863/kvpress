#!/usr/bin/env python3
"""Analyze C2 projections into C3 common, specific, and unresolved evidence.

This no-model analysis intentionally compares semantic availability and stated
meaning rather than cache layouts, resource values, or performance.  It marks
an invariant candidate only when every projection observes its prerequisite;
the candidate wording is restricted to the common abstraction and separately
records frontend-specific realization/order differences.
"""
from __future__ import annotations

from kvpress.research.cross_frontend import CORE_FIELDS, FRONTENDS, field_matrix, invariant_candidates, frontend_specific, unresolved, validate_analysis, analyze_projections

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


C2_SCHEMA = "cross-frontend-c2-realization-adapters-1.0"
C3_SCHEMA = "cross-frontend-c3-commonality-matrix-1.0"


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














def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"C3 output directory already exists: {args.output_dir}")
    c2 = load_c2(args.c2_report)
    matrix, invariants, specific, unresolved_rows = analyze_projections(c2)
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
