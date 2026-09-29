"""Pure-software R2 eligibility and arbitration reference for Route-A.

The reference models only eligibility, deterministic grant order, and the
dependency from payload durability to metadata-publication eligibility.  It
contains no controller schedule, cycle model, throughput claim, or PPA model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from kvpress.route_a_core_memory_reference import (
    CoreMemoryWrapperReference,
    CoreReadRequest,
    CoreWriteRequest,
    MemoryStatus,
    TransactionIdentity,
)


class ArbitrationViolation(AssertionError):
    """An R2 candidate or dependency event violates the selected contract."""


READ_CLASSES = ("s2_fill", "direct_pending", "pack_read")


@dataclass(frozen=True)
class ReadCandidate:
    candidate_id: str
    identity: TransactionIdentity
    read_kind: Literal["s2_fill", "direct_pending", "pack_read"]
    source_kind: Literal["full_kv", "packed", "pending"]
    destination: str
    address_ref: str
    expected_fragments: int
    arrival_ordinal: int


@dataclass(frozen=True)
class WriteCandidate:
    candidate_id: str
    identity: TransactionIdentity
    address_ref: str
    expected_fragments: int
    publication_group: str


@dataclass
class _ReadState:
    candidate: ReadCandidate
    fifo_ready: bool = False
    ownership_ready: bool = False
    credit_ready: bool = False
    destination_ready: bool = False
    metadata_published: bool = False
    pending_authoritative: bool = False
    p3_stage_ready: bool = False
    issued: bool = False


@dataclass
class _WriteState:
    candidate: WriteCandidate
    fifo_ready: bool = False
    ownership_ready: bool = False
    credit_ready: bool = False
    page_allocated: bool = False
    p3_stage_complete: bool = False
    p3_stage_owned: bool = False
    issued: bool = False
    durable: bool = False
    faulted: bool = False


class RouteAArbitrationReference:
    """Dependency scoreboard plus deterministic, weakly fair read arbiter.

    Read classes rotate in ``s2_fill -> direct_pending -> pack_read`` order.
    Within a class, the smallest arrival ordinal that has satisfied every
    frozen predecessor/ownership/credit dependency is selected.  The cursor
    advances only after the R1 core-memory wrapper accepts a request.  This is
    fairness among continuously eligible classes at grant opportunities, not a
    timing or forward-progress guarantee.
    """

    def __init__(self) -> None:
        self._reads: dict[str, _ReadState] = {}
        self._writes: dict[str, _WriteState] = {}
        self._read_cursor = 0
        self._publication_groups: dict[str, set[str]] = {}

    def register_read(self, candidate: ReadCandidate) -> None:
        self._require(candidate.candidate_id not in self._reads and candidate.candidate_id not in self._writes, "candidate_id is already registered")
        self._require(candidate.read_kind in READ_CLASSES, "unknown read class")
        self._require(candidate.expected_fragments > 0 and candidate.arrival_ordinal >= 0, "read candidate has invalid finite fields")
        self._require(bool(candidate.destination) and bool(candidate.address_ref), "read destination and address_ref are required")
        valid_source = (
            (candidate.read_kind == "s2_fill" and candidate.source_kind in {"full_kv", "packed"})
            or (candidate.read_kind in {"direct_pending", "pack_read"} and candidate.source_kind == "pending")
        )
        self._require(valid_source, "read class/source kind violates Route-A source ownership")
        self._reads[candidate.candidate_id] = _ReadState(candidate)

    def register_write(self, candidate: WriteCandidate) -> None:
        self._require(candidate.candidate_id not in self._reads and candidate.candidate_id not in self._writes, "candidate_id is already registered")
        self._require(candidate.expected_fragments > 0 and bool(candidate.address_ref) and bool(candidate.publication_group), "write candidate has invalid finite fields")
        self._writes[candidate.candidate_id] = _WriteState(candidate)
        self._publication_groups.setdefault(candidate.publication_group, set()).add(candidate.candidate_id)

    def mark_read_common_ready(
        self,
        candidate_id: str,
        *,
        fifo_ready: bool | None = None,
        ownership_ready: bool | None = None,
        credit_ready: bool | None = None,
        destination_ready: bool | None = None,
    ) -> None:
        state = self._read(candidate_id)
        self._require(not state.issued, "issued read cannot change eligibility")
        for field_name, value in {
            "fifo_ready": fifo_ready,
            "ownership_ready": ownership_ready,
            "credit_ready": credit_ready,
            "destination_ready": destination_ready,
        }.items():
            if value is not None:
                setattr(state, field_name, value)

    def mark_packed_metadata_published(self, candidate_id: str) -> None:
        state = self._read(candidate_id)
        self._require(state.candidate.read_kind == "s2_fill" and state.candidate.source_kind == "packed", "only packed S2 reads need metadata publication")
        state.metadata_published = True

    def mark_pending_authoritative(self, candidate_id: str) -> None:
        state = self._read(candidate_id)
        self._require(state.candidate.source_kind == "pending", "only pending-source reads need pending authority")
        state.pending_authoritative = True

    def mark_p3_stage_ready(self, candidate_id: str) -> None:
        state = self._read(candidate_id)
        self._require(state.candidate.read_kind == "pack_read", "only pack reads need P3 stage readiness")
        state.p3_stage_ready = True

    def mark_write_ready(
        self,
        candidate_id: str,
        *,
        fifo_ready: bool | None = None,
        ownership_ready: bool | None = None,
        credit_ready: bool | None = None,
        page_allocated: bool | None = None,
        p3_stage_complete: bool | None = None,
        p3_stage_owned: bool | None = None,
    ) -> None:
        state = self._write(candidate_id)
        self._require(not state.issued, "issued write cannot change eligibility")
        for field_name, value in {
            "fifo_ready": fifo_ready,
            "ownership_ready": ownership_ready,
            "credit_ready": credit_ready,
            "page_allocated": page_allocated,
            "p3_stage_complete": p3_stage_complete,
            "p3_stage_owned": p3_stage_owned,
        }.items():
            if value is not None:
                setattr(state, field_name, value)

    def read_is_eligible(self, candidate_id: str) -> bool:
        state = self._read(candidate_id)
        if state.issued or not all((state.fifo_ready, state.ownership_ready, state.credit_ready, state.destination_ready)):
            return False
        candidate = state.candidate
        if candidate.read_kind == "s2_fill" and candidate.source_kind == "packed":
            return state.metadata_published
        if candidate.read_kind == "direct_pending":
            return state.pending_authoritative
        if candidate.read_kind == "pack_read":
            return state.pending_authoritative and state.p3_stage_ready
        return candidate.read_kind == "s2_fill" and candidate.source_kind == "full_kv"

    def write_is_eligible(self, candidate_id: str) -> bool:
        state = self._write(candidate_id)
        return not state.issued and all(
            (
                state.fifo_ready,
                state.ownership_ready,
                state.credit_ready,
                state.page_allocated,
                state.p3_stage_complete,
                state.p3_stage_owned,
            )
        )

    def grant_next_read(self, wrapper: CoreMemoryWrapperReference) -> str | None:
        """Grant exactly one eligible read only if R1 ready accepts it."""
        if not wrapper.can_accept_read():
            return None
        for offset in range(len(READ_CLASSES)):
            class_index = (self._read_cursor + offset) % len(READ_CLASSES)
            read_class = READ_CLASSES[class_index]
            candidates = [
                state
                for state in self._reads.values()
                if state.candidate.read_kind == read_class and self.read_is_eligible(state.candidate.candidate_id)
            ]
            if not candidates:
                continue
            state = min(candidates, key=lambda item: (item.candidate.arrival_ordinal, item.candidate.candidate_id))
            candidate = state.candidate
            wrapper.accept_read(
                CoreReadRequest(
                    candidate.identity,
                    candidate.read_kind,
                    candidate.destination,
                    candidate.address_ref,
                    candidate.expected_fragments,
                )
            )
            state.issued = True
            self._read_cursor = (class_index + 1) % len(READ_CLASSES)
            return candidate.candidate_id
        return None

    def grant_write(self, candidate_id: str, wrapper: CoreMemoryWrapperReference) -> bool:
        """Issue the one pack write only when dependency and R1-ready hold."""
        state = self._write(candidate_id)
        if not self.write_is_eligible(candidate_id) or not wrapper.can_accept_write():
            return False
        candidate = state.candidate
        wrapper.accept_write(CoreWriteRequest(candidate.identity, candidate.address_ref, candidate.expected_fragments))
        state.issued = True
        return True

    def record_write_commit(
        self,
        candidate_id: str,
        *,
        wrapper: CoreMemoryWrapperReference,
        status: MemoryStatus,
    ) -> None:
        state = self._write(candidate_id)
        self._require(state.issued and not state.durable and not state.faulted, "write commit requires one issued nonterminal write")
        if status is MemoryStatus.OK:
            self._require(wrapper.durable(state.candidate.identity), "metadata dependency requires R1 durable write commit")
            state.durable = True
        elif status is MemoryStatus.FAULT:
            state.faulted = True
        else:
            raise ArbitrationViolation("write commit status is invalid")

    def metadata_publication_eligible(self, publication_group: str) -> bool:
        members = self._publication_groups.get(publication_group)
        self._require(members is not None and members, "unknown publication group")
        return all(self._writes[candidate_id].durable for candidate_id in members)

    def read_cursor_class(self) -> str:
        return READ_CLASSES[self._read_cursor]

    def _read(self, candidate_id: str) -> _ReadState:
        state = self._reads.get(candidate_id)
        self._require(state is not None, "unknown read candidate")
        return state

    def _write(self, candidate_id: str) -> _WriteState:
        state = self._writes.get(candidate_id)
        self._require(state is not None, "unknown write candidate")
        return state

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise ArbitrationViolation(message)
