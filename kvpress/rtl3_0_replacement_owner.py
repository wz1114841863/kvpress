"""No-model validation for the RTL3.0 replacement-owner planning map."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


VERSION = "kvzap-route-a-rtl3-0-replacement-owner-1.0"
STATUS = "implemented_planning_stop_for_review"
RECORD_IDS = (
    "functional_memory_environment",
    "packed_s2_read_association",
    "source_payload_to_partial_provider",
    "r4_functional_merge_provider",
)
STOP_IDS = ("packed_read_association_owner", "partial_provider_query_position_contract")


class RTL30ReplacementOwnerError(ValueError):
    """Raised when RTL3.0 would silently broaden a frozen owner boundary."""


def load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL30ReplacementOwnerError("RTL3.0 manifest root must be an object")
    return value


def _records_by_id(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    records = manifest.get("replacement_records")
    if not isinstance(records, list):
        raise RTL30ReplacementOwnerError("replacement records must be a list")
    by_id = {record.get("id"): record for record in records if isinstance(record, Mapping)}
    if tuple(by_id) != RECORD_IDS or len(by_id) != len(records):
        raise RTL30ReplacementOwnerError("replacement record inventory drift")
    return by_id


def validate(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != VERSION or manifest.get("status") != STATUS:
        raise RTL30ReplacementOwnerError("unexpected RTL3.0 version or status")
    disposition = manifest.get("disposition")
    if disposition != {
        "rtl3_0_replacement_map_complete": True,
        "rtl3_behavioral_activation_authorized": False,
        "next_required_action": "review and resolve the two stop-for-review items before their respective behavioral closures",
    }:
        raise RTL30ReplacementOwnerError("RTL3.0 may not authorize behavioral activation")
    records = _records_by_id(manifest)
    required_fields = {"current_boundary", "replacement", "scoreboard_observations", "environment_assumptions", "dut_guarantees", "post_replacement_prohibition", "forbidden"}
    for record_id, record in records.items():
        if not required_fields <= set(record):
            raise RTL30ReplacementOwnerError(f"replacement record incomplete: {record_id}")
        if not isinstance(record["scoreboard_observations"], list) or not record["scoreboard_observations"]:
            raise RTL30ReplacementOwnerError(f"missing scoreboard observation: {record_id}")

    memory = records["functional_memory_environment"]
    if memory.get("status") != "planned_rtl3_1" or memory["replacement"].get("authority") != "non_authoritative":
        raise RTL30ReplacementOwnerError("functional memory environment authority drift")
    if memory["replacement"].get("interface") != "existing core_mem_if_v1 external init/request/response interface":
        raise RTL30ReplacementOwnerError("functional memory environment must retain core_mem_if_v1")

    packed = records["packed_s2_read_association"]
    if packed.get("status") != "stop_for_review" or packed["replacement"].get("owner") != "UNRESOLVED_STOP_FOR_REVIEW":
        raise RTL30ReplacementOwnerError("packed S2 association must remain explicit stop-for-review")
    if "scheduler selection" not in packed.get("forbidden", []):
        raise RTL30ReplacementOwnerError("packed S2 association must not select a scheduler")

    partial = records["source_payload_to_partial_provider"]
    if partial.get("status") != "stop_for_review" or partial["replacement"].get("owner") != "route_a_functional_attention_partial_provider":
        raise RTL30ReplacementOwnerError("partial-provider ownership drift")
    if set(partial["replacement"].get("source_fact_owners", [])) != {
        "route_a_hot_source_path", "route_a_direct_pending_endpoint_v1", "route_a_s2_gqa_source_wrapper",
    }:
        raise RTL30ReplacementOwnerError("partial source-owner inventory drift")
    if "hidden attention MAC in a storage owner" not in partial.get("forbidden", []):
        raise RTL30ReplacementOwnerError("storage owner must not absorb attention MAC")

    r4 = records["r4_functional_merge_provider"]
    if r4.get("status") != "planned_rtl3_3_to_3_4" or r4["replacement"].get("owner") != "route_a_functional_r4_merge_provider":
        raise RTL30ReplacementOwnerError("R4 functional provider drift")
    observable = r4["replacement"].get("observable_contract", "")
    if "binary32" not in observable or "hot->pending->packed" not in observable:
        raise RTL30ReplacementOwnerError("R4 frozen observable contract missing")

    stops = manifest.get("stop_for_review")
    if not isinstance(stops, list) or tuple(stop.get("id") for stop in stops if isinstance(stop, Mapping)) != STOP_IDS:
        raise RTL30ReplacementOwnerError("stop-for-review inventory drift")
    if {tuple(stop.get("blocks", [])) for stop in stops} != {("rtl3_2",), ("rtl3_5",)}:
        raise RTL30ReplacementOwnerError("stop-for-review blocking scope drift")
    forbidden = set(manifest.get("forbidden", []))
    if not {"production-top completion claim", "numeric RTL completion claim", "new A4 DSE", "pruning admission scheduler or atomic-publication change"} <= forbidden:
        raise RTL30ReplacementOwnerError("RTL3.0 evidence boundary drift")


def validate_hashes(manifest: Mapping[str, Any], root: str | Path) -> None:
    base = Path(root).resolve()
    hashes = manifest.get("source_sha256")
    if not isinstance(hashes, Mapping) or not hashes:
        raise RTL30ReplacementOwnerError("RTL3.0 must hash-bind sources")
    for relative, expected in hashes.items():
        path = (base / str(relative)).resolve()
        if base not in path.parents or not path.is_file() or not isinstance(expected, str) or len(expected) != 64:
            raise RTL30ReplacementOwnerError("invalid RTL3.0 source hash")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RTL30ReplacementOwnerError(f"hash-bound source drift: {relative}")


def load_and_validate(manifest_path: str | Path, root: str | Path) -> None:
    manifest = load(manifest_path)
    validate(manifest)
    validate_hashes(manifest, root)
