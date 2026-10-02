"""No-model validation for RTL2.0d typed delivery-router descriptors."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "kvzap-route-a-rtl2-0d-typed-delivery-router-1.0"
STATUS = "rtl2_0d_endpoint_descriptor_contract_closed_router_behavior_pending"
READS = {
    "pack_read": "p3_pending_read",
    "s2_full": "s2_full_fill",
    "s2_packed": "s2_packed_fill",
    "direct_pending": "direct_pending_read",
}
WRITES = {
    "pack_write": "packed_write_terminal",
    "descriptor_maintenance": "descriptor_maintenance_terminal",
}


class RTL2TypedDeliveryRouterError(ValueError):
    """Raised when the typed endpoint-descriptor contract drifts."""


def load_manifest(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL2TypedDeliveryRouterError("manifest root must be object")
    return value


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA or manifest.get("status") != STATUS:
        raise RTL2TypedDeliveryRouterError("unexpected RTL2.0d manifest identity")
    if "No router behavior" not in str(manifest.get("scope")):
        raise RTL2TypedDeliveryRouterError("scope must retain no-behavior boundary")
    for path in _strings(manifest, "contract_references"):
        if not Path(path).is_file():
            raise RTL2TypedDeliveryRouterError(f"missing contract reference: {path}")

    router = _object(manifest, "router")
    if router.get("name") != "route_a_typed_delivery_router" or router.get("parent") != "route_a_kv_subsystem_top":
        raise RTL2TypedDeliveryRouterError("router hierarchy differs")
    if router.get("descriptor_provider") != "route_a_delivery_context_registry":
        raise RTL2TypedDeliveryRouterError("router must use separately owned registry")
    forbidden = set(_strings(router, "forbidden"))
    required_forbidden = {
        "target reconstruction from response fields",
        "generic untyped response demultiplexing",
        "response data mutation",
        "S2 READY creation",
        "authority transfer",
    }
    if not required_forbidden.issubset(forbidden):
        raise RTL2TypedDeliveryRouterError("router prohibitions incomplete")

    resolution = _object(manifest, "registry_resolution")
    if resolution.get("owner") != "route_a_delivery_context_registry":
        raise RTL2TypedDeliveryRouterError("registry owner differs")
    required_match = {
        "delivery_context_ref",
        "transaction_identity",
        "reset_epoch",
        "candidate_class",
        "target_identity_generation",
    }
    if not required_match.issubset(_strings(resolution, "match_fields")):
        raise RTL2TypedDeliveryRouterError("registry match fields incomplete")
    if (
        "stale_epoch" not in _strings(resolution, "reject_without_endpoint_mutation")
        or "retain the ref across accepted non-final read fragments" not in str(resolution.get("release_rule"))
    ):
        raise RTL2TypedDeliveryRouterError("stale rejection or multi-fragment lifetime missing")

    read = _object(manifest, "typed_read_fragment")
    if read.get("name") != "TypedReadFragment":
        raise RTL2TypedDeliveryRouterError("read fragment type differs")
    if not {"fragment_index", "last", "status", "data_512b"}.issubset(_strings(read, "fields")):
        raise RTL2TypedDeliveryRouterError("read fragment must preserve complete R1 data fields")
    if (
        "data_512b unchanged" not in str(read.get("ok_rule"))
        or "do not deposit payload" not in str(read.get("fault_rule"))
        or "only after the endpoint accepts" not in str(read.get("control_after_payload_accept"))
    ):
        raise RTL2TypedDeliveryRouterError("read payload/fault/control ordering differs")

    write = _object(manifest, "typed_write_terminal")
    if write.get("name") != "TypedWriteTerminal" or write.get("no_read_data") is not True or write.get("final_only") is not True:
        raise RTL2TypedDeliveryRouterError("write terminal boundary differs")

    reads = _records(manifest, "read_targets")
    if _mapping(reads) != READS:
        raise RTL2TypedDeliveryRouterError("read target mapping differs")
    by_read = {record["candidate_class"]: record for record in reads}
    required_read_fields = {
        "pack_read": {"p3_layer", "p3_stage_generation"},
        "s2_full": {"page_ref", "s2_slot", "source_generation", "requires_sidecar=false"},
        "s2_packed": {"page_ref", "s2_slot", "source_generation", "requires_sidecar=true"},
        "direct_pending": {"endpoint_generation", "ordinal", "explicit_empty"},
    }
    for candidate_class, required in required_read_fields.items():
        if not required.issubset(_strings(by_read[candidate_class], "descriptor_fields")):
            raise RTL2TypedDeliveryRouterError(f"read descriptor incomplete: {candidate_class}")
    if by_read["s2_full"].get("requires_sidecar") is not False or by_read["s2_packed"].get("requires_sidecar") is not True:
        raise RTL2TypedDeliveryRouterError("S2 sidecar distinction differs")

    writes = _records(manifest, "write_targets")
    if _mapping(writes) != WRITES:
        raise RTL2TypedDeliveryRouterError("write target mapping differs")
    by_write = {record["candidate_class"]: record for record in writes}
    for candidate_class, durable_field in {
        "pack_write": "r1_payload_durable",
        "descriptor_maintenance": "r1_descriptor_durable",
    }.items():
        record = by_write[candidate_class]
        if record.get("durable_field") != durable_field or record.get("durable_rule") != "last && status==OK":
            raise RTL2TypedDeliveryRouterError(f"write durable rule differs: {candidate_class}")

    excluded = set(_strings(manifest, "excluded_paths"))
    required_excluded = {
        "metadata publication",
        "authority handoff",
        "S2 READY",
        "R4 packetization and numeric result",
        "R6 lifecycle retirement",
    }
    if not required_excluded.issubset(excluded):
        raise RTL2TypedDeliveryRouterError("router exclusion boundary incomplete")

    follow = _object(manifest, "required_follow_on")
    if follow.get("behavioral_phase") != "rtl2_2" or "replaceable functional payload/transport wrappers" not in str(follow.get("requires")):
        raise RTL2TypedDeliveryRouterError("RTL2.2 follow-on differs")
    labels = set(_strings(manifest, "evidence_labels"))
    if not {"no model/GPU", "no PPA claim", "no RTL correctness claim", "no new A4 DSE"}.issubset(labels):
        raise RTL2TypedDeliveryRouterError("evidence labels incomplete")


def _object(manifest: dict[str, Any], key: str) -> dict[str, Any]:
    value = manifest.get(key)
    if not isinstance(value, dict):
        raise RTL2TypedDeliveryRouterError(f"{key} must be object")
    return value


def _records(manifest: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = manifest.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RTL2TypedDeliveryRouterError(f"{key} must be object list")
    return value


def _strings(value: dict[str, Any], key: str) -> list[str]:
    items = value.get(key)
    if not isinstance(items, list) or not items or not all(isinstance(item, str) and item for item in items):
        raise RTL2TypedDeliveryRouterError(f"{key} must be string list")
    return items


def _mapping(records: list[dict[str, Any]]) -> dict[str, str]:
    result = {record.get("candidate_class"): record.get("target_kind") for record in records}
    if (
        any(not isinstance(key, str) or not key or not isinstance(value, str) or not value for key, value in result.items())
        or len(result) != len(records)
    ):
        raise RTL2TypedDeliveryRouterError("target classes must be unique and named")
    return result
