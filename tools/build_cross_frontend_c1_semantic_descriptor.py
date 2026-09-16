#!/usr/bin/env python3
"""Build the no-model C1 cross-frontend semantic descriptor contract.

C1 turns only C0-bound completed manifests into a typed availability matrix. It
does not read raw trace/tensor payloads, load a model, or create a shared cache
or hardware interface.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

C1_SCHEMA = "cross-frontend-c1-semantic-descriptor-1.0"
C0_SCHEMA = "cross-frontend-c0-evidence-index-1.0"
VALUE_STATUSES = frozenset({"observed", "derived", "modeled", "unknown", "not_applicable"})
CORE_FIELD_TYPES = {
    "model_topology": {"value_type": "object", "scope": "model-level; model ID/revision, layer count, KV-head count, and query-to-KV grouping when available"},
    "identity": {"value_type": "object", "scope": "(layer, kv_head, source_record_id), with source_record_id kind explicitly labeled"},
    "epoch": {"value_type": "object", "scope": "phase, event kind, forward/decode index, and q_len when available"},
    "decision": {"value_type": "object", "scope": "decision value plus known and effective epochs; unobserved timing stays unknown"},
    "visibility": {"value_type": "object", "scope": "whether a record must be attention-visible at an epoch, distinct from physical completion"},
    "position_provenance": {"value_type": "object", "scope": "literal original logical position, explicit serial, or explicit unknown; never inferred from a slot ID"},
    "traversal_order": {"value_type": "object", "scope": "required source traversal order and the evidence/reason that constrains it"},
    "attention_binding": {"value_type": "object", "scope": "query/KV grouping and the frontend-specific accepted semantic comparator"},
}
REALIZATION_EXTENSIONS = {
    "persistent_packed": {"applies_to": "KVzap Route-A", "extension_only_fields": ["hot_pending_packed_state", "maturity", "admission_service", "append_only_pages", "page_sealing_and_tail"]},
    "one_shot_packed": {"applies_to": "SnapKV P0-P3 mapping", "extension_only_fields": ["terminal_action", "protected_observation_suffix", "canonical_static_packed_state", "initial_compaction"]},
    "dynamic_resident_slot": {"applies_to": "official DMS M0-M4", "extension_only_fields": ["active_slot", "delayed_eviction", "reclaim_reuse", "slot_to_arrival_identity", "native_slot_block_traversal"]},
}


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


def field(status: str, statement: str, *, reason: str | None = None, subfields: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"status": status, "statement": statement}
    if reason is not None:
        item["reason"] = reason
    if subfields is not None:
        item["subfields"] = subfields
    return item


def availability_matrix() -> dict[str, Any]:
    return {
        "kvzap_route_a_persistent_packed": {
            "frontend": "KVzap Route-A", "realization_extension": "persistent_packed",
            "evidence_scope": "Qwen core closure plus separate Qwen/Llama fixed-horizon coverage; model rows remain separate",
            "fields": {
                "model_topology": field("observed", "Model-specific descriptors are recorded without pooling Qwen and Llama values."),
                "identity": field("observed", "Layer, KV-head, and original-position source identities are preserved by Route-A lifecycle evidence."),
                "epoch": field("observed", "Creation, hot-window, maturity, pending, and packed-cold lifecycle epochs are explicitly represented."),
                "decision": field("observed", "Original KVzap decision semantics and maturity handling are bound by the core closure."),
                "visibility": field("observed", "Policy-on hot, pending, and packed pages are functionally attention-visible under the accepted comparator."),
                "position_provenance": field("observed", "Original positions and append order are preserved by the same-mask reference."),
                "traversal_order": field("observed", "The accepted reference preserves original mask, position, append order, hot window, and online-softmax composition."),
                "attention_binding": field("observed", "Online same-mask dense is the semantic comparator; Full-KV bypass remains a separate control."),
            },
        },
        "snapkv_one_shot_packed": {
            "frontend": "SnapKV", "realization_extension": "one_shot_packed",
            "evidence_scope": "Qwen3-8B terminal-prefill P2/P3 mapping and bounded prefill-tail same-mask probe only",
            "fields": {
                "model_topology": field("derived", "The P2 artifact is archived as a Qwen3-8B fixed-model study; it must not contribute a pooled hardware dimension."),
                "identity": field("observed", "One terminal prefill action is recorded per layer/KV-head/original-position identity."),
                "epoch": field("observed", "Only the terminal prefill epoch is observed.", subfields={"generated_decode_epoch": {"status": "unknown", "reason": "P2 records generated-token/decode continuation as unavailable/null."}}),
                "decision": field("observed", "Terminal retained/dropped action is observed at prefill completion.", subfields={"online_known_or_effective_epoch": {"status": "unknown", "reason": "No online decision/maturity event is observed in P2."}}),
                "visibility": field("derived", "Bounded same-mask prefill-tail visibility is supported by the P2 semantic probe, not native SnapKV decode behavior.", subfields={"generated_decode_visibility": {"status": "unknown", "reason": "Native SnapKV decode/cache semantics were deliberately excluded."}}),
                "position_provenance": field("observed", "Canonical original-position mapping and protected suffix mapping are recorded."),
                "traversal_order": field("observed", "Canonical original-position order is the static packed mapping order; it is not asserted as a native decode traversal."),
                "attention_binding": field("observed", "Same-mask prefill-tail is the accepted bounded comparator.", subfields={"native_decode_comparator": {"status": "unknown", "reason": "No native SnapKV decode claim is supported."}}),
            },
        },
        "official_dms_dynamic_resident_slot": {
            "frontend": "official DMS", "realization_extension": "dynamic_resident_slot",
            "evidence_scope": "Qwen3-8B official DMS M0-M4 fixed decode contract",
            "fields": {
                "model_topology": field("observed", "The all-36-layer native DMS replay records the workload/model binding and observed query-to-KV grouping."),
                "identity": field("observed", "Source arrival serial is observed as the source-record identity; it is not relabeled as a literal token position."),
                "epoch": field("observed", "The fixed decode contract observes delayed controller events and active-resident attention replay."),
                "decision": field("observed", "Delayed eviction/reuse controller behavior is provenance-bound through M1-M3 and replayed in M4."),
                "visibility": field("observed", "The native active resident set is functionally replayed as one attention source under the accepted contract."),
                "position_provenance": field("unknown", "Literal original token position is unavailable.", reason="A generally captured literal original token-position field is absent; only arrival serial and required native order are available."),
                "traversal_order": field("observed", "Required native logical-slot/block-table traversal order is observed; nonmonotonic layer/KV-head orders preclude substituting arrival order."),
                "attention_binding": field("observed", "Unchanged official native DMS FlashAttention is compared with one-source active-resident FP32 replay."),
            },
        },
    }


def validate_matrix(matrix: dict[str, Any]) -> None:
    if any(set(frontend.get("fields", {})) != set(CORE_FIELD_TYPES) for frontend in matrix.values()):
        raise ValueError("C1 every frontend must provide exactly the typed v1 core fields")
    for frontend_name, frontend in matrix.items():
        if frontend.get("realization_extension") not in REALIZATION_EXTENSIONS:
            raise ValueError(f"C1 {frontend_name} names an unknown realization extension")
        for name, item in frontend["fields"].items():
            if item.get("status") not in VALUE_STATUSES:
                raise ValueError(f"C1 {frontend_name}.{name} has invalid status")
            if item["status"] in {"unknown", "not_applicable"} and not item.get("reason"):
                raise ValueError(f"C1 {frontend_name}.{name} requires a reason for {item['status']}")
            for subfield_name, subfield in item.get("subfields", {}).items():
                if subfield.get("status") not in VALUE_STATUSES:
                    raise ValueError(f"C1 {frontend_name}.{name}.{subfield_name} has invalid status")
                if subfield["status"] in {"unknown", "not_applicable"} and not subfield.get("reason"):
                    raise ValueError(f"C1 {frontend_name}.{name}.{subfield_name} requires a reason for {subfield['status']}")


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
