"""Pure-software transaction reference for the Route-A pre-RTL contract.

This is a scoreboard/golden-reference seed, not an RTL model, HBM controller,
timing model, or attention implementation.  It accepts only abstract control
events and rejects sequences that violate the architecture specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import exp
from typing import Literal, Mapping


CANONICAL_SOURCE_ORDER = ("hot", "pending", "packed")


@dataclass(frozen=True)
class SourcePartial:
    """Logical online-softmax partial; not a numeric datapath representation."""

    m: float
    l: float
    o: float

    @classmethod
    def absent_identity(cls) -> "SourcePartial":
        return cls(float("-inf"), 0.0, 0.0)


@dataclass(frozen=True)
class MergeReferenceResult:
    """Canonical-order mathematical merge result for a nonempty source set."""

    partial: SourcePartial
    source_order: tuple[str, ...]

    def normalized(self) -> float:
        if self.partial.l <= 0.0:
            raise ContractViolation("online-softmax normalization requires l > 0")
        return self.partial.o / self.partial.l


class ContractViolation(AssertionError):
    """An event sequence violates a frozen Route-A interface invariant."""


class BackpressureStall(ContractViolation):
    """A legal semantic stall delayed an event without changing reference state."""


class RequestState(str, Enum):
    LIVE = "live"
    SUCCESS = "success"
    FAULT = "fault"


class SlotState(str, Enum):
    EMPTY = "empty"
    FILLING = "filling"
    READY = "ready"
    CONSUMING = "consuming"


def merge_source_partials(partials: Mapping[str, SourcePartial | None]) -> MergeReferenceResult:
    """Merge logical source partials in the frozen canonical source order.

    ``None`` denotes an absent source and is substituted with the specified
    identity ``(-inf, 0, 0)``.  This mathematical reference deliberately offers
    no source-reordering mode and makes no finite-precision equivalence claim.
    """
    unexpected = set(partials) - set(CANONICAL_SOURCE_ORDER)
    if unexpected:
        raise ValueError(f"unknown Route-A source(s): {sorted(unexpected)}")
    present = tuple(name for name in CANONICAL_SOURCE_ORDER if partials.get(name) is not None)
    if not present:
        raise ContractViolation("Route-A merge has an entirely empty logical source set")
    result = SourcePartial.absent_identity()
    for name in CANONICAL_SOURCE_ORDER:
        candidate = partials.get(name)
        partial = SourcePartial.absent_identity() if candidate is None else candidate
        if result.l == 0.0 and partial.l == 0.0:
            result = SourcePartial.absent_identity()
            continue
        if result.l == 0.0:
            result = partial
            continue
        if partial.l == 0.0:
            continue
        m = max(result.m, partial.m)
        l = exp(result.m - m) * result.l + exp(partial.m - m) * partial.l
        o = exp(result.m - m) * result.o + exp(partial.m - m) * partial.o
        result = SourcePartial(m, l, o)
    return MergeReferenceResult(result, CANONICAL_SOURCE_ORDER)


@dataclass
class _Request:
    request_id: int
    epoch: int
    kind: str
    state: RequestState = RequestState.LIVE
    terminal_count: int = 0
    slot: str | None = None
    generation: int | None = None
    requires_sidecar: bool = False
    payload_complete: bool = False
    sidecar_complete: bool = False
    token: str | None = None
    direct_tokens: tuple[str, ...] = ()
    next_ordinal: int = 0
    direct_consumers: set[int] = field(default_factory=set)


@dataclass
class _Slot:
    generation: int = 0
    state: SlotState = SlotState.EMPTY
    request_id: int | None = None
    epoch: int | None = None
    payload_complete: bool = False
    sidecar_complete: bool = False
    consumers: set[int] = field(default_factory=set)


@dataclass
class _MetadataGroup:
    members: frozenset[str]
    staged: set[str] = field(default_factory=set)
    published: bool = False


class RouteAArchitectureReference:
    """Event-level Route-A contract model with no model- or clock-dependence."""

    def __init__(
        self,
        *,
        slots: tuple[str, ...] = ("S2-A", "S2-B"),
        gqa_consumers: int = 4,
        request_id_profile: Literal["strict_no_reuse", "epoch_reuse"] = "strict_no_reuse",
        logical_admission_credits: int | None = None,
    ) -> None:
        if not slots or len(set(slots)) != len(slots) or gqa_consumers <= 0:
            raise ValueError("slots must be unique/nonempty and gqa_consumers positive")
        if request_id_profile not in {"strict_no_reuse", "epoch_reuse"}:
            raise ValueError("request_id_profile is invalid")
        if logical_admission_credits is not None and logical_admission_credits < 0:
            raise ValueError("logical_admission_credits must be nonnegative or None")
        self._slots = {name: _Slot() for name in slots}
        self._gqa_consumers = frozenset(range(gqa_consumers))
        self._request_id_profile = request_id_profile
        self._requests: dict[tuple[int, int], _Request] = {}
        self._authority: dict[str, str] = {}
        self._disposition: dict[str, str] = {}
        self._mask_decisions: dict[str, bool] = {}
        self._credit_tokens: set[str] = set()
        self._logical_admission_credit_capacity = logical_admission_credits
        self._durable_packed: set[str] = set()
        self._groups: dict[str, _MetadataGroup] = {}
        self._stalls: set[str] = set()

    def seed_hot(self, token: str) -> None:
        self._require(token not in self._authority, "token already has authoritative residency")
        self._authority[token], self._disposition[token] = "hot", "live"
        self.assert_invariants()

    def set_mask_decision(self, token: str, *, keep: bool) -> None:
        """Record the already-produced KVzap keep/drop decision without changing it."""
        self._require(self._authority.get(token) == "hot", "mask decision requires hot authority")
        prior = self._mask_decisions.get(token)
        self._require(prior is None or prior == keep, "mask decision may not change")
        self._mask_decisions[token] = keep
        self.assert_invariants()

    def mature_hot(self, token: str, *, keep: bool | None = None) -> str:
        """Apply the already-decided keep/drop disposition at maturity once."""
        self._require(self._authority.get(token) == "hot", "maturity requires hot authority")
        self._require(self._disposition.get(token) == "live", "maturity disposition already fixed")
        chosen = self._mask_decisions.get(token)
        if chosen is None:
            self._require(keep is not None, "maturity requires an immutable mask decision")
            chosen = keep
        elif keep is not None:
            self._require(chosen == keep, "mask decision may not change")
        if not chosen:
            self._mask_decisions[token] = False
            del self._authority[token]
            self._disposition[token] = "drop"
            self.assert_invariants()
            return "drop"
        self._delay_if_stalled("credit_availability")
        if self._logical_admission_credit_capacity is not None and len(self._credit_tokens) >= self._logical_admission_credit_capacity:
            raise BackpressureStall("logical admission credit unavailable")
        self._authority[token] = "pending"
        self._mask_decisions[token] = True
        self._credit_tokens.add(token)
        self.assert_invariants()
        return "pending"

    def seed_pending(self, token: str) -> None:
        """Compatibility fixture for an already-admitted pending token."""
        self._require(token not in self._authority, "token already has authoritative residency")
        if self._logical_admission_credit_capacity is not None and len(self._credit_tokens) >= self._logical_admission_credit_capacity:
            raise BackpressureStall("logical admission credit unavailable")
        self._authority[token], self._disposition[token] = "pending", "live"
        self._credit_tokens.add(token)
        self.assert_invariants()

    def set_stall(self, event: Literal["request_accept", "response_delivery", "consumer_completion", "metadata_publication", "credit_availability", "credit_release"], stalled: bool) -> None:
        if stalled:
            self._stalls.add(event)
        else:
            self._stalls.discard(event)

    def open_packed_write(self, request_id: int, token: str, *, epoch: int | None = None) -> None:
        self._require(self._authority.get(token) == "pending", "packed write requires pending authority")
        self._accept_request(request_id, "packed_write", epoch=epoch).token = token

    def page_write_commit(self, request_id: int, token: str, *, epoch: int | None = None) -> None:
        request = self._live_request(request_id, "packed_write", epoch=epoch)
        self._require(request.token == token, "write commit token differs from accepted request")
        self._require(self._authority.get(token) == "pending", "write commit cannot transfer authority")
        self._durable_packed.add(token)
        self._terminal(request, RequestState.SUCCESS)
        self.assert_invariants()

    def begin_metadata_group(self, group_id: str, members: tuple[str, ...]) -> None:
        self._require(group_id not in self._groups and members and len(set(members)) == len(members), "invalid metadata group")
        self._groups[group_id] = _MetadataGroup(frozenset(members))

    def stage_metadata_member(self, group_id: str, member: str) -> None:
        group = self._group(group_id)
        self._require(not group.published and member in group.members, "invalid metadata member staging")
        group.staged.add(member)
        self.assert_invariants()

    def metadata_atomic_publish(self, group_id: str) -> None:
        self._delay_if_stalled("metadata_publication")
        group = self._group(group_id)
        self._require(not group.published and group.staged == group.members, "partial metadata group cannot publish")
        self._require(group.members <= self._durable_packed, "metadata publication requires packed write commit")
        self._delay_if_stalled("credit_release")
        for token in group.members:
            self._require(self._authority.get(token) == "pending", "only pending authority may transfer to packed")
            self._authority[token] = "packed"
            self._credit_tokens.discard(token)
        group.published = True
        self.assert_invariants()

    def accept_s2_read(self, request_id: int, slot_name: str, *, requires_sidecar: bool, epoch: int | None = None) -> int:
        self._delay_if_stalled("request_accept")
        slot = self._slot(slot_name)
        self._require(slot.state is SlotState.EMPTY, "S2 slot is not releasable")
        request = self._accept_request(request_id, "s2_read", epoch=epoch)
        slot.generation += 1
        slot.state, slot.request_id = SlotState.FILLING, request_id
        slot.epoch = request.epoch
        slot.payload_complete = slot.sidecar_complete = False
        request.slot, request.generation, request.requires_sidecar = slot_name, slot.generation, requires_sidecar
        self.assert_invariants()
        return slot.generation

    def receive_s2_response(self, request_id: int, generation: int, *, epoch: int | None = None, payload_last: bool = False, sidecar_last: bool = False, fault: bool = False) -> str:
        self._delay_if_stalled("response_delivery")
        request = self._request_or_none(request_id, epoch)
        if request is None or request.kind != "s2_read" or request.state is not RequestState.LIVE:
            return "stale_rejected"
        slot = self._slot(request.slot)
        if slot.request_id != request_id or slot.epoch != request.epoch or slot.generation != generation or request.generation != generation:
            return "stale_rejected"
        if fault:
            slot.state, slot.request_id = SlotState.EMPTY, None
            slot.epoch = None
            slot.payload_complete = slot.sidecar_complete = False
            self._terminal(request, RequestState.FAULT)
            self.assert_invariants()
            return "fault"
        request.payload_complete |= payload_last
        request.sidecar_complete |= sidecar_last
        slot.payload_complete, slot.sidecar_complete = request.payload_complete, request.sidecar_complete
        if request.payload_complete and (not request.requires_sidecar or request.sidecar_complete):
            slot.state = SlotState.READY
            self._terminal(request, RequestState.SUCCESS)
            self.assert_invariants()
            return "ready"
        self.assert_invariants()
        return "partial"

    def begin_s2_consume(self, slot_name: str) -> None:
        slot = self._slot(slot_name)
        self._require(slot.state is SlotState.READY, "only READY S2 data may be consumed")
        slot.state, slot.consumers = SlotState.CONSUMING, set(self._gqa_consumers)
        self.assert_invariants()

    def commit_s2_consumer(self, slot_name: str, consumer: int) -> None:
        self._delay_if_stalled("consumer_completion")
        slot = self._slot(slot_name)
        self._require(slot.state is SlotState.CONSUMING and consumer in slot.consumers, "invalid S2 consumer completion")
        slot.consumers.remove(consumer)
        self.assert_invariants()

    def release_s2(self, slot_name: str) -> None:
        self._delay_if_stalled("credit_release")
        slot = self._slot(slot_name)
        self._require(slot.state is SlotState.CONSUMING and not slot.consumers, "S2 release requires all GQA completions")
        slot.state, slot.request_id = SlotState.EMPTY, None
        slot.epoch = None
        slot.payload_complete = slot.sidecar_complete = False
        self.assert_invariants()

    def open_direct_pending_source(self, request_id: int, tokens: tuple[str, ...], *, epoch: int | None = None) -> None:
        self._delay_if_stalled("request_accept")
        self._require(tokens and len(set(tokens)) == len(tokens), "pending source must contain unique ordered tokens")
        self._require(all(self._authority.get(token) == "pending" for token in tokens), "direct source requires pending authority")
        request = self._accept_request(request_id, "direct_pending", epoch=epoch)
        request.direct_tokens, request.direct_consumers = tokens, set(self._gqa_consumers)

    def receive_direct_pending_record(self, request_id: int, ordinal: int, token: str, *, last: bool, epoch: int | None = None) -> str:
        self._delay_if_stalled("response_delivery")
        request = self._request_or_none(request_id, epoch)
        if request is None or request.kind != "direct_pending" or request.state is not RequestState.LIVE:
            return "stale_rejected"
        self._require(ordinal == request.next_ordinal and ordinal < len(request.direct_tokens), "pending records must retain FIFO ordinal order")
        self._require(token == request.direct_tokens[ordinal] and self._authority.get(token) == "pending", "invalid pending record delivery")
        request.next_ordinal += 1
        self._require(last == (request.next_ordinal == len(request.direct_tokens)), "incorrect direct source terminal marker")
        self.assert_invariants()
        return "delivered"

    def commit_direct_pending_consumer(self, request_id: int, consumer: int, *, epoch: int | None = None) -> None:
        self._delay_if_stalled("consumer_completion")
        request = self._live_request(request_id, "direct_pending", epoch=epoch)
        self._require(request.next_ordinal == len(request.direct_tokens), "consumer completion precedes terminal pending record")
        self._require(consumer in request.direct_consumers, "invalid direct pending consumer completion")
        request.direct_consumers.remove(consumer)

    def close_direct_pending_source(self, request_id: int, *, epoch: int | None = None) -> None:
        self._delay_if_stalled("credit_release")
        request = self._live_request(request_id, "direct_pending", epoch=epoch)
        self._require(request.next_ordinal == len(request.direct_tokens) and not request.direct_consumers, "direct source cannot close before records and consumers complete")
        self._terminal(request, RequestState.SUCCESS)
        self.assert_invariants()

    def authority(self, token: str) -> str:
        return self._authority[token]

    def authoritative_count(self, token: str) -> int:
        """Transient P3/S2/direct transport state never contributes here."""
        return int(token in self._authority)

    def disposition(self, token: str) -> str:
        return self._disposition[token]

    def credit_state(self) -> tuple[int | None, int]:
        return self._logical_admission_credit_capacity, len(self._credit_tokens)

    def snapshot(self) -> dict[str, object]:
        """Small deterministic state image for stall/non-mutation tests."""
        return {
            "authority": dict(sorted(self._authority.items())),
            "disposition": dict(sorted(self._disposition.items())),
            "mask_decisions": dict(sorted(self._mask_decisions.items())),
            "credits": self.credit_state(),
            "slots": {name: (slot.generation, slot.state.value, slot.request_id, slot.epoch, tuple(sorted(slot.consumers))) for name, slot in sorted(self._slots.items())},
            "requests": {key: (request.kind, request.state.value, request.terminal_count, request.next_ordinal, tuple(sorted(request.direct_consumers))) for key, request in sorted(self._requests.items())},
            "groups": {key: (tuple(sorted(group.staged)), group.published) for key, group in sorted(self._groups.items())},
            "full_kv_substitution_count": 0,
        }

    def slot_state(self, slot_name: str) -> SlotState:
        return self._slot(slot_name).state

    def visible_group(self, group_id: str) -> bool:
        return self._group(group_id).published

    def assert_invariants(self) -> None:
        for request in self._requests.values():
            self._require(request.terminal_count in (0, 1), "request has multiple terminal outcomes")
            self._require((request.state is RequestState.LIVE) == (request.terminal_count == 0), "request liveness/terminal mismatch")
        for group in self._groups.values():
            self._require(not group.published or group.staged == group.members, "partial metadata group visible")
        self._require(all(state in {"hot", "pending", "packed"} for state in self._authority.values()), "invalid authoritative residency")
        for token, disposition in self._disposition.items():
            if disposition == "drop":
                self._require(token not in self._authority and token not in self._durable_packed, "dropped token retained an authoritative residency")
            else:
                self._require(self.authoritative_count(token) == 1, "live retained token lacks exactly one authoritative residency")
        self._require(set(self._mask_decisions) <= set(self._disposition), "mask decision lacks token lifecycle")
        self._require(self._credit_tokens <= {token for token, state in self._authority.items() if state == "pending"}, "credit outlives pending authority")
        for slot in self._slots.values():
            if slot.state is SlotState.EMPTY:
                self._require(slot.request_id is None and not slot.consumers, "empty S2 slot retains ownership")
            if slot.state is SlotState.READY:
                self._require(slot.payload_complete, "READY S2 slot lacks payload")

    def _accept_request(self, request_id: int, kind: str, *, epoch: int | None) -> _Request:
        self._delay_if_stalled("request_accept")
        key = self._request_key(request_id, epoch)
        self._require(key not in self._requests, "request ID/epoch may not be reallocated")
        self._require(not any(request.request_id == request_id and request.state is RequestState.LIVE for request in self._requests.values()), "live request ID may not be reallocated")
        request = _Request(request_id=request_id, epoch=key[1], kind=kind)
        self._requests[key] = request
        return request

    def _live_request(self, request_id: int, kind: str, *, epoch: int | None) -> _Request:
        request = self._request_or_none(request_id, epoch)
        self._require(request is not None and request.kind == kind and request.state is RequestState.LIVE, "request is not live for this operation")
        return request

    def _request_or_none(self, request_id: int, epoch: int | None) -> _Request | None:
        try:
            return self._requests.get(self._request_key(request_id, epoch))
        except ContractViolation:
            return None

    def _request_key(self, request_id: int, epoch: int | None) -> tuple[int, int]:
        self._require(request_id >= 0, "request ID is invalid")
        if self._request_id_profile == "strict_no_reuse":
            self._require(epoch is None, "strict profile does not carry request epochs")
            return request_id, 0
        self._require(epoch is not None and epoch >= 0, "epoch-reuse profile requires a nonnegative epoch")
        return request_id, epoch

    def _delay_if_stalled(self, event: str) -> None:
        if event in self._stalls:
            raise BackpressureStall(f"semantic backpressure stalled {event}")

    def _terminal(self, request: _Request, state: RequestState) -> None:
        self._require(request.state is RequestState.LIVE and state is not RequestState.LIVE, "request terminal outcome is invalid")
        request.state, request.terminal_count = state, request.terminal_count + 1

    def _slot(self, name: str | None) -> _Slot:
        self._require(name is not None and name in self._slots, "unknown S2 slot")
        return self._slots[name]

    def _group(self, group_id: str) -> _MetadataGroup:
        self._require(group_id in self._groups, "unknown metadata group")
        return self._groups[group_id]

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise ContractViolation(message)
