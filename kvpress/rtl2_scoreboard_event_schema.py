"""No-model validation for the pre-behavior RTL2 scoreboard-event schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kvpress.rtl2_activation_manifest import REQUIRED_EVENTS, RTL2ActivationManifestError, load_manifest, validate_manifest


SCHEMA_VERSION = "kvzap-route-a-rtl2-scoreboard-event-1.0"
SCHEMA_STATUS = "declared_pre_behavior_no_events_emittable"
REQUIRED_LABELS = frozenset({"no model/GPU", "no PPA claim", "no RTL correctness claim", "no new A4 DSE"})


class RTL2ScoreboardEventSchemaError(ValueError):
    """Raised when the versioned RTL2 event vocabulary drifts from its inventory."""


def load_schema(path: str | Path) -> dict[str, Any]:
    """Load one explicit JSON schema without synthesizing fields or defaults."""
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RTL2ScoreboardEventSchemaError("schema root must be a JSON object")
    return loaded


def validate_schema(schema: dict[str, Any], activation_manifest: dict[str, Any]) -> None:
    """Check schema-only event bindings; this does not emit or validate RTL events."""
    try:
        validate_manifest(activation_manifest)
    except RTL2ActivationManifestError as error:
        raise RTL2ScoreboardEventSchemaError(f"activation manifest is not review-pass valid: {error}") from error
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise RTL2ScoreboardEventSchemaError("unexpected RTL2 scoreboard schema_version")
    if schema.get("status") != SCHEMA_STATUS:
        raise RTL2ScoreboardEventSchemaError("RTL2 scoreboard schema must remain pre-behavior")
    if schema.get("activation_manifest") != "analysis/rtl2_0_activation_manifest.json":
        raise RTL2ScoreboardEventSchemaError("schema must bind the RTL2.0 activation manifest")

    extension = _object(schema, "extends")
    if extension.get("historical_schema") != "analysis/rtl1_v_scoreboard_event_schema.json":
        raise RTL2ScoreboardEventSchemaError("schema must preserve the frozen RTL1-V historical path")
    if extension.get("mode") != "versioned_non_mutating_extension":
        raise RTL2ScoreboardEventSchemaError("schema must be a non-mutating RTL1-V extension")
    if not Path(extension["historical_schema"]).is_file():
        raise RTL2ScoreboardEventSchemaError("frozen RTL1-V schema path does not exist")

    adapter = _object(schema, "adapter")
    if adapter.get("name") != "testbench_route_a_scoreboard_event_adapter_v2":
        raise RTL2ScoreboardEventSchemaError("schema must name the RTL2 testbench scoreboard adapter")
    if adapter.get("state") != "schema_only_not_implemented":
        raise RTL2ScoreboardEventSchemaError("adapter must remain schema-only before behavior activation")

    inventory_by_event = {record["event"]: record for record in _records(activation_manifest, "event_records")}
    records = _records(schema, "event_records")
    by_event = _unique_by_event(records)
    if frozenset(by_event) != REQUIRED_EVENTS:
        raise RTL2ScoreboardEventSchemaError("schema event set differs from the frozen RTL2 activation inventory")
    for event, record in by_event.items():
        _required_string(record, "activation_phase")
        if record.get("emission_state") != "not_emittable_until_named_behavioral_phase":
            raise RTL2ScoreboardEventSchemaError(f"{event} must remain non-emittable before its named phase")
        expected = inventory_by_event[event]
        if record["activation_phase"] != expected["activation_phase"]:
            raise RTL2ScoreboardEventSchemaError(f"{event} activation phase differs from the RTL2 inventory")
        if set(_string_list(record, "carrier_ids")) != set(_string_list(expected, "carrier_ids")):
            raise RTL2ScoreboardEventSchemaError(f"{event} carrier binding differs from the RTL2 inventory")
        expected_owners = _owners(expected)
        if set(_string_list(record, "emitter_owners")) != expected_owners:
            raise RTL2ScoreboardEventSchemaError(f"{event} emitter ownership differs from the RTL2 inventory")
        required_fields = set(_string_list(record, "required_fields"))
        if not set(_string_list(expected, "identity_fields")).issubset(required_fields):
            raise RTL2ScoreboardEventSchemaError(f"{event} drops an inventory identity field")

    forbidden = set(_string_list(schema, "forbidden"))
    for required in (
        "event emission before its named behavioral phase",
        "infer architectural event from arbitrary internal state",
        "rewrite frozen rtl1_v_scoreboard_event_schema.json",
        "raw HBM byte observation",
        "cycle or latency annotation",
    ):
        if required not in forbidden:
            raise RTL2ScoreboardEventSchemaError("schema must retain pre-behavior and evidence-boundary exclusions")
    if not REQUIRED_LABELS.issubset(set(_string_list(schema, "evidence_labels"))):
        raise RTL2ScoreboardEventSchemaError("schema evidence labels must preserve no-model/no-PPA/no-RTL boundaries")


def load_and_validate(schema_path: str | Path, manifest_path: str | Path) -> None:
    """Load both public artifacts and validate their exact pre-behavior binding."""
    validate_schema(load_schema(schema_path), load_manifest(manifest_path))


def _object(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise RTL2ScoreboardEventSchemaError(f"{key} must be a JSON object")
    return value


def _records(parent: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = parent.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RTL2ScoreboardEventSchemaError(f"{key} must be a list of objects")
    return value


def _string_list(parent: dict[str, Any], key: str) -> list[str]:
    value = parent.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise RTL2ScoreboardEventSchemaError(f"{key} must be a nonempty string list")
    return value


def _unique_by_event(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        event = record.get("event")
        if not isinstance(event, str) or not event:
            raise RTL2ScoreboardEventSchemaError("schema record lacks event")
        if event in result:
            raise RTL2ScoreboardEventSchemaError(f"duplicate schema event: {event}")
        result[event] = record
    return result


def _owners(record: dict[str, Any]) -> set[str]:
    if "emitter_owner" in record:
        owner = record["emitter_owner"]
        if not isinstance(owner, str) or not owner:
            raise RTL2ScoreboardEventSchemaError("inventory event has invalid emitter_owner")
        return {owner}
    return set(_string_list(record, "emitter_owners"))


def _required_string(record: dict[str, Any], key: str) -> None:
    if not isinstance(record.get(key), str) or not record[key]:
        raise RTL2ScoreboardEventSchemaError(f"schema record {record.get('event')!r} lacks {key}")
