"""No-model validation for the RTL2.0e R3/R5 durability prerequisite."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "kvzap-route-a-rtl2-0e-r3-r5-durability-prerequisite-1.0"
STATUS = "rtl2_0e_descriptor_durability_interface_owner_closed_behavior_pending"
IDENTITY_FIELDS = frozenset({
    "layer",
    "kv_head",
    "page_ref.page_id",
    "page_ref.generation",
    "transaction_group_tag",
})
EXCLUDED = frozenset({
    "descriptor visibility before metadata_publish_commit",
    "authority transition before metadata_publish_commit",
    "R5 allocator free or generation reuse",
    "R2 scheduler or R1 memory path",
    "R4 numeric processing",
    "R6 terminal and retirement handling",
})


class RTL2R3R5DurabilityPrerequisiteError(ValueError):
    """Raised when the R3/R5 prerequisite contract drifts."""


def load_manifest(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL2R3R5DurabilityPrerequisiteError("manifest root must be object")
    return value


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA or manifest.get("status") != STATUS:
        raise RTL2R3R5DurabilityPrerequisiteError("unexpected RTL2.0e manifest identity")
    if "No Chisel carrier behavior" not in str(manifest.get("scope")):
        raise RTL2R3R5DurabilityPrerequisiteError("scope must retain no-behavior boundary")
    for path in _strings(manifest, "contract_references"):
        if not Path(path).is_file():
            raise RTL2R3R5DurabilityPrerequisiteError(f"missing contract reference: {path}")

    mask = _object(manifest, "logical_operation_mask")
    if mask.get("width_bits") != 2:
        raise RTL2R3R5DurabilityPrerequisiteError("descriptor operation mask width differs")
    bits = _records(mask, "bits")
    by_bit = {record.get("bit"): record for record in bits}
    if set(by_bit) != {0, 1} or len(by_bit) != 2:
        raise RTL2R3R5DurabilityPrerequisiteError("descriptor operation bits differ")
    if by_bit[0].get("name") != "new_page" or by_bit[1].get("name") != "tail_link":
        raise RTL2R3R5DurabilityPrerequisiteError("descriptor operation names differ")
    if "required for every allocated append" not in str(by_bit[0].get("required_rule")):
        raise RTL2R3R5DurabilityPrerequisiteError("new_page requirement differs")
    if "requires_tail_link" not in str(by_bit[1].get("required_rule")):
        raise RTL2R3R5DurabilityPrerequisiteError("tail-link requirement differs")
    forbidden = set(_strings(mask, "forbidden_interpretations"))
    if not {"physical descriptor encoding", "R1 request kind", "physical port count"}.issubset(forbidden):
        raise RTL2R3R5DurabilityPrerequisiteError("logical mask physical-boundary exclusions incomplete")

    result = _object(manifest, "result_type")
    if (
        result.get("name") != "DescriptorDurabilityPrerequisite"
        or result.get("producer") != "route_a_page_manager"
        or result.get("consumer") != "route_a_m2_p3_wrapper"
        or result.get("handshake") != "decoupled_ready_valid"
    ):
        raise RTL2R3R5DurabilityPrerequisiteError("R5-to-R3 result ownership or handshake differs")
    fields = set(_strings(result, "fields"))
    if not IDENTITY_FIELDS.issubset(set(_strings(result, "identity_fields"))):
        raise RTL2R3R5DurabilityPrerequisiteError("R5-to-R3 result identity is incomplete")
    if not {
        "required_descriptor_operation_mask",
        "durable_descriptor_operation_mask",
        "descriptor_prepared",
        "status",
    }.issubset(fields):
        raise RTL2R3R5DurabilityPrerequisiteError("R5-to-R3 durable result fields are incomplete")
    if "private descriptor-operation aggregation" not in _strings(result, "producer_owns"):
        raise RTL2R3R5DurabilityPrerequisiteError("R5 aggregation ownership differs")
    if "successful prerequisite recording" not in _strings(result, "consumer_owns"):
        raise RTL2R3R5DurabilityPrerequisiteError("R3 prerequisite ownership differs")
    neither = set(_strings(result, "neither_owns"))
    if not {"descriptor visibility", "pending-to-packed authority transfer", "metadata_publish_commit"}.issubset(neither):
        raise RTL2R3R5DurabilityPrerequisiteError("result must not acquire visibility or authority ownership")

    success = _object(manifest, "success_rule")
    if (
        success.get("status") != "OK"
        or success.get("descriptor_prepared") is not True
        or "durable_descriptor_operation_mask == required_descriptor_operation_mask" not in str(success.get("mask_rule"))
        or "necessary but insufficient" not in str(success.get("effect"))
    ):
        raise RTL2R3R5DurabilityPrerequisiteError("success rule differs")

    fault = _object(manifest, "fault_rule")
    if (
        fault.get("status") != "FAULT"
        or fault.get("descriptor_prepared") is not False
        or "non-publishable" not in str(fault.get("effect"))
        or "cannot later emit successful descriptor_prepared" not in str(fault.get("one_way_rule"))
    ):
        raise RTL2R3R5DurabilityPrerequisiteError("fault rule differs")

    ordering = set(_strings(manifest, "ordering_and_acceptance"))
    for required in (
        "R5 allocation fixes page_ref",
        "only exact accepted final DescriptorMaintenanceTerminal facts",
        "R3 must have accepted an exact success prerequisite",
        "successful prerequisite does not itself emit metadata_publish_visibility_apply",
        "existing nested R3-to-R5 metadata_publish_visibility_apply/ack",
    ):
        if not any(required in item for item in ordering):
            raise RTL2R3R5DurabilityPrerequisiteError(f"ordering rule missing: {required}")

    rejection = _object(manifest, "rejection_and_stall")
    rejected = set(_strings(rejection, "reject_without_mutation"))
    if not {
        "stale page generation",
        "transaction group tag mismatch",
        "durable mask mismatch on success",
        "result after reset or release",
    }.issubset(rejected):
        raise RTL2R3R5DurabilityPrerequisiteError("stale/mismatch rejection is incomplete")
    if "every result field" not in str(rejection.get("ready_low_rule")) or "both owners" not in str(rejection.get("ready_low_rule")):
        raise RTL2R3R5DurabilityPrerequisiteError("ready-low nonmutation differs")

    if not EXCLUDED.issubset(_strings(manifest, "excluded_paths")):
        raise RTL2R3R5DurabilityPrerequisiteError("closure excludes insufficient external ownership")
    follow = _object(manifest, "required_follow_on")
    if (
        follow.get("behavioral_phase") != "rtl2_1b_then_rtl2_1c"
        or "exact R5-to-R3 decoupled carrier" not in str(follow.get("requires"))
        or "nested visibility apply/ack" not in str(follow.get("requires"))
    ):
        raise RTL2R3R5DurabilityPrerequisiteError("follow-on behavior scope differs")
    labels = set(_strings(manifest, "evidence_labels"))
    if not {"no model/GPU", "no PPA claim", "no RTL correctness claim", "no new A4 DSE"}.issubset(labels):
        raise RTL2R3R5DurabilityPrerequisiteError("evidence labels incomplete")


def _object(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise RTL2R3R5DurabilityPrerequisiteError(f"{key} must be object")
    return value


def _records(parent: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = parent.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RTL2R3R5DurabilityPrerequisiteError(f"{key} must be object list")
    return value


def _strings(parent: dict[str, Any], key: str) -> list[str]:
    value = parent.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise RTL2R3R5DurabilityPrerequisiteError(f"{key} must be string list")
    return value
