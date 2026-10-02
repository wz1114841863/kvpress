"""No-model validation for the RTL2.0 activation-owner inventory.

This validates a planning/reporting artifact before production carrier behavior
is enabled.  It is neither an RTL generator nor proof of dataflow behavior,
numerical correctness, timing, throughput, PPA, or performance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "kvzap-route-a-rtl2-0-activation-manifest-1.0"
MANIFEST_STATUS = "rtl2_0_inventory_complete_reviewed_hierarchy_interface_amendments_required"
REQUIRED_EVENTS = frozenset(
    {
        "request_accept", "fragment_deliver", "write_commit", "descriptor_durable",
        "metadata_publish_commit", "authority_transition", "source_deliverable",
        "consumer_partial_commit", "source_release", "merge_request",
        "attention_terminal", "descriptor_invalidate", "page_free", "retire_ack",
    }
)
REQUIRED_AMENDMENTS = frozenset(
    {
        "hot_payload_egress_interface", "admission_publication_ingress_adapter",
        "r2_multi_producer_ingress_interface", "typed_delivery_router",
        "r3_r5_durability_prerequisite_interface", "source_service_packet_adapter",
        "r4_result_stub_provider",
    }
)
REQUIRED_CARRIERS = frozenset(
    {
        "r6_to_r3_admission_context", "hot_to_admission_payload_ingress",
        "admission_to_r3_p3_claim", "admission_to_r5_allocation_request",
        "r3_to_r2_packed_write_candidate", "r2_to_r1_accepted_request",
        "r1_to_r3_packed_write_terminal", "r1_to_r5_descriptor_terminal",
        "r5_descriptor_durable_to_r3", "r3_nested_publication_to_r5",
        "r3_publication_ack_to_r6", "r2_to_typed_delivery_router",
        "source_owner_to_packet_adapter", "r4_to_matching_source_commit",
        "source_owner_release_to_r6", "r6_to_r4_merge_request",
        "r4_to_r6_terminal", "r5_to_r2_descriptor_reclaim_candidate",
        "r5_allocator_release", "r6_to_runtime_retire_ack",
    }
)


class RTL2ActivationManifestError(ValueError):
    """Raised when the RTL2.0 activation inventory drifts or hides ownership."""


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load one manifest without supplying implicit owner/default values."""
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RTL2ActivationManifestError("manifest root must be a JSON object")
    return loaded


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Check the planning inventory; this intentionally cannot PASS RTL2.0."""
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise RTL2ActivationManifestError("unexpected RTL2.0 activation schema_version")
    if manifest.get("status") != MANIFEST_STATUS:
        raise RTL2ActivationManifestError("unexpected RTL2.0 activation status")
    scope = manifest.get("scope")
    if not isinstance(scope, str) or "No payload behavior" not in scope:
        raise RTL2ActivationManifestError("scope must preserve the no-behavior boundary")

    for reference in _string_list(manifest, "contract_references"):
        if not Path(reference).is_file():
            raise RTL2ActivationManifestError(f"contract reference does not exist: {reference!r}")

    top_rule = _object(manifest, "top_rule")
    if top_rule.get("top_module") != "route_a_kv_subsystem_top" or top_rule.get("composition_only") is not True:
        raise RTL2ActivationManifestError("top must remain the composition-only frozen top")
    forbidden = set(_string_list(top_rule, "forbidden"))
    for required in ("top-generated source plan", "top-reconstructed delivery context", "top authority ownership"):
        if required not in forbidden:
            raise RTL2ActivationManifestError("top rule must forbid temporary top ownership")

    schema = _object(manifest, "scoreboard_schema")
    if schema.get("path") != "analysis/rtl2_scoreboard_event_schema.json":
        raise RTL2ActivationManifestError("RTL2 must reserve a versioned scoreboard schema path")
    if schema.get("state") != "required_before_first_behavioral_activation":
        raise RTL2ActivationManifestError("RTL2 schema must precede behavioral activation")
    if schema.get("adapter") != "testbench_route_a_scoreboard_event_adapter_v2":
        raise RTL2ActivationManifestError("RTL2 schema must name its testbench adapter")

    amendments = _records(manifest, "required_amendments")
    amendment_ids = _unique_ids(amendments, "amendment")
    if amendment_ids != REQUIRED_AMENDMENTS:
        raise RTL2ActivationManifestError("required hierarchy/interface amendment inventory differs")
    for amendment in amendments:
        _required_strings(amendment, "id", "kind", "owner", "purpose")
        if amendment["kind"] not in {"hierarchy", "interface", "testbench_boundary"}:
            raise RTL2ActivationManifestError(f"unsupported amendment kind: {amendment['id']}")
        if not _string_list(amendment, "forbidden"):
            raise RTL2ActivationManifestError(f"amendment lacks forbidden constraints: {amendment['id']}")
    router_amendment = next(record for record in amendments if record["id"] == "typed_delivery_router")
    if (
        router_amendment.get("closure_status") != "endpoint_descriptor_contract_closed_router_behavior_pending"
        or router_amendment.get("closure_artifact") != "analysis/rtl2_0d_typed_delivery_router_contract.md"
    ):
        raise RTL2ActivationManifestError("typed delivery router must bind the RTL2.0d endpoint-descriptor closure")
    durability_amendment = next(record for record in amendments if record["id"] == "r3_r5_durability_prerequisite_interface")
    if (
        durability_amendment.get("closure_status") != "descriptor_durability_interface_owner_closed_behavior_pending"
        or durability_amendment.get("closure_artifact") != "analysis/rtl2_0e_r3_r5_durability_prerequisite_contract.md"
    ):
        raise RTL2ActivationManifestError("R3/R5 durability prerequisite must bind the RTL2.0e closure")
    source_adapter_amendment = next(record for record in amendments if record["id"] == "source_service_packet_adapter")
    if (
        source_adapter_amendment.get("closure_status") != "source_service_packet_interface_owner_closed_behavior_pending"
        or source_adapter_amendment.get("closure_artifact") != "analysis/rtl2_0f_source_service_packet_adapter_contract.md"
    ):
        raise RTL2ActivationManifestError("source-service packet adapter must bind the RTL2.0f closure")
    r4_stub_amendment = next(record for record in amendments if record["id"] == "r4_result_stub_provider")
    if (
        r4_stub_amendment.get("closure_status") != "r4_result_stub_interface_owner_closed_testbench_behavior_pending"
        or r4_stub_amendment.get("closure_artifact") != "analysis/rtl2_0g_r4_result_stub_provider_contract.md"
    ):
        raise RTL2ActivationManifestError("R4 result-stub provider must bind the RTL2.0g closure")

    carriers = _records(manifest, "carrier_records")
    if _unique_ids(carriers, "carrier") != REQUIRED_CARRIERS:
        raise RTL2ActivationManifestError("carrier inventory differs from the RTL2.0 closure set")
    carrier_by_id = {record["id"]: record for record in carriers}
    for carrier in carriers:
        _required_strings(carrier, "id", "producer", "consumer", "current_state", "activation_phase", "semantic_event")
        if carrier["activation_phase"] not in {"rtl2_1a", "rtl2_1b", "rtl2_1c", "rtl2_2", "rtl2_4", "rtl2_5", "rtl2_6"}:
            raise RTL2ActivationManifestError(f"carrier has unknown activation phase: {carrier['id']}")
        if carrier["semantic_event"] not in REQUIRED_EVENTS:
            raise RTL2ActivationManifestError(f"carrier has unknown semantic event: {carrier['id']}")
        if not _string_list(carrier, "identity_fields"):
            raise RTL2ActivationManifestError(f"carrier lacks identity fields: {carrier['id']}")
        amendment_id = carrier.get("amendment_id")
        if amendment_id is not None and amendment_id not in amendment_ids:
            raise RTL2ActivationManifestError(f"carrier names unknown amendment: {carrier['id']}")
        if carrier["current_state"] in {"top_inert", "absent_from_frozen_interface", "absent_from_frozen_hierarchy"} and amendment_id is None:
            raise RTL2ActivationManifestError(f"inactive carrier lacks an explicit amendment: {carrier['id']}")
    durability_carrier = carrier_by_id["r5_descriptor_durable_to_r3"]
    if (
        durability_carrier.get("current_state") != "interface_owner_closed_behavior_pending"
        or not {"page_ref", "generation", "layer", "kv_head", "transaction_group_tag"}.issubset(_string_list(durability_carrier, "identity_fields"))
    ):
        raise RTL2ActivationManifestError("R5 descriptor-durable carrier must retain the RTL2.0e exact association")
    source_carrier = carrier_by_id["source_owner_to_packet_adapter"]
    if (
        source_carrier.get("producer") != "matching_source_owner"
        or source_carrier.get("consumer") != "route_a_source_service_packet_adapter"
        or source_carrier.get("current_state") != "interface_owner_closed_behavior_pending"
    ):
        raise RTL2ActivationManifestError("source-service carrier must retain the RTL2.0f source-owner ingress")
    r4_terminal = carrier_by_id["r4_to_r6_terminal"]
    if r4_terminal.get("current_state") != "testbench_boundary_closed_behavior_pending":
        raise RTL2ActivationManifestError("R4-to-R6 terminal must retain the RTL2.0g testbench boundary")

    events = _records(manifest, "event_records")
    if _unique_ids(events, "event") != REQUIRED_EVENTS:
        raise RTL2ActivationManifestError("event inventory differs from the RTL2 contract")
    for event in events:
        _required_strings(event, "event", "adapter_mapping", "activation_phase")
        if "emitter_owner" in event:
            emitters = [event["emitter_owner"]]
        else:
            emitters = _string_list(event, "emitter_owners")
        if not all(isinstance(owner, str) and owner for owner in emitters):
            raise RTL2ActivationManifestError(f"event lacks emitter owner: {event['event']}")
        carrier_ids = _string_list(event, "carrier_ids")
        if not all(carrier_id in carrier_by_id for carrier_id in carrier_ids):
            raise RTL2ActivationManifestError(f"event names unknown carrier: {event['event']}")
        if not _string_list(event, "identity_fields"):
            raise RTL2ActivationManifestError(f"event lacks identity fields: {event['event']}")
        if event["event"] == "metadata_publish_commit":
            if not {"r3_nested_publication_to_r5", "r3_publication_ack_to_r6"}.issubset(carrier_ids):
                raise RTL2ActivationManifestError("metadata publication must retain both frozen nested outputs")
        if event["event"] == "write_commit":
            if not {"r1_to_r3_packed_write_terminal", "r1_to_r5_descriptor_terminal"}.issubset(carrier_ids):
                raise RTL2ActivationManifestError("write commit must distinguish R3 payload and R5 descriptor terminals")

    review = _object(manifest, "review_disposition")
    if review.get("rtl2_0_pass") is not False:
        raise RTL2ActivationManifestError("RTL2.0 must not pass while amendments remain unreviewed")
    _required_strings(review, "reason", "next_action")
    if "top-level temporary producers" not in review["reason"]:
        raise RTL2ActivationManifestError("review disposition must explain why temporary top producers are prohibited")

    labels = set(_string_list(manifest, "evidence_labels"))
    if not {"no model/GPU", "no PPA claim", "no RTL correctness claim", "no new A4 DSE"}.issubset(labels):
        raise RTL2ActivationManifestError("evidence labels must preserve no-model/no-PPA/no-RTL boundaries")


def _object(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise RTL2ActivationManifestError(f"{key} must be a JSON object")
    return value


def _records(parent: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = parent.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RTL2ActivationManifestError(f"{key} must be a list of objects")
    return value


def _string_list(parent: dict[str, Any], key: str) -> list[str]:
    value = parent.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise RTL2ActivationManifestError(f"{key} must be a nonempty string list")
    return value


def _unique_ids(records: list[dict[str, Any]], label: str) -> frozenset[str]:
    identifiers = [record.get("id", record.get("event")) for record in records]
    if not all(isinstance(identifier, str) and identifier for identifier in identifiers):
        raise RTL2ActivationManifestError(f"{label} record lacks id")
    if len(set(identifiers)) != len(identifiers):
        raise RTL2ActivationManifestError(f"duplicate {label} id")
    return frozenset(identifiers)


def _required_strings(record: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if not isinstance(record.get(key), str) or not record[key]:
            raise RTL2ActivationManifestError(f"record {record.get('id', record.get('event'))!r} lacks {key}")
