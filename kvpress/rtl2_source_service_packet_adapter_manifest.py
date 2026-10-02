"""No-model validation for the RTL2.0f source-service packet adapter."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "kvzap-route-a-rtl2-0f-source-service-packet-adapter-1.0"
STATUS = "rtl2_0f_source_service_packet_interface_owner_closed_behavior_pending"
SOURCES = {
    "hot": ("route_a_hot_source_path", "hot_instance"),
    "pending": ("route_a_direct_pending_endpoint_v1", "pending_instance"),
    "packed": ("route_a_s2_gqa_source_wrapper", "packed_instance"),
}
REQUIRED_EXCLUDED = {
    "functional hot direct-pending or S2 payload storage",
    "source attention partial computation",
    "R4 binary32 arithmetic",
    "ConsumerPartialCommit consumption or SourceRelease creation",
    "R6 merge request or outward terminal creation",
    "authority transition metadata publication or page reclaim",
}


class RTL2SourceServicePacketAdapterError(ValueError):
    """Raised when the source-service packet adapter contract drifts."""


def load_manifest(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL2SourceServicePacketAdapterError("manifest root must be object")
    return value

def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA or manifest.get("status") != STATUS:
        raise RTL2SourceServicePacketAdapterError("unexpected RTL2.0f manifest identity")
    if "No Chisel packet behavior" not in str(manifest.get("scope")):
        raise RTL2SourceServicePacketAdapterError("scope must retain no-behavior boundary")
    for path in _strings(manifest, "contract_references"):
        if not Path(path).is_file():
            raise RTL2SourceServicePacketAdapterError(f"missing contract reference: {path}")

    child = _object(manifest, "child")
    if child.get("name") != "route_a_source_service_packet_adapter" or child.get("parent") != "route_a_kv_subsystem_top":
        raise RTL2SourceServicePacketAdapterError("packet adapter hierarchy differs")
    forbidden = set(_strings(child, "forbidden"))
    if not {
        "top-generated source plan",
        "source replacement or S2-for-direct substitution",
        "adapter-generated absent-source packet",
        "source reorder equivalence claim",
        "header or data mutation",
        "numeric merge",
    }.issubset(forbidden):
        raise RTL2SourceServicePacketAdapterError("packet adapter prohibitions incomplete")
    does_not_own = set(_strings(child, "does_not_own"))
    if not {
        "source plan discovery or source presence",
        "consumer commit counting or source release",
        "R6 merge request or attention terminal",
    }.issubset(does_not_own):
        raise RTL2SourceServicePacketAdapterError("packet adapter ownership boundary incomplete")

    order = _object(manifest, "canonical_source_order")
    if order.get("ordered_kinds") != ["hot", "pending", "packed"] or order.get("codes") != {"hot": 0, "pending": 1, "packed": 2}:
        raise RTL2SourceServicePacketAdapterError("canonical source order differs")
    if "not an execution schedule" not in str(order.get("rule")) or order.get("consumer_order") != "unselected; consumer_id remains a distinct 0..3 owner/R4 association":
        raise RTL2SourceServicePacketAdapterError("source/consumer ordering boundary differs")

    owners = _records(manifest, "source_owners")
    by_source = {record.get("source_kind"): record for record in owners}
    if set(by_source) != set(SOURCES) or len(by_source) != len(owners):
        raise RTL2SourceServicePacketAdapterError("source owner inventory differs")
    for kind, (producer, instance_field) in SOURCES.items():
        record = by_source[kind]
        if record.get("producer") != producer or record.get("plan_instance_field") != instance_field:
            raise RTL2SourceServicePacketAdapterError(f"source owner differs: {kind}")

    plan = _object(manifest, "accepted_plan_copy")
    if plan.get("producer") != "route_a_lifecycle_adapter" or plan.get("consumer") != child["name"]:
        raise RTL2SourceServicePacketAdapterError("accepted plan ownership differs")
    if not {"transaction_identity", "source_presence", "hot_instance", "pending_instance", "packed_instance"}.issubset(_strings(plan, "fields")):
        raise RTL2SourceServicePacketAdapterError("accepted plan fields incomplete")
    if "R6-accepted nonempty plan" not in str(plan.get("rule")) or not {"adapter plan creation", "empty plan acceptance"}.issubset(_strings(plan, "forbidden")):
        raise RTL2SourceServicePacketAdapterError("accepted plan boundary differs")

    ingress = _object(manifest, "source_packet_ingress")
    if ingress.get("offer_name") != "SourceServicePartialOffer" or ingress.get("fragment_name") != "SourceServiceValueFragment":
        raise RTL2SourceServicePacketAdapterError("source packet type names differ")
    if not {"transaction_identity", "source_instance", "consumer_id", "r4_header_128b", "partial_present"}.issubset(_strings(ingress, "offer_fields")):
        raise RTL2SourceServicePacketAdapterError("source offer fields incomplete")
    if not {"transaction_identity", "source_instance", "consumer_id", "fragment_index_3b", "last", "data_512b"}.issubset(_strings(ingress, "fragment_fields")):
        raise RTL2SourceServicePacketAdapterError("source fragment fields incomplete")
    if "partial_present must be true" not in str(ingress.get("offer_rule")) or "exactly fragments 0..7" not in str(ingress.get("present_fragment_rule")):
        raise RTL2SourceServicePacketAdapterError("source offer presence/fragment rule differs")
    if "does not synthesize an absent partial" not in str(ingress.get("absent_rule")):
        raise RTL2SourceServicePacketAdapterError("absent source generation boundary differs")

    egress = _object(manifest, "r4_packet_egress")
    if egress.get("header_sideband_handshake") != "atomic ready_valid pair":
        raise RTL2SourceServicePacketAdapterError("R4 header/sideband handshake differs")
    if not {"R4PartialHeader.header_128b", "R4SourceInstanceSideband.source_instance", "R4SourceInstanceSideband.consumer_id"}.issubset(_strings(egress, "header_fields")):
        raise RTL2SourceServicePacketAdapterError("R4 header/sideband fields incomplete")
    if not {"R4ValueFragment.fragment_index_3b", "R4ValueFragment.last", "R4ValueFragment.data_512b"}.issubset(_strings(egress, "fragment_fields")):
        raise RTL2SourceServicePacketAdapterError("R4 fragment fields incomplete")
    structural = set(_strings(egress, "structural_checks"))
    if not {
        "header source ordinal equals source_instance.source_kind",
        "header consumer ID equals consumer_id",
        "merge instance is zero",
        "reserved header bits are zero",
        "present header declares eight fragments",
    }.issubset(structural):
        raise RTL2SourceServicePacketAdapterError("R4 structural checks incomplete")

    completion = _object(manifest, "commit_release_association")
    if completion.get("r4_commit_producer") != "route_a_merge_boundary" or completion.get("commit_consumer") != "matching source owner through existing top demultiplexer":
        raise RTL2SourceServicePacketAdapterError("commit demultiplexing differs")
    if "adapter does not consume ConsumerPartialCommit" not in str(completion.get("rule")) or "R6 alone compares exact SourceRelease" not in str(completion.get("r6_rule")):
        raise RTL2SourceServicePacketAdapterError("commit/release owner boundary differs")

    rejection = _object(manifest, "rejection_and_stall")
    rejected = set(_strings(rejection, "reject_without_mutation"))
    if not {
        "stale source generation",
        "source instance mismatch with accepted plan",
        "offer from absent source-plan bit",
        "header source or consumer mismatch",
        "duplicate consumer association",
        "malformed fragment ordinal or last",
        "post-reset association",
    }.issubset(rejected):
        raise RTL2SourceServicePacketAdapterError("source packet rejection boundary incomplete")
    ready_low = str(rejection.get("ready_low_rule"))
    if "every held identity" not in ready_low or "no source ownership, release, authority, or terminal state changes" not in ready_low:
        raise RTL2SourceServicePacketAdapterError("ready-low nonmutation differs")

    if not REQUIRED_EXCLUDED.issubset(_strings(manifest, "excluded_paths")):
        raise RTL2SourceServicePacketAdapterError("source adapter exclusion boundary incomplete")
    follow = _object(manifest, "required_follow_on")
    if follow.get("behavioral_phase") != "rtl2_4" or "all seven nonempty source masks" not in str(follow.get("requires")):
        raise RTL2SourceServicePacketAdapterError("RTL2.4 follow-on differs")
    labels = set(_strings(manifest, "evidence_labels"))
    if not {"no model/GPU", "no PPA claim", "no RTL correctness claim", "no new A4 DSE"}.issubset(labels):
        raise RTL2SourceServicePacketAdapterError("evidence labels incomplete")


def _object(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise RTL2SourceServicePacketAdapterError(f"{key} must be object")
    return value


def _records(parent: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = parent.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RTL2SourceServicePacketAdapterError(f"{key} must be object list")
    return value


def _strings(parent: dict[str, Any], key: str) -> list[str]:
    value = parent.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise RTL2SourceServicePacketAdapterError(f"{key} must be string list")
    return value
