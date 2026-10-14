"""Testbench-only RTL2.5.5 binding for R5 reclaim and R6 retire events.

This module is an architecture-event oracle.  It models no controller timing,
numeric datapath, HBM transaction, physical allocator, or RTL equivalence.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kvpress.route_a_core_memory_reference import TransactionIdentity
from kvpress.route_a_lifecycle_adapter_reference import INIT_ACKS, RETIRE_DRAIN_ACKS, RouteALifecycleAdapterReference, SessionRetireRequest
from kvpress.route_a_page_manager_reference import DescriptorOperationKind, RouteAPageManagerReference
from kvpress.route_a_rtl_profile import PAGE_GENERATION_WRAP_QUIESCENCE, PageRef


class ReclaimScoreboardBindingError(AssertionError):
    """The named event carrier or its reference-oracle mirror drifted."""


@dataclass(frozen=True)
class ReclaimScoreboardObservation:
    name: str
    fields: dict[str, int]


_EXPECTED = {
    "descriptor_invalidate": ("route_a_page_manager", "r5_to_r2_descriptor_reclaim_candidate", ("page_ref", "generation", "descriptor_operation", "delivery_context_ref")),
    "page_free": ("route_a_page_manager", "r5_allocator_release", ("page_ref", "generation")),
    "retire_ack": ("route_a_lifecycle_adapter", "r6_to_runtime_retire_ack", ("session_id", "request_id", "incarnation")),
}


def load_binding(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_binding(binding: dict[str, Any], schema: dict[str, Any], overlay: dict[str, Any]) -> None:
    if binding.get("status") != "active_testbench_reclaim_and_retire_events_bound":
        raise ReclaimScoreboardBindingError("binding status is not active")
    records = {record["event"]: record for record in schema["event_records"]}
    overrides = {record["event"]: record for record in overlay["overrides"]}
    bound = {record["name"]: record for record in binding["events"]}
    if set(bound) != set(_EXPECTED):
        raise ReclaimScoreboardBindingError("binding event set drift")
    for name, (owner, carrier, fields) in _EXPECTED.items():
        record, event, phase = records.get(name), bound[name], overrides.get(name)
        if record is None or phase is None:
            raise ReclaimScoreboardBindingError(f"missing schema/phase record for {name}")
        if tuple(record["emitter_owners"]) != (owner,) or tuple(record["carrier_ids"]) != (carrier,):
            raise ReclaimScoreboardBindingError(f"origin owner/carrier drift for {name}")
        if tuple(record["required_fields"]) != fields or tuple(event["required_fields"]) != fields:
            raise ReclaimScoreboardBindingError(f"required fields drift for {name}")
        if phase["emission_state"] != "bound_and_emittable_in_rtl2_5_5_test_harness":
            raise ReclaimScoreboardBindingError(f"phase binding missing for {name}")


class RouteARTL2ReclaimScoreboardAdapter:
    """Explicit event mirror; setup facts are supplied by the testbench."""
    def __init__(self, root: Path) -> None:
        binding = load_binding(root / "analysis" / "rtl2_5_5_active_state_scoreboard_binding.json")
        validate_binding(binding, json.loads((root / "analysis" / "rtl2_scoreboard_event_schema.json").read_text()), json.loads((root / "analysis" / "rtl2_scoreboard_event_phase_reconciliation_01.json").read_text()))
        # C4-P0 replays the frozen source hashes at their immutable Git
        # revision; this descendant adapter validates only binding semantics.
        self._r5 = RouteAPageManagerReference(page_pool_pages=4, layer_count=1, kv_head_count=1, generation_width=2)
        self._r6 = RouteALifecycleAdapterReference()
        self._reclaim_ref: PageRef | None = None
        self._invalidate_seen = False
        self._page_free_seen = False
        self._retire_armed: TransactionIdentity | None = None

    def arm_reclaim(self) -> PageRef:
        if self._reclaim_ref is not None:
            raise ReclaimScoreboardBindingError("reclaim mirror already armed")
        ref = self._r5.allocate_page(layer=0, kv_head=0)
        self._r5.payload_write_commit(ref)
        for operation in self._r5.begin_descriptor_prepare(ref, layer=0, kv_head=0, valid_count=1):
            self._r5.complete_descriptor_operation(operation.operation_id, success=True)
        self._r5.atomic_metadata_publish(ref, publication_action=lambda: None)
        self._r5.request_retire(TransactionIdentity(0, 0))
        self._r5.mark_page_quiescent(ref, quiescence=PAGE_GENERATION_WRAP_QUIESCENCE)
        self._reclaim_ref = ref
        return ref

    def arm_retire_ack(self, identity: TransactionIdentity) -> None:
        for acknowledgement in INIT_ACKS:
            self._r6.acknowledge_init(acknowledgement)
        self._r6.session_start(__import__("kvpress.route_a_lifecycle_adapter_reference", fromlist=["SessionStart"]).SessionStart(0, 32768))
        self._r6.session_retire(SessionRetireRequest(0, identity))
        for acknowledgement in RETIRE_DRAIN_ACKS:
            self._r6.acknowledge_drain(acknowledgement)
        self._retire_armed = identity

    def dispatch(self, observation: ReclaimScoreboardObservation) -> None:
        expected = _EXPECTED.get(observation.name)
        if expected is None or tuple(observation.fields) != expected[2]:
            raise ReclaimScoreboardBindingError("unknown event or fields differ")
        if observation.name == "descriptor_invalidate":
            self._descriptor_invalidate(observation.fields)
        elif observation.name == "page_free":
            self._page_free(observation.fields)
        else:
            self._retire_ack(observation.fields)

    def _expect_ref(self, fields: dict[str, int]) -> PageRef:
        ref = self._reclaim_ref
        if ref is None or fields["page_ref"] != ref.page_id or fields["generation"] != ref.generation:
            raise ReclaimScoreboardBindingError("page reference/generation mismatch")
        return ref

    def _descriptor_invalidate(self, fields: dict[str, int]) -> None:
        ref = self._expect_ref(fields)
        if self._invalidate_seen or fields["descriptor_operation"] != 2 or fields["delivery_context_ref"] != 0:
            raise ReclaimScoreboardBindingError("invalid descriptor-invalidate observation")
        operation = self._r5.begin_descriptor_invalidate(ref)
        if operation.kind is not DescriptorOperationKind.INVALIDATE:
            raise ReclaimScoreboardBindingError("reference operation kind drift")
        self._r5.complete_descriptor_operation(operation.operation_id, success=True)
        self._invalidate_seen = True

    def _page_free(self, fields: dict[str, int]) -> None:
        ref = self._expect_ref(fields)
        if not self._invalidate_seen or self._page_free_seen:
            raise ReclaimScoreboardBindingError("page free is not after exactly one durable invalidation")
        self._r5.finish_reclaim(ref)
        self._page_free_seen = True

    def _retire_ack(self, fields: dict[str, int]) -> None:
        identity = self._retire_armed
        if identity is None or (fields["session_id"], fields["request_id"], fields["incarnation"]) != (0, identity.request_id, identity.incarnation):
            raise ReclaimScoreboardBindingError("retire acknowledgement identity mismatch")
        if self._r6.retire_ack().identity != identity:
            raise ReclaimScoreboardBindingError("retire acknowledgement oracle drift")
        self._retire_armed = None
