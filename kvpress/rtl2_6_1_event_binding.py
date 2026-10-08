"""No-model field-provenance contract for the ten unbound RTL2 events.

This is deliberately a testbench observation contract, not a waveform reader,
RTL event emitter, controller model, or production-top component.  A later
RTL2.6.2 harness must connect its declared observation points to real owner
carriers before the completion review can count these events as emittable.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


BINDING_SCHEMA_VERSION = "kvzap-route-a-rtl2-6-1-event-field-binding-1.0"
BINDING_STATUS = "field_provenance_contract_closed_chisel_capture_pending"
UNBOUND_EVENTS = (
    "request_accept", "fragment_deliver", "write_commit", "descriptor_durable",
    "metadata_publish_commit", "authority_transition", "source_deliverable",
    "consumer_partial_commit", "source_release", "merge_request",
)
ALLOWED_PROVENANCE_KINDS = frozenset({"accepted_carrier_field", "accepted_carrier_predicate"})


class RTL26EventBindingError(ValueError):
    """Raised when a field binding would hide ownership or create a default."""


@dataclass(frozen=True)
class RTL26EventObservation:
    """One explicit testbench-captured architectural event, never a cycle trace."""

    event: str
    fields: Mapping[str, int]


def load_binding(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL26EventBindingError("RTL2.6.1 binding root must be an object")
    return value


def validate_binding(binding: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    """Validate exact provenance without declaring an RTL capture implemented."""
    if binding.get("schema_version") != BINDING_SCHEMA_VERSION:
        raise RTL26EventBindingError("unexpected RTL2.6.1 binding schema version")
    if binding.get("status") != BINDING_STATUS:
        raise RTL26EventBindingError("RTL2.6.1 must remain capture-pending")
    if binding.get("base_schema") != "analysis/rtl2_scoreboard_event_schema.json":
        raise RTL26EventBindingError("binding must name the immutable RTL2 schema")
    if binding.get("capture_boundary") != "rtl2_6_2_composed_testbench_harness":
        raise RTL26EventBindingError("binding must defer real-carrier capture to RTL2.6.2")

    schema_by_event = _records_by_event(schema.get("event_records"), "schema")
    expected = set(UNBOUND_EVENTS)
    records = _records_by_event(binding.get("event_bindings"), "binding")
    if set(records) != expected:
        raise RTL26EventBindingError("RTL2.6.1 must bind exactly the ten previously unbound events")

    for event_name in UNBOUND_EVENTS:
        schema_record = schema_by_event.get(event_name)
        record = records[event_name]
        if schema_record is None:
            raise RTL26EventBindingError(f"immutable schema lacks {event_name}")
        if tuple(record.get("origin_owners", ())) != tuple(schema_record.get("emitter_owners", ())):
            raise RTL26EventBindingError(f"origin owner drift for {event_name}")
        if tuple(record.get("origin_carriers", ())) != tuple(schema_record.get("carrier_ids", ())):
            raise RTL26EventBindingError(f"origin carrier drift for {event_name}")
        required_fields = tuple(schema_record.get("required_fields", ()))
        if tuple(record.get("required_fields", ())) != required_fields:
            raise RTL26EventBindingError(f"required field order drift for {event_name}")
        if record.get("capture_status") != "contract_bound_chisel_capture_pending":
            raise RTL26EventBindingError(f"{event_name} must not claim a Chisel capture before RTL2.6.2")
        provenance = record.get("field_provenance")
        if not isinstance(provenance, list) or len(provenance) != len(required_fields):
            raise RTL26EventBindingError(f"{event_name} needs one explicit provenance entry per required field")
        observed_fields = set()
        for source in provenance:
            if not isinstance(source, Mapping):
                raise RTL26EventBindingError(f"{event_name} provenance entry must be an object")
            field = source.get("field")
            kind = source.get("kind")
            carrier = source.get("carrier")
            expression = source.get("expression")
            if field not in required_fields or field in observed_fields:
                raise RTL26EventBindingError(f"{event_name} has missing or duplicate field provenance")
            if kind not in ALLOWED_PROVENANCE_KINDS:
                raise RTL26EventBindingError(f"{event_name}.{field} uses an unapproved provenance kind")
            if carrier not in record["origin_carriers"]:
                raise RTL26EventBindingError(f"{event_name}.{field} names a non-origin carrier")
            if not isinstance(expression, str) or not expression or "internal" in expression.lower() or "default" in expression.lower():
                raise RTL26EventBindingError(f"{event_name}.{field} hides an internal/default source")
            if kind == "accepted_carrier_predicate" and "accepted" not in expression.lower():
                raise RTL26EventBindingError(f"{event_name}.{field} predicate must be acceptance-qualified")
            observed_fields.add(field)

    forbidden = binding.get("forbidden")
    if not isinstance(forbidden, list) or not {
        "infer event from arbitrary internal state",
        "implicit field default",
        "production-top scoreboard adapter",
        "change immutable RTL2 event schema",
    }.issubset(set(forbidden)):
        raise RTL26EventBindingError("RTL2.6.1 forbidden boundary drift")


def validate_source_hashes(binding: Mapping[str, Any], repo_root: str | Path) -> None:
    sources = binding.get("source_sha256")
    if not isinstance(sources, Mapping) or not sources:
        raise RTL26EventBindingError("binding must hash-bind reviewed sources")
    root = Path(repo_root).resolve()
    for relative, expected in sources.items():
        if not isinstance(relative, str) or not isinstance(expected, str) or len(expected) != 64:
            raise RTL26EventBindingError("invalid source hash entry")
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file():
            raise RTL26EventBindingError(f"hash-bound source unavailable: {relative}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RTL26EventBindingError(f"hash-bound source drift: {relative}")


class RouteARTL26EventFieldBindingAdapter:
    """Validate exact captured fields without supplying omitted values.

    RTL2.6.2 will feed this adapter from real owner-carrier observations.  The
    adapter deliberately cannot infer a field from private RTL state or fill a
    value missing from a captured record.
    """

    def __init__(self, repo_root: str | Path, binding_path: str | Path | None = None) -> None:
        root = Path(repo_root)
        binding = load_binding(binding_path or root / "analysis/rtl2_6_1_event_binding_manifest.json")
        schema = json.loads((root / "analysis/rtl2_scoreboard_event_schema.json").read_text(encoding="utf-8"))
        validate_binding(binding, schema)
        validate_source_hashes(binding, root)
        self._fields = {record["event"]: tuple(record["required_fields"]) for record in binding["event_bindings"]}

    def capture(self, observation: RTL26EventObservation) -> RTL26EventObservation:
        expected = self._fields.get(observation.event)
        if expected is None:
            raise RTL26EventBindingError("event is not in the RTL2.6.1 binding set")
        if tuple(observation.fields) != expected:
            raise RTL26EventBindingError("captured fields differ from the immutable event schema")
        if not all(isinstance(value, int) for value in observation.fields.values()):
            raise RTL26EventBindingError("captured event fields must be explicit integers")
        return observation


def _records_by_event(value: Any, label: str) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, list):
        raise RTL26EventBindingError(f"{label} records must be a list")
    records: dict[str, Mapping[str, Any]] = {}
    for record in value:
        if not isinstance(record, Mapping) or not isinstance(record.get("event"), str):
            raise RTL26EventBindingError(f"{label} record lacks event")
        if record["event"] in records:
            raise RTL26EventBindingError(f"duplicate {label} event: {record['event']}")
        records[record["event"]] = record
    return records
