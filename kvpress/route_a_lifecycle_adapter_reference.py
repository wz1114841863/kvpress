"""Pure-software R6 generic lifecycle-adapter and top-level graph reference.

This module closes only finite adapter ports, ownership handoff, session/reset,
and module-drain dependencies for the Route-A Qwen anchor. It is not RTL, a
controller/FSM implementation, a timing model, or a model/GPU workload.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum

from kvpress.route_a_architecture_reference import CANONICAL_SOURCE_ORDER
from kvpress.route_a_core_memory_reference import TransactionIdentity


ANCHOR_CONTEXT_TOKENS = 32_768
ANCHOR_LAYERS = 36
ANCHOR_KV_HEADS = 8
HOT_WINDOW_TOKENS = 128
SESSION_ID_WIDTH = 1
ENTRY_ID_WIDTH = 24
PAYLOAD_REF_WIDTH = 64
RID_WIDTH = 3
INCARNATION_WIDTH = 2

INIT_ACKS = frozenset({"mem_init_done", "m2_p3_init_done", "page_manager_init_done"})
RETIRE_DRAIN_ACKS = frozenset(
    {
        "r1_memory_transactions_drained",
        "r2_payload_arbiter_drained",
        "r2_descriptor_maintenance_drained",
        "r3_m2_p3_drained",
        "r5_page_manager_descriptor_ops_drained",
        "s2_gqa_source_drained",
        "direct_pending_endpoint_drained",
        "merge_wrapper_drained",
    }
)


class LifecycleAdapterViolation(AssertionError):
    """A generic lifecycle adapter event violates the selected R6 contract."""


class AdapterBackpressure(LifecycleAdapterViolation):
    """A legal adapter ready-low event delayed a request without mutation."""


class AdapterState(str, Enum):
    RESET = "reset"
    IDLE = "idle"
    ACTIVE = "active"
    RETIRING = "retiring"
    RETIRED = "retired"


class RetentionDisposition(str, Enum):
    RETAIN = "retain"
    DROP = "drop"


class AuthorityState(str, Enum):
    HOT = "hot"
    PENDING = "pending"
    PACKED = "packed"


@dataclass(frozen=True)
class SessionStart:
    session_id: int
    context_tokens: int


@dataclass(frozen=True)
class KVArrival:
    entry_id: int
    layer: int
    kv_head: int
    logical_position: int
    payload_ref: int


@dataclass(frozen=True)
class MaturityDisposition:
    entry_id: int
    disposition: RetentionDisposition


@dataclass(frozen=True)
class AttentionServiceRequest:
    identity: TransactionIdentity
    layer: int
    kv_head: int
    query_position: int


@dataclass(frozen=True)
class SessionRetireRequest:
    session_id: int
    identity: TransactionIdentity


@dataclass(frozen=True)
class AttentionDispatchPlan:
    identity: TransactionIdentity
    sources: tuple[str, ...]


@dataclass
class _Entry:
    arrival: KVArrival
    authority: AuthorityState = AuthorityState.HOT
    disposition: RetentionDisposition | None = None


class RouteALifecycleAdapterReference:
    """Event-level R6 adapter; it does not choose any module implementation."""

    def __init__(self) -> None:
        self._state = AdapterState.RESET
        self._init_acks: set[str] = set()
        self._entries: dict[int, _Entry] = {}
        self._stream_high_water: dict[tuple[int, int], int] = {}
        self._live_attention: set[TransactionIdentity] = set()
        self._merge_eligible: set[TransactionIdentity] = set()
        self._retire: SessionRetireRequest | None = None
        self._drain_acks: set[str] = set()
        self._stalls: set[str] = set()

    @property
    def state(self) -> AdapterState:
        return self._state

    @staticmethod
    def derived_entry_id(*, layer: int, kv_head: int, logical_position: int) -> int:
        RouteALifecycleAdapterReference._validate_coordinate(layer, kv_head, logical_position)
        return ((logical_position * ANCHOR_LAYERS) + layer) * ANCHOR_KV_HEADS + kv_head

    @staticmethod
    def public_port_field_names() -> frozenset[str]:
        """Names visible at the generic frontend boundary; scores stay outside."""
        return frozenset(
            name
            for port in (SessionStart, KVArrival, MaturityDisposition, AttentionServiceRequest, SessionRetireRequest)
            for name in (field.name for field in fields(port))
        )

    def acknowledge_init(self, acknowledgement: str) -> None:
        self._require(self._state is AdapterState.RESET, "initialization acknowledgement requires reset state")
        self._require(acknowledgement in INIT_ACKS, "unknown R6 initialization acknowledgement")
        self._init_acks.add(acknowledgement)
        if self._init_acks == INIT_ACKS:
            self._state = AdapterState.IDLE

    def set_stall(self, event: str, *, stalled: bool) -> None:
        self._require(event in {"session_start", "kv_arrival", "maturity_disposition", "attention_service", "session_retire"}, "unknown generic adapter event")
        if stalled:
            self._stalls.add(event)
        else:
            self._stalls.discard(event)

    def session_start(self, request: SessionStart) -> None:
        self._delay_if_stalled("session_start")
        self._require(self._state is AdapterState.IDLE, "session start requires initialized idle state")
        self._require(request.session_id == 0 and request.context_tokens == ANCHOR_CONTEXT_TOKENS, "session start exceeds the selected R6 anchor")
        self._entries.clear()
        self._stream_high_water.clear()
        self._live_attention.clear()
        self._retire = None
        self._drain_acks.clear()
        self._state = AdapterState.ACTIVE

    def kv_arrival(self, arrival: KVArrival) -> None:
        self._delay_if_stalled("kv_arrival")
        self._require(self._state is AdapterState.ACTIVE, "KV arrival requires an active session")
        self._validate_coordinate(arrival.layer, arrival.kv_head, arrival.logical_position)
        self._require(0 <= arrival.payload_ref < 2**PAYLOAD_REF_WIDTH, "payload_ref exceeds the selected opaque width")
        self._require(arrival.entry_id == self.derived_entry_id(layer=arrival.layer, kv_head=arrival.kv_head, logical_position=arrival.logical_position), "entry_id does not match the selected coordinate derivation")
        self._require(arrival.entry_id not in self._entries, "KV entry may arrive exactly once")
        stream = (arrival.layer, arrival.kv_head)
        prior = self._stream_high_water.get(stream)
        self._require(prior is None or arrival.logical_position > prior, "KV arrival must be position-monotonic within one stream")
        self._entries[arrival.entry_id] = _Entry(arrival)
        self._stream_high_water[stream] = arrival.logical_position

    def maturity_disposition(self, event: MaturityDisposition) -> AuthorityState | None:
        self._delay_if_stalled("maturity_disposition")
        self._require(self._state is AdapterState.ACTIVE, "maturity disposition requires an active session")
        entry = self._entry(event.entry_id)
        self._require(entry.authority is AuthorityState.HOT and entry.disposition is None, "maturity disposition may occur exactly once from hot")
        high_water = self._stream_high_water[(entry.arrival.layer, entry.arrival.kv_head)]
        self._require(entry.arrival.logical_position + HOT_WINDOW_TOKENS <= high_water, "maturity disposition precedes the frozen hot-window boundary")
        entry.disposition = event.disposition
        if event.disposition is RetentionDisposition.DROP:
            del self._entries[event.entry_id]
            return None
        entry.authority = AuthorityState.PENDING
        return entry.authority

    def metadata_publish_commit(self, *, entry_id: int) -> None:
        """Existing R3 publication acknowledgement transfers pending to packed."""
        self._require(self._state is AdapterState.ACTIVE, "atomic publication requires an active session")
        entry = self._entry(entry_id)
        self._require(entry.authority is AuthorityState.PENDING, "only retained pending entry may publish packed")
        entry.authority = AuthorityState.PACKED

    def atomic_publication(self, *, entry_id: int) -> None:
        """Compatibility spelling for the sole ``metadata_publish_commit`` event."""
        self.metadata_publish_commit(entry_id=entry_id)

    def attention_service_request(self, request: AttentionServiceRequest) -> AttentionDispatchPlan:
        self._delay_if_stalled("attention_service")
        self._require(self._state is AdapterState.ACTIVE, "attention request requires an active session")
        self._validate_identity(request.identity)
        self._validate_coordinate(request.layer, request.kv_head, request.query_position)
        self._require(request.identity not in self._live_attention, "live attention identity may not be reallocated")
        sources = tuple(
            source
            for source in CANONICAL_SOURCE_ORDER
            if any(
                entry.authority.value == source
                and entry.arrival.layer == request.layer
                and entry.arrival.kv_head == request.kv_head
                and entry.arrival.logical_position < request.query_position
                for entry in self._entries.values()
            )
        )
        self._require(sources, "attention service has no causal Route-A source and may not substitute Full-KV")
        self._live_attention.add(request.identity)
        return AttentionDispatchPlan(request.identity, sources)

    def terminal_attention(self, identity: TransactionIdentity, *, success: bool) -> str:
        self._require(self._state in {AdapterState.ACTIVE, AdapterState.RETIRING}, "terminal attention requires active or retiring session")
        self._require(identity in self._live_attention, "attention identity is not live")
        if success:
            self._require(identity in self._merge_eligible, "successful attention terminal requires all GQA updates committed")
        self._live_attention.remove(identity)
        self._merge_eligible.discard(identity)
        return "success" if success else "fault"

    def mark_gqa_updates_committed(self, identity: TransactionIdentity) -> None:
        """Make an attention identity eligible for the R4 merge terminal path."""
        self._require(self._state in {AdapterState.ACTIVE, AdapterState.RETIRING}, "GQA update commit requires active or retiring session")
        self._require(identity in self._live_attention, "GQA update commit requires a live attention identity")
        self._merge_eligible.add(identity)

    def merge_numeric_fault(self, identity: TransactionIdentity) -> str:
        """Consume R4 ``numeric_fault`` as the one outward attention fault.

        The source service has already committed all four GQA updates before an
        R4 merge is eligible.  This method selects neither retry nor fallback.
        """
        self._require(identity in self._merge_eligible, "numeric fault requires all GQA updates committed")
        return self.terminal_attention(identity, success=False)

    def session_retire(self, request: SessionRetireRequest) -> None:
        self._delay_if_stalled("session_retire")
        self._require(self._state is AdapterState.ACTIVE, "session retire requires an active session")
        self._require(request.session_id == 0, "session retire exceeds the selected anchor")
        self._validate_identity(request.identity)
        self._retire = request
        self._state = AdapterState.RETIRING

    def acknowledge_drain(self, acknowledgement: str) -> None:
        self._require(self._state is AdapterState.RETIRING, "module drain acknowledgement requires retirement")
        self._require(acknowledgement in RETIRE_DRAIN_ACKS, "unknown R6 drain acknowledgement")
        self._drain_acks.add(acknowledgement)

    def retire_ack(self) -> SessionRetireRequest:
        self._require(self._state is AdapterState.RETIRING and self._retire is not None, "retire acknowledgement requires retirement")
        self._require(not self._live_attention, "retire acknowledgement requires attention drain")
        self._require(self._drain_acks == RETIRE_DRAIN_ACKS, "retire acknowledgement requires every R6 module drain")
        acknowledgement = self._retire
        self._state = AdapterState.RETIRED
        return acknowledgement

    def destructive_reset(self) -> None:
        """Drop local reachability; R1/R3/R5 retain their own reset handshakes."""
        self._entries.clear()
        self._stream_high_water.clear()
        self._live_attention.clear()
        self._merge_eligible.clear()
        self._retire = None
        self._drain_acks.clear()
        self._init_acks.clear()
        self._stalls.clear()
        self._state = AdapterState.RESET

    def authority(self, entry_id: int) -> AuthorityState | None:
        entry = self._entries.get(entry_id)
        return None if entry is None else entry.authority

    def _entry(self, entry_id: int) -> _Entry:
        entry = self._entries.get(entry_id)
        self._require(entry is not None, "entry is not live in the generic lifecycle adapter")
        return entry

    def _delay_if_stalled(self, event: str) -> None:
        if event in self._stalls:
            raise AdapterBackpressure(f"generic adapter {event} is ready-low")

    @staticmethod
    def _validate_coordinate(layer: int, kv_head: int, position: int) -> None:
        if not (0 <= layer < ANCHOR_LAYERS and 0 <= kv_head < ANCHOR_KV_HEADS and 0 <= position < ANCHOR_CONTEXT_TOKENS):
            raise LifecycleAdapterViolation("layer/head/position is outside the selected R6 anchor")

    @staticmethod
    def _validate_identity(identity: TransactionIdentity) -> None:
        if not isinstance(identity, TransactionIdentity) or not (0 <= identity.request_id < 2**RID_WIDTH and 0 <= identity.incarnation < 2**INCARNATION_WIDTH):
            raise LifecycleAdapterViolation("identity exceeds the selected A3 namespace")

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise LifecycleAdapterViolation(message)
