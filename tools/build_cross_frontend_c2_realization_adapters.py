#!/usr/bin/env python3
"""Build C2 provenance-preserving realization adapters from the C1 contract.

This no-model tool creates three frontend-specific semantic projections.  It
does not normalize their cache formats, infer missing decode state, allocate
storage, or select a hardware interface.  A projection is valid only when its
source manifests still match the SHA-256 hashes bound by C1 and every core
field retains the C1 availability status.
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


def projected_field(status: str, value: Any = None, *, reason: str | None = None, evidence: list[str]) -> dict[str, Any]:
    item: dict[str, Any] = {"status": status, "evidence_sources": evidence}
    if status in {"unknown", "not_applicable"}:
        if reason is None:
            raise ValueError(f"C2 {status} projection requires a reason")
        item["reason"] = reason
        item["value"] = None
    else:
        item["value"] = value
    return item


def c1_status(c1: dict[str, Any], frontend: str, field_name: str) -> str:
    try:
        status = c1["frontend_field_availability"][frontend]["fields"][field_name]["status"]
    except (KeyError, TypeError) as error:
        raise ValueError(f"C2 C1 availability lacks {frontend}.{field_name}") from error
    if status not in VALUE_STATUSES:
        raise ValueError(f"C2 C1 has invalid availability status for {frontend}.{field_name}")
    return status


def require_qwen_shape(qwen: dict[str, Any], m6: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    descriptor = qwen.get("qwen3_8b_kvzap_resource_descriptor")
    core = qwen.get("route_a_core_contract_v1")
    per_model = m6.get("per_model_fixed_workload_descriptors")
    if not isinstance(descriptor, dict) or not isinstance(core, dict) or not isinstance(per_model, dict):
        raise ValueError("C2 KVzap sources lack required core/coverage descriptors")
    scope = descriptor.get("scope")
    if not isinstance(scope, dict) or scope.get("model") != "Qwen/Qwen3-8B" or scope.get("observed_layer_count") != 36 or scope.get("observed_kv_head_count") != 288:
        raise ValueError("C2 KVzap Qwen source does not expose the expected semantic topology")
    if not isinstance(per_model.get("qwen3_8b_kvzap"), list) or not isinstance(per_model.get("nous_llama31_8b_kvzap"), list):
        raise ValueError("C2 KVzap coverage must retain separate Qwen and Llama rows")
    return descriptor, scope, core


def snap_statuses(snap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    descriptor = snap.get("descriptor")
    rows = descriptor.get("field_statuses") if isinstance(descriptor, dict) else None
    if not isinstance(rows, list):
        raise ValueError("C2 SnapKV source lacks field-status rows")
    by_name = {row.get("name"): row for row in rows if isinstance(row, dict)}
    required = ("terminal_per_identity_action", "canonical_identity_and_append_order", "online_decision_epochs_and_maturity_events", "generated_token_decision_and_decode_continuation")
    if any(by_name.get(name, {}).get("status") not in {"available", "unavailable"} for name in required):
        raise ValueError("C2 SnapKV source has incomplete terminal/decode boundary")
    if by_name["generated_token_decision_and_decode_continuation"].get("value") is not None:
        raise ValueError("C2 SnapKV generated decode must remain null")
    return by_name


def require_dms_shape(dms: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    active = dms.get("active_resident_attention")
    topology = dms.get("fresh_native_control_topology")
    if not isinstance(active, dict) or not isinstance(topology, dict):
        raise ValueError("C2 DMS source lacks active-resident/topology evidence")
    if active.get("all_36_layers_all_decode_steps_observed") is not True or topology.get("final_active_physical_slot_order_nonmonotonic_count") != 269:
        raise ValueError("C2 DMS source does not preserve all-layer/nonmonotonic-order boundary")
    return active, topology


def build_kvzap_projection(c1: dict[str, Any], qwen: dict[str, Any], m6: dict[str, Any]) -> dict[str, Any]:
    frontend = "kvzap_route_a_persistent_packed"
    descriptor, scope, core = require_qwen_shape(qwen, m6)
    lifecycle = core["lifecycle"]
    attention = core["attention"]
    dependency = core["dependency"]
    return {
        "frontend": frontend,
        "realization_extension": "persistent_packed",
        "model_anchors": {
            "qwen3_8b": {"model": scope["model"], "model_revision": scope["model_revision"], "layer_count": scope["observed_layer_count"], "kv_head_count": scope["observed_kv_head_count"], "query_heads_per_kv_head_group": descriptor["qwen_specific_group_width_values"]},
            "llama31_8b": {"status": "observed_separate_coverage", "reason": "M6 supplies separate normalized rows; C2 does not pool them with Qwen or infer an identical topology."},
        },
        "core_fields": {
            "model_topology": projected_field(c1_status(c1, frontend, "model_topology"), {"topology_scope": "model-specific; Qwen and Llama rows remain separate", "qwen": scope}, evidence=["kvzap_qwen_core_contract", "kvzap_qwen_llama_coverage"]),
            "identity": projected_field(c1_status(c1, frontend, "identity"), {"source_record_id_kind": "original_logical_position", "keying": "(layer, kv_head, original_logical_position)"}, evidence=["kvzap_qwen_core_contract"]),
            "epoch": projected_field(c1_status(c1, frontend, "epoch"), {"lifecycle": ["creation", "hot_window", "maturity", "pending_staging", "sealed_packed_cold"], "source_statement": lifecycle}, evidence=["kvzap_qwen_core_contract"]),
            "decision": projected_field(c1_status(c1, frontend, "decision"), {"retain_drop": "original KVzap decision available no later than maturity", "source_statement": lifecycle[0]}, evidence=["kvzap_qwen_core_contract"]),
            "visibility": projected_field(c1_status(c1, frontend, "visibility"), {"active_sources": ["hot", "pending", "packed"], "semantic_scope": "policy-on functional reference"}, evidence=["kvzap_qwen_core_contract"]),
            "position_provenance": projected_field(c1_status(c1, frontend, "position_provenance"), {"position_kind": "original_logical_position", "append_order_preserved": True}, evidence=["kvzap_qwen_core_contract"]),
            "traversal_order": projected_field(c1_status(c1, frontend, "traversal_order"), {"source_order_contract": "ordered hot/pending/packed partial-or-skip decisions, then one merge", "cross_layer_order_preserved": True, "source_statement": dependency}, evidence=["kvzap_qwen_core_contract"]),
            "attention_binding": projected_field(c1_status(c1, frontend, "attention_binding"), {"comparator": "online same-mask dense; Full-KV bypass distinct", "source_statement": attention, "query_to_kv_group_relation": "model-scoped, not an accelerator dimension"}, evidence=["kvzap_qwen_core_contract"]),
        },
        "realization_extension_fields": {"hot_pending_packed_lifecycle": "applicable", "page_or_tail_values": "frontend-specific trace-derived fields; not exported as common core", "online_softmax_merge": "KVzap-specific accepted functional composition"},
    }


def build_snap_projection(c1: dict[str, Any], snap: dict[str, Any]) -> dict[str, Any]:
    frontend = "snapkv_one_shot_packed"
    rows = snap_statuses(snap)
    source = snap["source"]
    terminal = rows["terminal_per_identity_action"]["value"]
    return {
        "frontend": frontend,
        "realization_extension": "one_shot_packed",
        "model_anchors": {"qwen3_8b": {"status": "derived", "reason": "P2 is a fixed Qwen3-8B study; no pooled topology or hardware dimension is created."}},
        "core_fields": {
            "model_topology": projected_field(c1_status(c1, frontend, "model_topology"), {"scope": "fixed Qwen3-8B P2 study only"}, evidence=["snapkv_terminal_prefill"]),
            "identity": projected_field(c1_status(c1, frontend, "identity"), {"source_record_id_kind": "original_logical_position", "keying": "(layer, kv_head, original_logical_position)", "terminal_event_count": terminal["event_count"]}, evidence=["snapkv_terminal_prefill"]),
            "epoch": projected_field(c1_status(c1, frontend, "epoch"), {"observed_epoch": source["p0_decision_epoch"], "generated_decode_epoch": None}, evidence=["snapkv_terminal_prefill"]),
            "decision": projected_field(c1_status(c1, frontend, "decision"), {"decision_kind": "terminal prefill retain/drop", "known_epoch": terminal["decision_epoch"], "online_effective_epoch": None}, evidence=["snapkv_terminal_prefill"]),
            "visibility": projected_field(c1_status(c1, frontend, "visibility"), {"supported_scope": "bounded same-mask prefill-tail probe", "generated_decode_visibility": None}, evidence=["snapkv_terminal_prefill"]),
            "position_provenance": projected_field(c1_status(c1, frontend, "position_provenance"), {"position_kind": "original_logical_position", "protected_suffix_mapping": "recorded only for the compatibility mapping"}, evidence=["snapkv_terminal_prefill"]),
            "traversal_order": projected_field(c1_status(c1, frontend, "traversal_order"), {"order": "canonical original-position order per (layer, KV head)", "excluded": "native score-ranked gather order"}, evidence=["snapkv_terminal_prefill"]),
            "attention_binding": projected_field(c1_status(c1, frontend, "attention_binding"), {"comparator": "same-mask prefill-tail", "native_decode_comparator": None}, evidence=["snapkv_terminal_prefill"]),
        },
        "unknown_subfields": {
            "generated_decode_epoch": "P2 records generated-token/decode continuation as unavailable/null.",
            "online_decision_or_maturity_epoch": "P2 records no online decision epochs or maturity events.",
            "native_decode_visibility_and_comparator": "Native SnapKV cache/decode semantics are deliberately excluded.",
        },
        "realization_extension_fields": {"terminal_action": "applicable", "protected_observation_suffix": "applicable only to the P0-P3 compatibility mapping", "pending_or_decode_lifecycle": "unknown, not zero"},
    }


def build_dms_projection(c1: dict[str, Any], dms: dict[str, Any]) -> dict[str, Any]:
    frontend = "official_dms_dynamic_resident_slot"
    active, topology = require_dms_shape(dms)
    return {
        "frontend": frontend,
        "realization_extension": "dynamic_resident_slot",
        "model_anchors": {"qwen3_8b": {"status": "observed", "layer_coverage": 36, "query_heads_per_kv_head_group_values": active["query_heads_per_kv_head_group_values"], "head_dim_values": active["head_dim_values"], "scope": "fixed official DMS decode contract"}},
        "core_fields": {
            "model_topology": projected_field(c1_status(c1, frontend, "model_topology"), {"layer_coverage": 36, "query_heads_per_kv_head_group_values": active["query_heads_per_kv_head_group_values"], "head_dim_values": active["head_dim_values"]}, evidence=["official_dms_active_resident"]),
            "identity": projected_field(c1_status(c1, frontend, "identity"), {"source_record_id_kind": "source_arrival_serial", "literal_original_token_position": None}, evidence=["official_dms_active_resident"]),
            "epoch": projected_field(c1_status(c1, frontend, "epoch"), {"phase": "fixed decode contract", "decode_flash_attention_call_count": active["decode_flash_attention_call_count"]}, evidence=["official_dms_active_resident"]),
            "decision": projected_field(c1_status(c1, frontend, "decision"), {"controller": "delayed eviction/reuse", "provenance": "M1-M3 bound and replayed in M4"}, evidence=["official_dms_active_resident"]),
            "visibility": projected_field(c1_status(c1, frontend, "visibility"), {"source": "native active resident set", "semantic_scope": "one-source functional replay"}, evidence=["official_dms_active_resident"]),
            "position_provenance": projected_field(c1_status(c1, frontend, "position_provenance"), reason="No generally captured literal original token-position field exists; arrival serial and required native order remain distinct.", evidence=["official_dms_active_resident"]),
            "traversal_order": projected_field(c1_status(c1, frontend, "traversal_order"), {"order": "official native logical-slot/block-table order", "nonmonotonic_layer_kv_head_orders": topology["final_active_physical_slot_order_nonmonotonic_count"], "arrival_order_substitution": "forbidden"}, evidence=["official_dms_active_resident"]),
            "attention_binding": projected_field(c1_status(c1, frontend, "attention_binding"), {"comparator": "unchanged official native DMS FlashAttention versus one-source active-resident FP32 replay", "tolerance_scope": "fixed contract only"}, evidence=["official_dms_active_resident"]),
        },
        "realization_extension_fields": {"active_slot": "applicable", "delayed_eviction_and_reuse": "applicable", "native_slot_block_traversal": "required", "packed_cold_mapping": "not established"},
    }


def validate_projection(c1: dict[str, Any], projection: dict[str, Any]) -> None:
    frontend = projection.get("frontend")
    if frontend not in FRONTENDS or projection.get("realization_extension") not in {"persistent_packed", "one_shot_packed", "dynamic_resident_slot"}:
        raise ValueError("C2 projection has unknown frontend/extension")
    fields = projection.get("core_fields")
    if not isinstance(fields, dict) or set(fields) != set(CORE_FIELDS):
        raise ValueError(f"C2 {frontend} must project exactly the v1 core fields")
    for field_name, item in fields.items():
        expected = c1_status(c1, frontend, field_name)
        if item.get("status") != expected:
            raise ValueError(f"C2 {frontend}.{field_name} changed C1 status {expected!r} to {item.get('status')!r}")
        if not item.get("evidence_sources"):
            raise ValueError(f"C2 {frontend}.{field_name} lacks evidence_sources")
        if expected in {"unknown", "not_applicable"}:
            if item.get("value") is not None or not item.get("reason"):
                raise ValueError(f"C2 {frontend}.{field_name} fabricated or unexplained unavailable value")


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
