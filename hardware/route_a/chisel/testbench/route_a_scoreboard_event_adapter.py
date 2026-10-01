"""Executable RTL1-V transaction adapter for frozen Python semantic references.

This host-side adapter consumes only accepted logical events.  It is neither a
cycle simulator nor a raw-HBM monitor, and it does not claim RTL equivalence,
numeric datapath behavior, timing, throughput, or PPA.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from kvpress.route_a_architecture_reference import RouteAArchitectureReference
from kvpress.route_a_core_memory_reference import TransactionIdentity
from kvpress.route_a_lifecycle_adapter_reference import (
    AttentionServiceRequest,
    KVArrival,
    RouteALifecycleAdapterReference,
    SessionRetireRequest,
    SessionStart,
)
from kvpress.route_a_page_manager_reference import RouteAPageManagerReference
from kvpress.route_a_rtl_profile import PAGE_GENERATION_WRAP_QUIESCENCE, PageRef


class ScoreboardEventError(ValueError):
    """Raised when a testbench event is outside the frozen RTL1-V schema."""


@dataclass(frozen=True)
class ScoreboardEvent:
    """One accepted transaction observation, not a cycle-accurate waveform."""

    domain: str
    event: str
    fields: Mapping[str, Any]


class RouteAScoreboardEventAdapter:
    """Dispatch a bounded RTL1-V event vocabulary to existing Python oracles."""

    def __init__(self, repo_root: Path) -> None:
        schema_path = repo_root / "analysis/rtl1_v_scoreboard_event_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema.get("schema_version") != "kvzap-route-a-rtl1-v-scoreboard-event-1.0":
            raise ScoreboardEventError("unexpected RTL1-V scoreboard schema")
        self._required = {
            (record["domain"], record["event"]): frozenset(record["required_fields"])
            for record in schema["event_records"]
        }
        self.authority = RouteAArchitectureReference(logical_admission_credits=1)
        self.pages = RouteAPageManagerReference(page_pool_pages=4, layer_count=1, kv_head_count=1, generation_width=2)
        self.lifecycle = RouteALifecycleAdapterReference()
        self._refs: dict[str, PageRef] = {}
        self._operations: dict[str, str] = {}

    def dispatch(self, observation: ScoreboardEvent) -> object | None:
        key = (observation.domain, observation.event)
        required = self._required.get(key)
        if required is None:
            raise ScoreboardEventError(f"unknown RTL1-V scoreboard event: {key}")
        provided = frozenset(observation.fields)
        if provided != required:
            raise ScoreboardEventError(f"event {key} fields differ: expected {sorted(required)}, got {sorted(provided)}")
        return getattr(self, f"_dispatch_{observation.domain}")(observation.event, observation.fields)

    def operation_id(self, label: str) -> str:
        return self._operations[label]

    def snapshot(self) -> dict[str, object]:
        return {
            "authority": self.authority.snapshot(),
            "page_manager_state": self.pages.state.value,
            "lifecycle_state": self.lifecycle.state.value,
        }

    def _dispatch_authority(self, event: str, f: Mapping[str, Any]) -> object | None:
        if event == "seed_hot": return self.authority.seed_hot(str(f["token"]))
        if event == "mature": return self.authority.mature_hot(str(f["token"]), keep=bool(f["keep"]))
        if event == "open_packed_write": return self.authority.open_packed_write(int(f["request_id"]), str(f["token"]))
        if event == "page_write_commit": return self.authority.page_write_commit(int(f["request_id"]), str(f["token"]))
        if event == "begin_metadata_group": return self.authority.begin_metadata_group(str(f["group_id"]), tuple(f["members"]))
        if event == "stage_metadata_member": return self.authority.stage_metadata_member(str(f["group_id"]), str(f["member"]))
        if event == "metadata_atomic_publish": return self.authority.metadata_atomic_publish(str(f["group_id"]))
        raise AssertionError(event)

    def _dispatch_reclaim(self, event: str, f: Mapping[str, Any]) -> object | None:
        if event == "allocate":
            ref = self.pages.allocate_page(layer=int(f["layer"]), kv_head=int(f["kv_head"]))
            self._refs[str(f["ref"])] = ref
            return ref
        if event == "payload_write_commit": return self.pages.payload_write_commit(self._ref(f["ref"]))
        if event == "descriptor_prepare":
            operations = self.pages.begin_descriptor_prepare(self._ref(f["ref"]), layer=int(f["layer"]), kv_head=int(f["kv_head"]), valid_count=int(f["valid_count"]))
            for operation in operations: self._operations[operation.operation_id] = operation.operation_id
            return tuple(operation.operation_id for operation in operations)
        if event == "descriptor_terminal": return self.pages.complete_descriptor_operation(str(f["operation_id"]), success=bool(f["success"]))
        if event == "metadata_publish": return self.pages.metadata_publish_commit(self._ref(f["ref"]), publication_action=lambda: None)
        if event == "retire": return self.pages.request_retire(self._identity(f))
        if event == "quiesce": return self.pages.mark_page_quiescent(self._ref(f["ref"]), quiescence=PAGE_GENERATION_WRAP_QUIESCENCE)
        if event == "invalidate":
            operation = self.pages.begin_descriptor_invalidate(self._ref(f["ref"]))
            self._operations[operation.operation_id] = operation.operation_id
            return operation.operation_id
        if event == "invalidate_terminal": return self.pages.complete_descriptor_operation(str(f["operation_id"]), success=bool(f["success"]))
        if event == "finish_reclaim": return self.pages.finish_reclaim(self._ref(f["ref"]))
        raise AssertionError(event)

    def _dispatch_lifecycle(self, event: str, f: Mapping[str, Any]) -> object | None:
        if event == "ack_init": return self.lifecycle.acknowledge_init(str(f["acknowledgement"]))
        if event == "session_start": return self.lifecycle.session_start(SessionStart(int(f["session_id"]), int(f["context_tokens"])))
        if event == "kv_arrival": return self.lifecycle.kv_arrival(KVArrival(int(f["entry_id"]), int(f["layer"]), int(f["kv_head"]), int(f["logical_position"]), int(f["payload_ref"])))
        if event == "attention_accept": return self.lifecycle.attention_service_request(AttentionServiceRequest(self._identity(f), int(f["layer"]), int(f["kv_head"]), int(f["query_position"])))
        if event == "gqa_complete": return self.lifecycle.mark_gqa_updates_committed(self._identity(f))
        if event == "terminal": return self.lifecycle.terminal_attention(self._identity(f), success=bool(f["success"]))
        if event == "retire": return self.lifecycle.session_retire(SessionRetireRequest(int(f["session_id"]), self._identity(f)))
        if event == "drain_ack": return self.lifecycle.acknowledge_drain(str(f["acknowledgement"]))
        if event == "retire_ack": return self.lifecycle.retire_ack()
        raise AssertionError(event)

    def _ref(self, label: object) -> PageRef:
        try: return self._refs[str(label)]
        except KeyError as error: raise ScoreboardEventError(f"unknown page-ref label: {label}") from error

    @staticmethod
    def _identity(fields: Mapping[str, Any]) -> TransactionIdentity:
        return TransactionIdentity(request_id=int(fields["request_id"]), incarnation=int(fields["incarnation"]))
