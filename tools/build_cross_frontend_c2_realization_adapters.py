#!/usr/bin/env python3
"""Build C2 provenance-preserving realization adapters from the C1 contract.

This no-model tool creates three frontend-specific semantic projections.  It
does not normalize their cache formats, infer missing decode state, allocate
storage, or select a hardware interface.  A projection is valid only when its
source manifests still match the SHA-256 hashes bound by C1 and every core
field retains the C1 availability status.
"""
from __future__ import annotations

from kvpress.research.cross_frontend import projected_field, c1_status, require_qwen_shape, snap_statuses, require_dms_shape, build_kvzap_projection, build_snap_projection, build_dms_projection, validate_projection

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


C1_SCHEMA = "cross-frontend-c1-semantic-descriptor-1.0"
C2_SCHEMA = "cross-frontend-c2-realization-adapters-1.0"
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
FRONTENDS = {
    "kvzap_route_a_persistent_packed": "kvzap_qwen_core_contract",
    "snapkv_one_shot_packed": "snapkv_terminal_prefill",
    "official_dms_dynamic_resident_slot": "official_dms_active_resident",
}
SOURCE_SCHEMAS = {
    "kvzap_qwen_core_contract": "kvzap-route-a4214-core-contract-closure-1.0",
    "kvzap_qwen_llama_coverage": "kvzap-route-a-m6-cross-model-fixed-horizon-envelope-1.2",
    "snapkv_terminal_prefill": "route-a-snapkv-p2-lifecycle-resource-descriptor-1.0",
    "official_dms_active_resident": "route-a-dms-m4-active-resident-attention-gate-1.0",
}
VALUE_STATUSES = frozenset({"observed", "derived", "modeled", "unknown", "not_applicable"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="C2 no-model realization adapters: verify C1/source provenance, then write three frontend-specific semantic projections.")
    parser.add_argument("--c1-report", type=Path, required=True)
    parser.add_argument("--qwen-core-contract", type=Path, required=True)
    parser.add_argument("--qwen-llama-coverage", type=Path, required=True)
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
        raise FileNotFoundError(f"C2 required {label} is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != schema or value.get("status") != "complete":
        raise ValueError(f"C2 required {label} completed schema {schema}, got {value.get('schema_version')!r}/{value.get('status')!r}")
    return value


def c1_source_hash(record: dict[str, Any]) -> str | None:
    return record.get("sha256") if isinstance(record.get("sha256"), str) else None


def verify_c1_bindings(c1: dict[str, Any], sources: dict[str, Path]) -> dict[str, dict[str, str]]:
    gate = c1.get("c1_gate")
    if not isinstance(gate, dict) or gate.get("c0_hash_bound_sources_reverified") is not True:
        raise ValueError("C2 requires a C1 report that reverified C0-bound sources")
    records = c1.get("source_bindings")
    if not isinstance(records, dict):
        raise ValueError("C2 C1 report lacks source_bindings")
    verified: dict[str, dict[str, str]] = {}
    for label, path in sources.items():
        record = records.get(label)
        expected = c1_source_hash(record) if isinstance(record, dict) else None
        actual = sha256_file(path)
        if expected != actual:
            raise ValueError(f"C2 source differs from C1 binding for {label}")
        verified[label] = {
            "c1_bound_path": str(record.get("c0_bound_path", record.get("path"))),
            "input_path": str(path),
            "sha256": actual,
            "schema_version": str(record.get("schema_version")),
        }
    return verified




















def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"C2 output directory already exists: {args.output_dir}")
    c1 = load_complete(args.c1_report, schema=C1_SCHEMA, label="C1 report")
    sources = {"kvzap_qwen_core_contract": args.qwen_core_contract, "kvzap_qwen_llama_coverage": args.qwen_llama_coverage, "snapkv_terminal_prefill": args.snapkv_terminal_prefill, "official_dms_active_resident": args.official_dms_active_resident}
    source_reports = {label: load_complete(path, schema=SOURCE_SCHEMAS[label], label=label) for label, path in sources.items()}
    bindings = verify_c1_bindings(c1, sources)
    projections = {
        "kvzap_route_a_persistent_packed": build_kvzap_projection(c1, source_reports["kvzap_qwen_core_contract"], source_reports["kvzap_qwen_llama_coverage"]),
        "snapkv_one_shot_packed": build_snap_projection(c1, source_reports["snapkv_terminal_prefill"]),
        "official_dms_dynamic_resident_slot": build_dms_projection(c1, source_reports["official_dms_active_resident"]),
    }
    for projection in projections.values():
        validate_projection(c1, projection)
    config = {"c1_report": str(args.c1_report), **{label: str(path) for label, path in sources.items()}}
    report = {
        "schema_version": C2_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model provenance-preserving semantic projections over C1-bound trace-derived/functional source artifacts; not measured or modeled hardware evidence",
        "c1_binding": {"path": str(args.c1_report), "sha256": sha256_file(args.c1_report), "schema_version": C1_SCHEMA},
        "source_bindings": bindings,
        "adapter_contract": {
            "name": "CrossFrontendResidencyDescriptor realization adapters",
            "core_fields": list(CORE_FIELDS),
            "projection_rule": "Preserve C1 field status, provenance, and required order; do not synthesize unavailable values.",
            "extensions_remain_frontend_specific": ["persistent_packed", "one_shot_packed", "dynamic_resident_slot"],
        },
        "projections": projections,
        "c2_gate": {"c1_and_all_source_hashes_reverified": True, "three_frontend_specific_projections_written": True, "all_core_statuses_preserved_from_c1": True, "unknown_or_not_applicable_fields_remain_unfabricated": True, "raw_traces_or_tensor_payloads_opened": False, "model_or_runtime_loaded": False, "allocator_or_physical_capacity_claim_made": False, "hardware_interface_or_parameter_selected": False},
        "boundaries": ["C2 maps existing semantic evidence only; it does not establish a shared cache format or hardware interface.", "KVzap model anchors remain separate; C2 does not pool Qwen and Llama values into a resource envelope.", "SnapKV generated decode, online maturity, and native decode semantics remain unknown rather than zero.", "DMS arrival serial, unknown literal position, and required native traversal order remain separate facts.", "No projection creates allocator, physical capacity, traffic, latency, throughput, energy, area, acceleration, architecture, RTL, or parameter-selection evidence."],
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "cross_frontend_c2_realization_adapters_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"C2 cross-frontend realization adapters passed: {output}")


if __name__ == "__main__":
    main()
