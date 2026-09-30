"""No-model validation for the RTL1-I cross-owner planning manifest.

The manifest freezes association ownership and semantic boundaries before any
top-level behavioral wiring exists. It is not an RTL generator, implementation,
timing model, or PPA model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "kvzap-route-a-rtl1-i-integration-manifest-1.0"
MANIFEST_STATUS = "rtl1_i0_contract_frozen_no_behavioral_wiring"
REQUIRED_INERT_IDS = frozenset(
    {
        "component_status_to_r6",
        "r6_authority_out",
        "r3_authority_to_r6",
        "r6_merge_ready",
        "s2_mem_init",
        "s2_fill_and_commit",
        "s2_release",
        "direct_mem_init",
        "direct_terminal_and_commit",
        "direct_release",
        "r4_packet_inputs",
        "r4_result_or_fault",
        "r4_consumer_commit",
        "r2_candidate",
        "r1_mem_init",
        "r2_source_delivery",
        "r3_mem_init_and_ingress",
        "r5_mem_init_and_ingress",
        "r3_r5_lifecycle_publish_chain",
    }
)
REQUIRED_ASSOCIATION_IDS = frozenset(
    {
        "admission_context",
        "publication_membership_and_authority_observation",
        "delivery_context",
        "r4_source_instance_sideband",
        "init_and_drain_status",
        "reclaim_and_generation_reuse",
    }
)
REQUIRED_COMPOSED_ASSERTIONS = frozenset(
    {
        "a_metadata_publish_commit",
        "a_authority_conservation",
        "a_gqa_release",
        "a_numeric_fault_consumer",
        "a_reset_stale_exclusion",
        "a_descriptor_invalidate_before_free",
        "a_global_retirement_membership",
        "p_accepted_to_terminal",
        "p_retire_to_ack",
        "p_credit_return",
    }
)


class RTL1IManifestError(ValueError):
    """Raised when the non-RTL RTL1-I manifest is incomplete or drifting."""


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load one manifest without inferring implementation defaults."""
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RTL1IManifestError("manifest root must be a JSON object")
    return loaded


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Validate I0 semantic inventory, without validating RTL behavior."""
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise RTL1IManifestError("unexpected manifest schema_version")
    if manifest.get("status") != MANIFEST_STATUS:
        raise RTL1IManifestError("unexpected RTL1-I0 manifest status")
    scope = manifest.get("scope")
    if not isinstance(scope, str) or "No Chisel behavior" not in scope:
        raise RTL1IManifestError("manifest scope must preserve the no-behavior boundary")

    references = manifest.get("contract_references")
    if not isinstance(references, list) or not references:
        raise RTL1IManifestError("contract_references must be a nonempty list")
    for reference in references:
        if not isinstance(reference, str) or not Path(reference).is_file():
            raise RTL1IManifestError(f"contract reference does not exist: {reference!r}")

    inert = _records(manifest, "top_inert_inventory")
    if _unique_ids(inert, "top-inert") != REQUIRED_INERT_IDS:
        raise RTL1IManifestError("top-inert inventory differs from the I0 closure set")
    for record in inert:
        _required_strings(record, "id", "producer", "consumer", "current_state", "closure_step", "required_fact")
        if record["closure_step"] not in {"rtl1_i1", "rtl1_i2", "rtl1_i3", "rtl1_i4", "deferred_numeric_gate", "rtl1_i2_then_i3", "rtl1_i1_then_i2"}:
            raise RTL1IManifestError(f"top-inert record has unknown closure step: {record['id']}")

    associations = _records(manifest, "association_records")
    if _unique_ids(associations, "association") != REQUIRED_ASSOCIATION_IDS:
        raise RTL1IManifestError("association inventory differs from the I0 closure set")
    for record in associations:
        _required_strings(record, "id", "producer_owner", "consumer_owner", "atomic_boundary", "cardinality", "implementation_step")
        identity_fields = record.get("identity_fields")
        forbidden = record.get("forbidden")
        if not isinstance(identity_fields, list) or not all(isinstance(field, str) and field for field in identity_fields):
            raise RTL1IManifestError(f"association {record['id']} lacks identity_fields")
        if not isinstance(forbidden, list) or not all(isinstance(item, str) and item for item in forbidden):
            raise RTL1IManifestError(f"association {record['id']} lacks forbidden constraints")

    publication = _by_id(associations, "publication_membership_and_authority_observation")
    if publication["atomic_boundary"] != "existing metadata_publish_commit only":
        raise RTL1IManifestError("publication association must retain the sole metadata_publish_commit boundary")
    if "entry_id" not in publication["identity_fields"] or "record_ordinal" not in publication["identity_fields"]:
        raise RTL1IManifestError("publication membership must preserve per-record entry association")
    if "first_entry_plus_count span substitution" not in publication["forbidden"]:
        raise RTL1IManifestError("publication membership must forbid span substitution")

    r4 = _by_id(associations, "r4_source_instance_sideband")
    if "modify frozen 128-bit R4 header" not in r4["forbidden"]:
        raise RTL1IManifestError("R4 sideband must preserve the frozen packet header")
    delivery = _by_id(associations, "delivery_context")
    if "delivery_context_ref" not in delivery["identity_fields"]:
        raise RTL1IManifestError("delivery association must preserve delivery_context_ref")

    assertions = manifest.get("composed_assertions")
    if not isinstance(assertions, list) or set(assertions) != REQUIRED_COMPOSED_ASSERTIONS or len(assertions) != len(REQUIRED_COMPOSED_ASSERTIONS):
        raise RTL1IManifestError("composed assertion inventory differs from the I0 closure set")

    hierarchy = manifest.get("hierarchy_control")
    if not isinstance(hierarchy, dict) or hierarchy.get("rtl1_i0_behavioral_modules_added") is not False:
        raise RTL1IManifestError("I0 may not add behavioral modules")
    if hierarchy.get("top_remains_composition_only") is not True:
        raise RTL1IManifestError("I0 top must remain composition-only")

    verification = manifest.get("verification")
    if not isinstance(verification, dict):
        raise RTL1IManifestError("verification must be an object")
    labels = verification.get("evidence_labels")
    if not isinstance(labels, list) or "no model/GPU" not in labels or "no PPA claim" not in labels:
        raise RTL1IManifestError("verification labels must preserve no-model/no-PPA boundary")


def _records(manifest: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = manifest.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RTL1IManifestError(f"{key} must be a list of objects")
    return value


def _unique_ids(records: list[dict[str, Any]], label: str) -> frozenset[str]:
    identifiers = [record.get("id") for record in records]
    if not all(isinstance(identifier, str) and identifier for identifier in identifiers):
        raise RTL1IManifestError(f"{label} record lacks id")
    if len(set(identifiers)) != len(identifiers):
        raise RTL1IManifestError(f"duplicate {label} id")
    return frozenset(identifiers)


def _required_strings(record: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if not isinstance(record.get(key), str) or not record[key]:
            raise RTL1IManifestError(f"record {record.get('id')!r} lacks {key}")


def _by_id(records: list[dict[str, Any]], identifier: str) -> dict[str, Any]:
    return next(record for record in records if record["id"] == identifier)
