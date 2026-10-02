"""No-model validation for the RTL2.1a retained-group activation record."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "kvzap-route-a-rtl2-1a-retained-group-admission-1.0"
STATUS = "rtl2_1a_control_association_implemented_directed_tested"
REQUIRED_DEFERRED = frozenset({
    "hot_payload_materialization_or_egress", "p3_fragment_or_sidecar", "r2_or_r1_traffic",
    "descriptor_terminal_or_durability", "metadata_publish_commit", "packed_authority_or_read",
    "s2_direct_or_r4_service",
})


class RTL21AManifestError(ValueError):
    """Raised when RTL2.1a expands past its retained-group control scope."""


def load_manifest(path: str | Path) -> dict[str, Any]:
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RTL21AManifestError("manifest root must be a JSON object")
    return loaded


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != STATUS:
        raise RTL21AManifestError("unexpected RTL2.1a manifest version or status")
    for reference in _string_list(manifest, "contract_references"):
        if not Path(reference).is_file():
            raise RTL21AManifestError(f"contract reference does not exist: {reference!r}")
    implementation = _object(manifest, "implementation")
    if implementation.get("child") != "route_a_admission_publication_ingress_adapter" or implementation.get("parent") != "route_a_kv_subsystem_top":
        raise RTL21AManifestError("RTL2.1a must bind the one reviewed child beneath the frozen top")
    for key in ("source", "top_source", "test"):
        value = implementation.get(key)
        if not isinstance(value, str) or not Path(value).is_file():
            raise RTL21AManifestError(f"RTL2.1a implementation {key} does not exist")

    anchor = _object(manifest, "anchor")
    if anchor.get("max_active_groups") != 1 or anchor.get("max_group_members") != 64 or anchor.get("p3_reservation_owner_value") != 0:
        raise RTL21AManifestError("RTL2.1a must retain the one-packer 64-record reservation anchor")
    rule = _object(manifest, "input_rule")
    if rule.get("context_and_authority_atomic") is not True or rule.get("only_authority_edge") != "hot_to_pending":
        raise RTL21AManifestError("RTL2.1a must accept only atomic hot-to-pending RETAIN pairs")
    required_fields = {"entry_id", "layer", "kv_head", "logical_position", "payload_ref", "transaction_group_tag", "group_member_ordinal", "group_valid_records"}
    if not required_fields.issubset(set(_string_list(rule, "preserved_fields"))):
        raise RTL21AManifestError("RTL2.1a must preserve every immutable group association field")

    expected_order = [
        "all_unique_ordinals_0_to_valid_records_minus_1_present",
        "r5_allocation_request_and_matching_response",
        "r3_p3_claim_and_matching_layer_acknowledgement",
        "one_exact_R3_context_authority_pair_relay_per_ordinal",
    ]
    if _string_list(manifest, "ordered_prerequisites") != expected_order:
        raise RTL21AManifestError("RTL2.1a prerequisite ordering differs from the reviewed contract")
    authority = _object(manifest, "authority")
    if authority.get("before_and_after_rtl2_1a") != "pending_only_for_retained_live_token" or authority.get("adapter_authority_owner") is not False:
        raise RTL21AManifestError("RTL2.1a must preserve pending authority without making the adapter an owner")
    if not {"pending_to_packed", "metadata_publish_commit", "packed_readable"}.issubset(set(_string_list(authority, "forbidden_until_later_phase"))):
        raise RTL21AManifestError("RTL2.1a must keep publication and packed authority deferred")
    if set(_string_list(manifest, "inactive_or_deferred")) != REQUIRED_DEFERRED:
        raise RTL21AManifestError("RTL2.1a deferred scope differs from the reviewed boundary")
    labels = set(_string_list(manifest, "evidence_labels"))
    if not {"no model/GPU", "no cycle/timing/throughput claim", "no PPA claim", "no new A4 DSE"}.issubset(labels):
        raise RTL21AManifestError("RTL2.1a evidence labels have drifted")


def _object(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise RTL21AManifestError(f"{key} must be a JSON object")
    return value


def _string_list(parent: dict[str, Any], key: str) -> list[str]:
    value = parent.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise RTL21AManifestError(f"{key} must be a nonempty string list")
    return value
