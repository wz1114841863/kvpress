"""Accepted-carrier event capture and no-model oracle replay for RTL2.6.5c.

This is a testbench-only bridge.  It accepts an explicit observation only when
the named architecture carrier was accepted, validates every schema field, and
then replays the resulting architectural event sequence through the existing
Route-A software references.  It is not a waveform reader, cycle trace,
production-top adapter, numeric model, or RTL-equivalence claim.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from kvpress.route_a_architecture_reference import ContractViolation, RouteAArchitectureReference
from kvpress.route_a_core_memory_reference import TransactionIdentity
from kvpress.rtl2_attention_terminal_scoreboard_binding import (
    AttentionTerminalObservation,
    RouteARTL2AttentionTerminalScoreboardAdapter,
)
from kvpress.rtl2_reclaim_scoreboard_binding import (
    ReclaimScoreboardObservation,
    RouteARTL2ReclaimScoreboardAdapter,
)


CAPTURE_SCHEMA_VERSION = "kvzap-route-a-rtl2-6-5c-event-capture-replay-1.0"
CAPTURE_STATUS = "testbench_accepted_carrier_capture_and_oracle_replay"


class RTL265cEventReplayError(AssertionError):
    """An observation or replay would hide an ownership/semantic violation."""


@dataclass(frozen=True)
class AcceptedCarrierObservation:
    """One named testbench observation; ``accepted`` is the carrier fire fact."""

    event: str
    owner: str
    carrier: str
    accepted: bool
    fields: Mapping[str, int]


@dataclass(frozen=True)
class CapturedEvent:
    """A schema-exact event emitted only after its declared carrier acceptance."""

    event: str
    fields: Mapping[str, int]


def _records_by_name(schema: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    records = schema.get("event_records")
    if not isinstance(records, list):
        raise RTL265cEventReplayError("immutable event schema lacks event records")
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping) or not isinstance(record.get("event"), str):
            raise RTL265cEventReplayError("invalid immutable event record")
        if record["event"] in result:
            raise RTL265cEventReplayError("duplicate immutable event record")
        result[record["event"]] = record
    return result


def load_manifest(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL265cEventReplayError("RTL2.6.5c manifest root must be an object")
    return value


def validate_manifest(manifest: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != CAPTURE_SCHEMA_VERSION or manifest.get("status") != CAPTURE_STATUS:
        raise RTL265cEventReplayError("unexpected RTL2.6.5c capture/replay manifest")
    if manifest.get("base_schema") != "analysis/rtl2_scoreboard_event_schema.json":
        raise RTL265cEventReplayError("capture/replay must bind the immutable RTL2 schema")
    expected = tuple(_records_by_name(schema))
    if tuple(manifest.get("captured_event_order", ())) != expected:
        raise RTL265cEventReplayError("capture/replay must name every immutable event once in schema order")
    forbidden = set(manifest.get("forbidden", ()))
    required_forbidden = {
        "production-top scoreboard adapter",
        "private-state event inference",
        "implicit field default",
        "cycle or latency annotation",
        "numeric datapath or PPA claim",
    }
    if not required_forbidden <= forbidden:
        raise RTL265cEventReplayError("capture/replay forbidden boundary drift")


class AcceptedCarrierCapture:
    """No-default testbench capture boundary for all immutable RTL2 events."""

    def __init__(self, root: str | Path, manifest_path: str | Path | None = None) -> None:
        self._root = Path(root)
        self._schema = json.loads((self._root / "analysis/rtl2_scoreboard_event_schema.json").read_text(encoding="utf-8"))
        self._manifest = load_manifest(manifest_path or self._root / "analysis/rtl2_6_5c_event_capture_replay_manifest.json")
        validate_manifest(self._manifest, self._schema)
        # C4-P0 validates source_sha256 through immutable Git provenance.
        # Capture itself remains a semantic accepted-carrier boundary.
        self._records = _records_by_name(self._schema)

    def capture(self, observation: AcceptedCarrierObservation) -> CapturedEvent:
        record = self._records.get(observation.event)
        if record is None:
            raise RTL265cEventReplayError("unknown immutable event")
        if not observation.accepted:
            raise RTL265cEventReplayError("unaccepted carrier observation cannot emit an event")
        if observation.owner not in tuple(record["emitter_owners"]) or observation.carrier not in tuple(record["carrier_ids"]):
            raise RTL265cEventReplayError("event owner/carrier differs from immutable schema")
        if tuple(observation.fields) != tuple(record["required_fields"]):
            raise RTL265cEventReplayError("captured fields differ from immutable schema")
        if not all(isinstance(value, int) for value in observation.fields.values()):
            raise RTL265cEventReplayError("captured fields must be explicit integers")
        return CapturedEvent(observation.event, dict(observation.fields))

    def capture_many(self, observations: Iterable[AcceptedCarrierObservation]) -> tuple[CapturedEvent, ...]:
        return tuple(self.capture(item) for item in observations)


class RouteARTL265cOracleReplay:
    """Event-level replay with authority and terminal/reclaim oracle delegation."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._reference = RouteAArchitectureReference(request_id_profile="epoch_reuse")
        self._terminal = RouteARTL2AttentionTerminalScoreboardAdapter(self._root)
        self._reclaim = RouteARTL2ReclaimScoreboardAdapter(self._root)
        self._accepted: tuple[int, int] | None = None
        self._write_durable = False
        self._descriptor_durable = False
        self._published = False
        self._source_deliverable = False
        self._commits: set[int] = set()
        self._released = False
        self._merge_requested = False
        self._terminal_seen = False
        self._faulted = False
        self._invalidated = False
        self._freed = False
        self._acked = False

    def replay(self, events: Iterable[CapturedEvent]) -> None:
        for event in events:
            self.dispatch(event)

    def dispatch(self, event: CapturedEvent) -> None:
        fields = event.fields
        if event.event == "request_accept":
            identity = (fields["request_id"], fields["incarnation"])
            if self._accepted is not None or fields["reset_epoch"] < 0:
                raise RTL265cEventReplayError("duplicate or reset-era request acceptance")
            self._accepted = identity
            self._reference.seed_hot("member")
            self._reference.set_mask_decision("member", keep=True)
            self._reference.mature_hot("member")
        elif event.event == "fragment_deliver":
            self._same_identity(fields)
            if fields["status"] != 0:
                self._faulted = True
            elif self._faulted:
                raise RTL265cEventReplayError("success fragment follows fault")
        elif event.event == "write_commit":
            self._same_identity(fields)
            if self._faulted or fields["status"] != 0 or fields["r1_durable"] != 1:
                raise RTL265cEventReplayError("fault/non-durable write cannot become durable")
            if self._write_durable:
                raise RTL265cEventReplayError("duplicate packed write commit")
            request_id, incarnation = self._accepted_or_error()
            self._reference.open_packed_write(request_id, "member", epoch=incarnation)
            self._reference.page_write_commit(request_id, "member", epoch=incarnation)
            self._write_durable = True
        elif event.event == "descriptor_durable":
            if self._faulted or not self._write_durable or self._descriptor_durable:
                raise RTL265cEventReplayError("descriptor durability prerequisite violated")
            self._descriptor_durable = True
        elif event.event == "metadata_publish_commit":
            if self._faulted or not self._write_durable or not self._descriptor_durable or self._published:
                raise RTL265cEventReplayError("publication prerequisite violated")
            self._reference.begin_metadata_group("group", ("member",))
            self._reference.stage_metadata_member("group", "member")
            self._reference.metadata_atomic_publish("group")
            self._published = True
        elif event.event == "authority_transition":
            if not self._published or fields["from_authority"] != 1 or fields["to_authority"] != 2:
                raise RTL265cEventReplayError("authority transition is not pending-to-packed publication")
            if self._reference.authority("member") != "packed":
                raise RTL265cEventReplayError("authority oracle did not reach packed")
        elif event.event == "source_deliverable":
            self._same_identity(fields)
            if not self._published or fields["source_valid"] != 1:
                raise RTL265cEventReplayError("source cannot be deliverable before publication")
            self._source_deliverable = True
        elif event.event == "consumer_partial_commit":
            self._same_identity(fields)
            consumer = fields["consumer_id"]
            if not self._source_deliverable or consumer not in range(4) or consumer in self._commits:
                raise RTL265cEventReplayError("invalid GQA consumer commit")
            self._commits.add(consumer)
        elif event.event == "source_release":
            self._same_identity(fields)
            if not self._source_deliverable or self._commits != {0, 1, 2, 3} or fields["all_four_consumers_committed"] != 1:
                raise RTL265cEventReplayError("source release lacks four committed consumers")
            self._released = True
        elif event.event == "merge_request":
            self._same_identity(fields)
            if not self._released or fields["source_presence"] == 0:
                raise RTL265cEventReplayError("merge request lacks released nonempty source")
            self._merge_requested = True
        elif event.event == "attention_terminal":
            self._same_identity(fields)
            if not self._merge_requested or self._terminal_seen:
                raise RTL265cEventReplayError("terminal lacks one merge request or is duplicated")
            request_id, incarnation = self._accepted_or_error()
            identity = TransactionIdentity(request_id, incarnation)
            self._terminal.arm_attention(identity)
            self._terminal.dispatch(AttentionTerminalObservation("attention_terminal", fields))
            self._terminal_seen = True
            self._faulted |= fields["terminal_status"] == 1
        elif event.event == "descriptor_invalidate":
            if not self._terminal_seen or self._invalidated:
                raise RTL265cEventReplayError("invalidation is not after terminal")
            ref = self._reclaim.arm_reclaim()
            if (fields["page_ref"], fields["generation"]) != (ref.page_id, ref.generation):
                raise RTL265cEventReplayError("reclaim page identity mismatch")
            self._reclaim.dispatch(ReclaimScoreboardObservation("descriptor_invalidate", dict(fields)))
            self._invalidated = True
        elif event.event == "page_free":
            if not self._invalidated or self._freed:
                raise RTL265cEventReplayError("page free precedes durable invalidation")
            self._reclaim.dispatch(ReclaimScoreboardObservation("page_free", dict(fields)))
            self._freed = True
        elif event.event == "retire_ack":
            request_id, incarnation = self._accepted_or_error()
            if not self._freed or self._acked or (fields["request_id"], fields["incarnation"]) != (request_id, incarnation):
                raise RTL265cEventReplayError("retire acknowledgement prerequisite/identity violated")
            self._reclaim.arm_retire_ack(TransactionIdentity(request_id, incarnation))
            self._reclaim.dispatch(ReclaimScoreboardObservation("retire_ack", dict(fields)))
            self._acked = True
        else:
            raise RTL265cEventReplayError("unknown replay event")

    def summary(self) -> dict[str, object]:
        return {"authority": self._reference.authority("member") if self._accepted else None,
                "faulted": self._faulted, "terminal_seen": self._terminal_seen,
                "retire_ack": self._acked, "full_kv_substitution_count": 0}

    def _accepted_or_error(self) -> tuple[int, int]:
        if self._accepted is None:
            raise RTL265cEventReplayError("event lacks an accepted request")
        return self._accepted

    def _same_identity(self, fields: Mapping[str, int]) -> None:
        request_id, incarnation = self._accepted_or_error()
        if (fields.get("request_id"), fields.get("incarnation")) != (request_id, incarnation):
            raise RTL265cEventReplayError("event identity is stale or mismatched")

