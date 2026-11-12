#!/usr/bin/env python3
"""Build the no-model C1 cross-frontend semantic descriptor contract.

C1 turns only C0-bound completed manifests into a typed availability matrix. It
does not read raw trace/tensor payloads, load a model, or create a shared cache
or hardware interface.
"""
from __future__ import annotations

from kvpress.research.cross_frontend import VALUE_STATUSES, CORE_FIELD_TYPES, REALIZATION_EXTENSIONS, field, availability_matrix, validate_matrix

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

C1_SCHEMA = "cross-frontend-c1-semantic-descriptor-1.0"
C0_SCHEMA = "cross-frontend-c0-evidence-index-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="C1 no-model semantic descriptor: verify C0 hash bindings and write a typed cross-frontend field-availability matrix.")
    parser.add_argument("--c0-report", type=Path, required=True, help="Completed C0 hash-bound evidence index.")
    parser.add_argument("--qwen-core-contract", type=Path, required=True)
    parser.add_argument("--qwen-llama-coverage", type=Path, required=True)
    parser.add_argument("--snapkv-terminal-prefill", type=Path, required=True)
    parser.add_argument("--official-dms-active-resident", type=Path, required=True)
    parser.add_argument("--allow-relocated-c0-sources", action="store_true", help="Allow a fresh staging path only when its manifest SHA-256 still equals the C0-bound source; record both paths.")
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


def load_complete(path: Path, *, expected_schema: str, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"C1 required {label} input is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != expected_schema or value.get("status") != "complete":
        raise ValueError(f"C1 required {label} completed schema {expected_schema}, got {value.get('schema_version')!r}/{value.get('status')!r}")
    return value


def require_c0_bindings(c0: dict[str, Any], sources: dict[str, Path], *, allow_relocated_sources: bool = False) -> dict[str, dict[str, str | bool]]:
    gate = c0.get("c0_gate")
    required = ("all_four_completed_sources_hash_bound", "archive_path_and_hash_bindings_verified", "required_semantic_and_claim_boundary_guards_verified")
    if not isinstance(gate, dict) or not all(gate.get(name) is True for name in required):
        raise ValueError("C1 requires the completed C0 hash/claim-boundary gate")
    records = c0.get("completed_artifacts")
    if not isinstance(records, dict):
        raise ValueError("C1 C0 report lacks completed_artifacts")
    bound: dict[str, dict[str, str | bool]] = {}
    for label, path in sources.items():
        record = records.get(label)
        if not isinstance(record, dict):
            raise ValueError(f"C1 C0 report lacks {label} binding")
        actual_hash = sha256_file(path)
        if record.get("sha256") != actual_hash:
            raise ValueError(f"C1 source differs from C0 binding for {label}")
        relocated = record.get("path") != str(path)
        if relocated and not allow_relocated_sources:
            raise ValueError(f"C1 source path differs from C0 binding for {label}; use an exact C0-bound path or explicit hash-preserving relocation")
        bound[label] = {"c0_bound_path": str(record.get("path")), "input_path": str(path), "sha256": actual_hash, "schema_version": str(record.get("schema_version")), "hash_preserving_relocation": relocated}
    return bound








def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"C1 output directory already exists: {args.output_dir}")
    sources = {"kvzap_qwen_core_contract": args.qwen_core_contract, "kvzap_qwen_llama_coverage": args.qwen_llama_coverage, "snapkv_terminal_prefill": args.snapkv_terminal_prefill, "official_dms_active_resident": args.official_dms_active_resident}
    c0 = load_complete(args.c0_report, expected_schema=C0_SCHEMA, label="C0 report")
    for label, path in sources.items():
        expected = c0["completed_artifacts"].get(label, {}).get("schema_version")
        load_complete(path, expected_schema=expected, label=label)
    bindings = require_c0_bindings(c0, sources, allow_relocated_sources=args.allow_relocated_c0_sources)
    matrix = availability_matrix()
    validate_matrix(matrix)
    config = {"c0_report": str(args.c0_report), **{label: str(path) for label, path in sources.items()}}
    report = {
        "schema_version": C1_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": git_commit(), "config": config, "config_hash": stable_hash(config),
        "execution_classification": "no-model typed availability contract over C0-bound completed trace-derived/functional artifacts; not measured or modeled hardware evidence",
        "c0_binding": {"path": str(args.c0_report), "sha256": sha256_file(args.c0_report), "schema_version": C0_SCHEMA}, "source_bindings": bindings,
        "descriptor_specification": {"name": "CrossFrontendResidencyDescriptor", "version": "v1", "logic_grain": "(model, layer, kv_head, epoch)", "allowed_value_statuses": sorted(VALUE_STATUSES), "core_fields": CORE_FIELD_TYPES, "realization_extensions": REALIZATION_EXTENSIONS, "non_core_examples": ["pending", "page_descriptor", "free_slot_list", "native_cache_block_table"]},
        "frontend_field_availability": matrix,
        "c1_gate": {"c0_hash_bound_sources_reverified": True, "c0_bound_source_paths_reused_or_hash_preserving_relocation_recorded": True, "every_core_field_typed_for_every_frontend": True, "unknown_and_not_applicable_values_have_reasons": True, "extension_only_state_not_promoted_to_core": True, "raw_traces_or_tensor_payloads_opened": False, "model_or_runtime_loaded": False, "hardware_interface_or_parameter_selected": False},
        "boundaries": ["C1 is an availability/typing contract, not a shared cache format, hardware interface, resource envelope, architecture specification, or RTL gate.", "A relocated source is accepted only under the explicit flag and only if its SHA-256 equals C0; both the C0-bound origin and actual input path are recorded.", "KVzap, SnapKV, and DMS keep their own accepted semantic comparators; C1 creates no common oracle.", "SnapKV generated-token/decode behavior remains unknown, not zero or not_applicable.", "DMS source arrival serial remains distinct from an unobserved literal original token position and from its required native traversal order.", "Model topology is model-scoped and must not be pooled into accelerator dimensions."],
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "cross_frontend_c1_semantic_descriptor_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"C1 cross-frontend semantic descriptor passed: {output}")


if __name__ == "__main__":
    main()
