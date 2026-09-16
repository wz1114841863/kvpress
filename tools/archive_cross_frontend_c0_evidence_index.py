#!/usr/bin/env python3
"""Create the C0 hash-bound cross-frontend evidence index.

This no-model provenance gate reads only four completed JSON artifacts and the
Markdown archive which names them. It never opens a trace/tensor payload,
model, cache, or allocator state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


C0_SCHEMA = "cross-frontend-c0-evidence-index-1.0"

ARTIFACTS = {
    "kvzap_qwen_core_contract": {
        "schema": "kvzap-route-a4214-core-contract-closure-1.0",
        "guards_true": ("all_input_hashes_and_required_guards_verified", "core_contract_separates_portable_from_qwen_specific_fields", "three_workload_qwen_descriptor_coverage_verified", "no_hardware_parameter_selected"),
    },
    "kvzap_qwen_llama_coverage": {
        "schema": "kvzap-route-a-m6-cross-model-fixed-horizon-envelope-1.2",
        "guards_true": ("all_input_hashes_and_required_guards_verified", "qwen_and_llama_rows_kept_separate", "absolute_event_counts_not_pooled", "same_actual_policy_decode_call_count_verified", "no_model_runtime_loaded", "no_hardware_parameter_selected"),
    },
    "snapkv_terminal_prefill": {"schema": "route-a-snapkv-p2-lifecycle-resource-descriptor-1.0", "guards_true": ()},
    "official_dms_active_resident": {
        "schema": "route-a-dms-m4-active-resident-attention-gate-1.0",
        "guards_true": ("official_dms_model_and_base_tokenizer_bound_to_completed_m0", "m1_m2_m3_provenance_bound", "fresh_control_topology_replayed", "all_36_layers_all_decode_steps_observed", "all_active_resident_replays_within_declared_tolerance", "native_dms_cache_used", "no_kv_payload_serialized"),
        "guards_false": ("attention_replaced", "route_a_backend_instantiated", "kvpress_dmspress_used", "kvzap_predictor_used", "fake_key_attention_used", "generation_api_used"),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="C0 no-model cross-frontend evidence index; validates source hashes, schemas, status, and claim-boundary guards.")
    parser.add_argument("--archive", type=Path, required=True, help="Cross-frontend Markdown evidence archive.")
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


def load_completed(path: Path, *, schema: str, label: str) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise FileNotFoundError(f"C0 required {label} artifact is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != schema or value.get("status") != "complete":
        raise ValueError(f"C0 required {label} completed schema {schema}, got {value.get('schema_version')!r}/{value.get('status')!r}")
    return value, sha256_file(path)


def require_guard_values(value: dict[str, Any], *, label: str, true_names: tuple[str, ...], false_names: tuple[str, ...] = ()) -> dict[str, bool]:
    guards = value.get("observational_guards")
    if not isinstance(guards, dict):
        raise ValueError(f"C0 required {label} observational_guards object")
    bad_true = [name for name in true_names if guards.get(name) is not True]
    bad_false = [name for name in false_names if guards.get(name) is not False]
    if bad_true or bad_false:
        raise ValueError(f"C0 {label} guard mismatch: required_true={bad_true}, required_false={bad_false}")
    return {name: bool(guards[name]) for name in (*true_names, *false_names)}


def require_snapkv_boundary(value: dict[str, Any]) -> dict[str, bool]:
    descriptor = value.get("descriptor")
    eligibility = descriptor.get("eligibility") if isinstance(descriptor, dict) else None
    if not isinstance(eligibility, dict):
        raise ValueError("C0 SnapKV P2 lacks descriptor eligibility")
    expected = {"bounded_prefill_same_mask_semantic_probe": True, "static_canonical_route_a_mapping": True, "decode_lifecycle_or_pending_contract": False, "native_snapkv_cache_or_decode_semantics": False, "physical_resource_or_hardware_contract": False, "scheduler_or_backpressure_contract": False}
    mismatch = {name: (eligibility.get(name), required) for name, required in expected.items() if eligibility.get(name) is not required}
    if mismatch:
        raise ValueError(f"C0 SnapKV P2 eligibility boundary mismatch: {mismatch}")
    statuses = descriptor.get("field_statuses")
    generated = [row for row in statuses or [] if isinstance(row, dict) and row.get("name") == "generated_token_decision_and_decode_continuation"]
    if len(generated) != 1 or generated[0].get("status") != "unavailable" or generated[0].get("value") is not None:
        raise ValueError("C0 SnapKV P2 must preserve generated-token/decode as unavailable, not zero")
    return expected


def require_archive_binding(archive: str, *, artifact_path: Path, digest: str, label: str) -> None:
    if artifact_path.as_posix() not in archive or digest not in archive:
        raise ValueError(f"C0 archive does not bind {label} path and SHA-256")


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"C0 output directory already exists: {args.output_dir}")
    if not args.archive.is_file():
        raise FileNotFoundError(f"C0 evidence archive is absent: {args.archive}")
    archive_text = args.archive.read_text(encoding="utf-8")
    sources = {"kvzap_qwen_core_contract": args.qwen_core_contract, "kvzap_qwen_llama_coverage": args.qwen_llama_coverage, "snapkv_terminal_prefill": args.snapkv_terminal_prefill, "official_dms_active_resident": args.official_dms_active_resident}
    records: dict[str, Any] = {}
    for label, path in sources.items():
        contract = ARTIFACTS[label]
        report, digest = load_completed(path, schema=contract["schema"], label=label)
        require_archive_binding(archive_text, artifact_path=path, digest=digest, label=label)
        if label == "snapkv_terminal_prefill":
            details = {"snapkv_eligibility_boundary": require_snapkv_boundary(report)}
        else:
            details = {"validated_guards": require_guard_values(report, label=label, true_names=contract["guards_true"], false_names=contract.get("guards_false", ())) }
        records[label] = {"path": str(path), "sha256": digest, "schema_version": contract["schema"], "status": "complete", **details}
    config = {"archive": str(args.archive), **{label: str(path) for label, path in sources.items()}}
    report = {"schema_version": C0_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model hash-bound provenance index over completed trace-derived/functional/modeled source artifacts; not hardware evidence", "archive": {"path": str(args.archive), "sha256": sha256_file(args.archive)}, "completed_artifacts": records, "c0_gate": {"all_four_completed_sources_hash_bound": True, "archive_path_and_hash_bindings_verified": True, "required_semantic_and_claim_boundary_guards_verified": True, "raw_traces_or_tensor_payloads_opened": False, "model_or_runtime_loaded": False, "hardware_parameter_selected": False}, "boundaries": ["C0 indexes completed manifests and does not create, copy, mutate, or interpret raw trace/tensor payloads.", "SnapKV generated-token/decode behavior remains unavailable, not zero or not-applicable.", "DMS remains native active-resident source/order evidence, not a packed-cold Route-A mapping.", "This report is provenance-only, not a common descriptor, shared hardware interface, resource envelope, architecture specification, or RTL gate."]}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "cross_frontend_c0_evidence_index_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"C0 cross-frontend evidence index passed: {output}")


if __name__ == "__main__":
    main()
