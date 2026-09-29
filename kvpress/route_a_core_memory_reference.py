"""Pure-software R1 core-side memory-wrapper reference for Route-A.

This module defines transaction and reset semantics at the ``core_mem_if_v1``
boundary.  It is not an HBM controller, CDC implementation, RTL model, timing
model, bandwidth model, or PPA model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


CORE_MEM_FRAGMENT_BYTES = 64


class MemoryProtocolViolation(AssertionError):
    """A core-side memory event violates the R1 transaction contract."""


class MemoryBackpressure(MemoryProtocolViolation):
    """A legal ready-low condition delayed request acceptance without mutation."""


class MemoryStatus(str, Enum):
    OK = "ok"
    FAULT = "fault"


@dataclass(frozen=True)
class TransactionIdentity:
    """The A3-selected identity carried on every core-side memory operation."""

    request_id: int
    incarnation: int


@dataclass(frozen=True)
class CoreReadRequest:
    identity: TransactionIdentity
    read_kind: str
    destination: str
    address_ref: str
    expected_fragments: int


@dataclass(frozen=True)
class CoreReadResponse:
    identity: TransactionIdentity
    fragment_index: int
    last: bool
    status: MemoryStatus
    data: bytes | None


@dataclass(frozen=True)
class CoreWriteRequest:
    identity: TransactionIdentity
    address_ref: str
    expected_fragments: int


@dataclass(frozen=True)
class CoreWriteData:
    identity: TransactionIdentity
    fragment_index: int
    last: bool
    data: bytes


@dataclass
class _LiveRead:
    request: CoreReadRequest
    next_fragment: int = 0


@dataclass
class _LiveWrite:
    request: CoreWriteRequest
    next_fragment: int = 0


class CoreMemoryWrapperReference:
    """Event-level `core_mem_if_v1` reference with no cycle model.

    ``adapter_epoch`` is intentionally an external-adapter verification aid,
    not a core-side wire.  The real boundary instead requires the external
    adapter to suppress all pre-reset responses before it raises
    ``mem_init_done`` for the new epoch.
    """

    _READ_KINDS = frozenset({"s2_fill", "direct_pending", "pack_read"})

    def __init__(
        self,
        *,
        max_live_reads: int = 4,
        max_live_writes: int = 1,
        fragment_bytes: int = CORE_MEM_FRAGMENT_BYTES,
        rid_width: int = 3,
        incarnation_width: int = 2,
    ) -> None:
        if max_live_reads <= 0 or max_live_writes <= 0 or fragment_bytes <= 0 or rid_width <= 0 or incarnation_width <= 0:
            raise ValueError("memory-wrapper bounds must be positive")
        self._max_live_reads = max_live_reads
        self._max_live_writes = max_live_writes
        self._fragment_bytes = fragment_bytes
        self._rid_limit = 2**rid_width
        self._incarnation_limit = 2**incarnation_width
        self._adapter_epoch = 0
        self._mem_init_done = False
        self._reads: dict[TransactionIdentity, _LiveRead] = {}
        self._writes: dict[TransactionIdentity, _LiveWrite] = {}
        self._live_request_ids: set[int] = set()
        self._retired_identities: set[TransactionIdentity] = set()
        self._durable_writes: set[TransactionIdentity] = set()

    @property
    def adapter_epoch(self) -> int:
        return self._adapter_epoch

    @property
    def fragment_bytes(self) -> int:
        return self._fragment_bytes

    @property
    def mem_init_done(self) -> bool:
        return self._mem_init_done

    def can_accept_read(self) -> bool:
        return self._mem_init_done and len(self._reads) < self._max_live_reads

    def can_accept_write(self) -> bool:
        return self._mem_init_done and len(self._writes) < self._max_live_writes

    def accept_read(self, request: CoreReadRequest) -> None:
        if not self.can_accept_read():
            raise MemoryBackpressure("core_mem_if read ready is low")
        self._validate_read_request(request)
        self._accept_identity(request.identity)
        self._reads[request.identity] = _LiveRead(request)

    def receive_read_response(self, response: CoreReadResponse, *, adapter_epoch: int) -> str:
        if adapter_epoch != self._adapter_epoch:
            return "pre_reset_rejected"
        if not self._mem_init_done:
            raise MemoryProtocolViolation("memory response is illegal before mem_init_done")
        live = self._reads.get(response.identity)
        if live is None:
            return "stale_rejected"
        if response.status is MemoryStatus.FAULT:
            self._require(response.last and response.data is None, "fault response must be terminal and data-less")
            self._terminal(response.identity, is_write=False)
            return "fault"
        self._require(response.status is MemoryStatus.OK, "read response status is invalid")
        self._require(response.fragment_index == live.next_fragment, "read fragments must be ordered within one transaction")
        self._require(response.data is not None and len(response.data) == self._fragment_bytes, "read response width differs from core fragment")
        expected_last = response.fragment_index + 1 == live.request.expected_fragments
        self._require(response.last == expected_last, "read last does not match the requested fragment count")
        live.next_fragment += 1
        if response.last:
            self._terminal(response.identity, is_write=False)
            return "success"
        return "partial"

    def accept_write(self, request: CoreWriteRequest) -> None:
        if not self.can_accept_write():
            raise MemoryBackpressure("core_mem_if write ready is low")
        self._require(bool(request.address_ref), "write address_ref is required")
        self._require(request.expected_fragments > 0, "write expected_fragments must be positive")
        self._accept_identity(request.identity)
        self._writes[request.identity] = _LiveWrite(request)

    def accept_write_data(self, beat: CoreWriteData) -> None:
        self._require(self._mem_init_done, "write data is illegal before mem_init_done")
        live = self._writes.get(beat.identity)
        self._require(live is not None, "write data requires a live write")
        self._require(beat.fragment_index == live.next_fragment, "write fragments must be ordered within one transaction")
        self._require(len(beat.data) == self._fragment_bytes, "write data width differs from core fragment")
        expected_last = beat.fragment_index + 1 == live.request.expected_fragments
        self._require(beat.last == expected_last, "write last does not match the requested fragment count")
        live.next_fragment += 1

    def receive_write_commit(self, identity: TransactionIdentity, *, status: MemoryStatus, adapter_epoch: int) -> str:
        if adapter_epoch != self._adapter_epoch:
            return "pre_reset_rejected"
        if not self._mem_init_done:
            raise MemoryProtocolViolation("write commit is illegal before mem_init_done")
        live = self._writes.get(identity)
        if live is None:
            return "stale_rejected"
        if status is MemoryStatus.FAULT:
            self._terminal(identity, is_write=True)
            return "fault"
        self._require(status is MemoryStatus.OK, "write commit status is invalid")
        self._require(live.next_fragment == live.request.expected_fragments, "write commit requires complete ordered write data")
        self._durable_writes.add(identity)
        self._terminal(identity, is_write=True)
        return "payload_durable_only"

    def destructive_reset(self) -> int:
        """Clear local state; external adapter must drain/suppress old traffic."""
        self._reads.clear()
        self._writes.clear()
        self._live_request_ids.clear()
        self._retired_identities.clear()
        self._durable_writes.clear()
        self._adapter_epoch += 1
        self._mem_init_done = False
        return self._adapter_epoch

    def acknowledge_mem_init_done(self, *, adapter_epoch: int) -> None:
        self._require(adapter_epoch == self._adapter_epoch, "mem_init_done epoch is stale")
        self._require(not self._mem_init_done, "mem_init_done was already acknowledged")
        self._mem_init_done = True

    def durable(self, identity: TransactionIdentity) -> bool:
        return identity in self._durable_writes

    def live_counts(self) -> tuple[int, int]:
        return len(self._reads), len(self._writes)

    def _validate_read_request(self, request: CoreReadRequest) -> None:
        self._require(request.read_kind in self._READ_KINDS, "read kind is not a selected R1 destination class")
        self._require(bool(request.destination) and bool(request.address_ref), "read destination and address_ref are required")
        self._require(request.expected_fragments > 0, "read expected_fragments must be positive")

    def _accept_identity(self, identity: TransactionIdentity) -> None:
        self._require(0 <= identity.request_id < self._rid_limit and 0 <= identity.incarnation < self._incarnation_limit, "identity exceeds the selected finite namespace")
        self._require(identity not in self._reads and identity not in self._writes, "identity is already live")
        self._require(identity not in self._retired_identities, "identity may not be reused in one adapter epoch")
        self._require(identity.request_id not in self._live_request_ids, "live request_id may not acquire another incarnation")
        self._live_request_ids.add(identity.request_id)

    def _terminal(self, identity: TransactionIdentity, *, is_write: bool) -> None:
        live = self._writes.pop(identity, None) if is_write else self._reads.pop(identity, None)
        self._require(live is not None, "terminal event requires a matching live transaction")
        self._live_request_ids.remove(identity.request_id)
        self._retired_identities.add(identity)

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise MemoryProtocolViolation(message)
