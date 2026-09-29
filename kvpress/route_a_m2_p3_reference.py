"""Pure-software R3 M2/P3 wrapper reference for Route-A.

This module fixes only the event-level storage-wrapper ownership boundary.  It
does not implement an SRAM macro, an HBM controller, a clock/cycle model, a
queue topology, or an RTL datapath.  In particular, the M2 resource names are
logical A4 contracts and the 36 P3 slots are logical payload-stage slots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Literal

from kvpress.route_a_core_memory_reference import CORE_MEM_FRAGMENT_BYTES, MemoryStatus


P3_LOGICAL_SLOT_COUNT = 36
P3_RECORD_BYTES = 512
P3_RECORDS_PER_STAGE = 64
P3_PAYLOAD_STAGE_BYTES = P3_RECORD_BYTES * P3_RECORDS_PER_STAGE
P3_FRAGMENTS_PER_RECORD = P3_RECORD_BYTES // CORE_MEM_FRAGMENT_BYTES
P3_SIDECAR_BYTES_PER_RECORD = 8
M2_BANK_COUNT = 8


class M2P3Violation(AssertionError):
    """An R3 wrapper event violates selected ownership or publication rules."""


class M2Object(str, Enum):
    HEAD_CONTROL = "head_control"
    SPAN_OWNER = "span_owner"


class M2Access(str, Enum):
    READ = "read"
    WRITE = "write"
    RMW = "rmw"


class M2Member(str, Enum):
    HEAD_CONTROL_RMW = "head_control_rmw"
    SPAN_OWNER_RMW = "span_owner_rmw"


class M2GroupState(str, Enum):
    OPEN = "open"
    STAGED = "staged"
    DURABLE = "durable"
    PUBLISHED = "published"
    FAULTED = "faulted"


class P3StageState(str, Enum):
    EMPTY = "empty"
    RESERVED = "reserved"
    FILLING = "filling"
    COMPLETE = "complete"
    WRITE_ISSUED = "write_issued"
    DURABLE = "durable"
    FAULTED = "faulted"


@dataclass(frozen=True)
class M2Operation:
    """One decoupled logical M2 request; ``address_ref`` remains opaque."""

    operation_id: str
    bank: int
    object_kind: M2Object
    access: M2Access
    address_ref: str
    owner: str
    group_id: str | None = None
    member: M2Member | None = None


@dataclass
class _M2Group:
    layer: int
    kv_head: int
    owner: str
    stage_generation: int
    state: M2GroupState = M2GroupState.OPEN
    submitted: set[M2Member] = field(default_factory=set)
    completed: set[M2Member] = field(default_factory=set)


@dataclass
class _M2Outstanding:
    request: M2Operation


@dataclass
class _P3Stage:
    generation: int = 0
    state: P3StageState = P3StageState.EMPTY
    owner: str | None = None
    kv_head: int | None = None
    page_ref: str | None = None
    group_id: str | None = None
    valid_records: int = 0
    next_fragment: int = 0
    sidecar_positions: set[int] = field(default_factory=set)


class RouteAM2P3Reference:
    """Event-level M2/P3 wrapper contract for the finite Route-A anchor.

    M2 accepts logical ``op_req`` events and returns one ``op_rsp``.  Grouped
    RMWs stage privately until a separate commit acknowledgement.  P3 supplies
    one logical pending-to-stage read stream and one logical packed-write
    stream; those stream names do not select physical ports or scheduling.
    """

    _GROUP_MEMBERS = frozenset({M2Member.HEAD_CONTROL_RMW, M2Member.SPAN_OWNER_RMW})

    def __init__(self) -> None:
        self._initialized = False
        self._m2_req_ready = True
        self._m2_commit_ready = True
        self._p3_read_ready = True
        self._p3_write_ready = True
        self._groups: dict[str, _M2Group] = {}
        self._outstanding: dict[str, _M2Outstanding] = {}
        self._stages = [_P3Stage() for _ in range(P3_LOGICAL_SLOT_COUNT)]
        self._p3_read_stream_layer: int | None = None
        self._p3_write_stream_layer: int | None = None

    @property
    def initialized(self) -> bool:
        return self._initialized

    def acknowledge_init_done(self, *, core_mem_initialized: bool) -> None:
        """Enable local traffic only after the R1 memory wrapper is initialized."""
        self._require(core_mem_initialized, "R3 init requires R1 mem_init_done")
        self._require(not self._initialized, "R3 init was already acknowledged")
        self._initialized = True

    def destructive_reset(self) -> None:
        """Invalidate local groups/stages; it neither erases nor authorizes HBM."""
        self._initialized = False
        self._groups.clear()
        self._outstanding.clear()
        self._p3_read_stream_layer = None
        self._p3_write_stream_layer = None
        for stage in self._stages:
            stage.generation += 1
            self._clear_stage(stage, keep_generation=True)

    def set_channel_ready(
        self,
        *,
        m2_req: bool | None = None,
        m2_commit: bool | None = None,
        p3_read: bool | None = None,
        p3_write: bool | None = None,
    ) -> None:
        """Inject legal ready-low backpressure without introducing a cycle model."""
        if m2_req is not None:
            self._m2_req_ready = m2_req
        if m2_commit is not None:
            self._m2_commit_ready = m2_commit
        if p3_read is not None:
            self._p3_read_ready = p3_read
        if p3_write is not None:
            self._p3_write_ready = p3_write

    # M2 logical op_req / op_rsp / commit-ack wrapper.
    def open_m2_group(
        self,
        group_id: str,
        *,
        layer: int,
        kv_head: int,
        owner: str,
        stage_generation: int,
    ) -> None:
        self._require_ready()
        self._require(group_id not in self._groups and bool(group_id) and bool(owner), "M2 group identity/owner must be new and nonempty")
        self._validate_layer_head(layer, kv_head)
        stage = self._stage(layer, stage_generation)
        self._require(stage.state is P3StageState.RESERVED, "M2 group requires a reserved P3 stage")
        self._require(stage.owner == owner and stage.kv_head == kv_head, "M2 and P3 ownership must match")
        self._require(stage.group_id is None, "P3 stage is already bound to an M2 group")
        stage.group_id = group_id
        self._groups[group_id] = _M2Group(layer, kv_head, owner, stage_generation)

    def submit_m2_op(self, request: M2Operation) -> bool:
        """Accept one logical operation iff the decoupled request channel is ready."""
        self._require_ready()
        self._validate_m2_operation(request)
        if not self._m2_req_ready:
            return False
        self._require(request.operation_id not in self._outstanding, "M2 operation_id is already live")
        if request.group_id is not None:
            group = self._group(request.group_id)
            self._require(group.state is M2GroupState.OPEN, "grouped M2 operation requires an open group")
            self._require(request.owner == group.owner and request.bank == group.kv_head, "grouped M2 owner/bank mismatch")
            self._validate_group_member_shape(request)
            self._require(request.member is not None and request.member not in group.submitted, "M2 group member is missing or duplicated")
            group.submitted.add(request.member)
        self._outstanding[request.operation_id] = _M2Outstanding(request)
        return True

    def receive_m2_op_rsp(self, operation_id: str, *, status: MemoryStatus) -> None:
        """Complete one logical operation; a group member fault is fail-closed."""
        self._require_ready()
        outstanding = self._outstanding.pop(operation_id, None)
        self._require(outstanding is not None, "M2 response requires one live operation")
        request = outstanding.request
        self._require(status in {MemoryStatus.OK, MemoryStatus.FAULT}, "M2 response status is invalid")
        if request.group_id is None:
            return
        group = self._group(request.group_id)
        if status is MemoryStatus.FAULT:
            group.state = M2GroupState.FAULTED
            return
        self._require(group.state is M2GroupState.OPEN and request.member is not None, "M2 group changed before member completion")
        group.completed.add(request.member)
        if group.completed == self._GROUP_MEMBERS:
            self._require(group.submitted == self._GROUP_MEMBERS, "M2 group cannot stage before both members are accepted")
            group.state = M2GroupState.STAGED

    def mark_payload_durable(self, group_id: str, *, stage_generation: int, r1_payload_durable: bool) -> None:
        """Bind R1 payload durability to the pre-existing M2 publication dependency."""
        self._require_ready()
        group = self._group(group_id)
        self._require(group.state is M2GroupState.STAGED, "payload durability requires fully staged private M2 members")
        self._require(group.stage_generation == stage_generation, "payload durability stage generation is stale")
        stage = self._stage(group.layer, stage_generation)
        self._require(stage.state is P3StageState.DURABLE, "P3 stage is not payload durable")
        self._require(r1_payload_durable, "M2 durability dependency requires an R1 durable write commit")
        group.state = M2GroupState.DURABLE

    def metadata_publish_commit(self, group_id: str, *, publication_action: Callable[[], None]) -> bool:
        """Perform the sole publication linearization boundary if commit is ready.

        ``publication_action`` is the lifecycle authority-transfer action (for
        example, the A2 reference's metadata atomic publication).  It runs
        before the local publication bit becomes visible; if it rejects, the
        wrapper state is unchanged.  This is an event-level atomicity binding,
        not a controller or coherence implementation.
        """
        self._require_ready()
        group = self._group(group_id)
        self._require(group.state is M2GroupState.DURABLE, "M2 publication requires staged members and payload durability")
        if not self._m2_commit_ready:
            return False
        publication_action()
        group.state = M2GroupState.PUBLISHED
        stage = self._stage(group.layer, group.stage_generation)
        self._require(stage.state is P3StageState.DURABLE, "published group lost its durable P3 stage")
        self._clear_stage(stage)
        return True

    def atomic_publish(self, group_id: str, *, publication_action: Callable[[], None]) -> bool:
        """Compatibility spelling for the sole ``metadata_publish_commit`` event."""
        return self.metadata_publish_commit(group_id, publication_action=publication_action)

    def abort_faulted_group(self, group_id: str) -> None:
        """Release only a faulted, non-visible group; no retry/fallback is selected."""
        self._require_ready()
        group = self._group(group_id)
        self._require(group.state is M2GroupState.FAULTED, "only a faulted group may be aborted")
        stage = self._stage(group.layer, group.stage_generation)
        self._require(stage.state not in {P3StageState.FILLING, P3StageState.WRITE_ISSUED}, "faulted group still has a live P3 stream")
        self._clear_stage(stage)

    def m2_group_state(self, group_id: str) -> M2GroupState:
        return self._group(group_id).state

    def metadata_is_published(self, group_id: str) -> bool:
        return self._group(group_id).state is M2GroupState.PUBLISHED

    # P3 logical pending-read / stage-fill / packed-write wrapper.
    def claim_p3_stage(self, *, layer: int, kv_head: int, owner: str, page_ref: str, valid_records: int) -> int:
        self._require_ready()
        self._validate_layer_head(layer, kv_head)
        self._require(bool(owner) and bool(page_ref), "P3 owner and opaque page reference are required")
        self._require(1 <= valid_records <= P3_RECORDS_PER_STAGE, "P3 valid record count exceeds the 64-record logical stage")
        stage = self._stages[layer]
        self._require(stage.state is P3StageState.EMPTY, "one logical P3 slot per layer has one owner")
        stage.generation += 1
        stage.state = P3StageState.RESERVED
        stage.owner, stage.kv_head, stage.page_ref = owner, kv_head, page_ref
        stage.valid_records = valid_records
        return stage.generation

    def p3_read_ready_owned(self, *, layer: int, generation: int, owner: str) -> bool:
        stage = self._stage(layer, generation)
        return self._initialized and stage.state is P3StageState.RESERVED and stage.owner == owner

    def begin_p3_read(self, *, layer: int, generation: int, owner: str) -> bool:
        """Accept the sole logical pending-to-stage fill stream if ready."""
        self._require_ready()
        stage = self._stage(layer, generation)
        self._require(stage.state is P3StageState.RESERVED and stage.owner == owner, "P3 fill requires the reserved stage owner")
        if not self._p3_read_ready:
            return False
        self._require(self._p3_read_stream_layer is None, "only one logical P3 fill stream is selected")
        self._p3_read_stream_layer = layer
        stage.state = P3StageState.FILLING
        return True

    def receive_p3_read_fragment(self, *, layer: int, generation: int, owner: str, fragment_index: int, last: bool, data: bytes) -> None:
        self._require_ready()
        stage = self._stage(layer, generation)
        self._require(stage.state is P3StageState.FILLING and stage.owner == owner, "P3 fragment requires its filling stage owner")
        self._require(self._p3_read_stream_layer == layer, "P3 fragment is not on the selected fill stream")
        self._require(fragment_index == stage.next_fragment, "P3 fragments must preserve pending FIFO order")
        self._require(len(data) == CORE_MEM_FRAGMENT_BYTES, "P3 fragment width differs from R1 core fragment")
        total = stage.valid_records * P3_FRAGMENTS_PER_RECORD
        self._require(last == (fragment_index + 1 == total), "P3 terminal fragment does not match valid record count")
        stage.next_fragment += 1
        if last:
            self._p3_read_stream_layer = None
            self._maybe_complete_stage(stage)

    def bind_position_sidecar(self, *, layer: int, generation: int, owner: str, record_ordinal: int, logical_position: int) -> None:
        """Bind one 8-B logical position sidecar; it is not P3 payload storage."""
        self._require_ready()
        stage = self._stage(layer, generation)
        self._require(stage.state in {P3StageState.RESERVED, P3StageState.FILLING} and stage.owner == owner, "sidecar bind requires the live P3 stage owner")
        self._require(0 <= record_ordinal < stage.valid_records and logical_position >= 0, "invalid P3 sidecar ordinal or logical position")
        self._require(record_ordinal not in stage.sidecar_positions, "P3 sidecar ordinal is duplicated")
        stage.sidecar_positions.add(record_ordinal)
        self._maybe_complete_stage(stage)

    def p3_write_ready_owned(self, *, layer: int, generation: int, owner: str) -> bool:
        stage = self._stage(layer, generation)
        return self._initialized and stage.state is P3StageState.COMPLETE and stage.owner == owner

    def begin_p3_write(self, *, layer: int, generation: int, owner: str) -> bool:
        """Accept the sole logical P3-to-packed write stream if ready."""
        self._require_ready()
        stage = self._stage(layer, generation)
        self._require(stage.state is P3StageState.COMPLETE and stage.owner == owner, "P3 write requires complete owned payload and sidecars")
        if not self._p3_write_ready:
            return False
        self._require(self._p3_write_stream_layer is None, "only one logical P3 packed-write stream is selected")
        self._p3_write_stream_layer = layer
        stage.state = P3StageState.WRITE_ISSUED
        return True

    def record_p3_write_terminal(self, *, layer: int, generation: int, owner: str, status: MemoryStatus, r1_payload_durable: bool = False) -> None:
        """Consume an R1 terminal write result without creating packed authority."""
        self._require_ready()
        stage = self._stage(layer, generation)
        self._require(stage.state is P3StageState.WRITE_ISSUED and stage.owner == owner, "P3 write terminal requires its issued stage owner")
        self._require(self._p3_write_stream_layer == layer, "P3 write terminal is not on the selected write stream")
        self._p3_write_stream_layer = None
        if status is MemoryStatus.FAULT:
            stage.state = P3StageState.FAULTED
            self._fault_bound_group(stage)
            return
        self._require(status is MemoryStatus.OK and r1_payload_durable, "successful P3 terminal requires R1 payload durability")
        stage.state = P3StageState.DURABLE

    def fault_p3_read(self, *, layer: int, generation: int, owner: str) -> None:
        """Fail closed after a terminal pending-read fault; no fallback is implied."""
        self._require_ready()
        stage = self._stage(layer, generation)
        self._require(stage.state is P3StageState.FILLING and stage.owner == owner, "P3 read fault requires its filling stage owner")
        self._require(self._p3_read_stream_layer == layer, "P3 read fault is not on the selected fill stream")
        self._p3_read_stream_layer = None
        stage.state = P3StageState.FAULTED
        self._fault_bound_group(stage)

    def p3_stage_state(self, *, layer: int, generation: int) -> P3StageState:
        return self._stage(layer, generation).state

    def p3_slot_state(self, *, layer: int) -> P3StageState:
        """Inspect a logical slot without dereferencing a possibly stale generation."""
        self._require(0 <= layer < P3_LOGICAL_SLOT_COUNT, "P3 layer is outside the selected anchor")
        return self._stages[layer].state

    def p3_stage_payload_bytes(self, *, layer: int, generation: int) -> int:
        stage = self._stage(layer, generation)
        return stage.valid_records * P3_RECORD_BYTES

    def p3_stage_is_authoritative(self, *, layer: int, generation: int) -> bool:
        self._stage(layer, generation)
        return False

    def _maybe_complete_stage(self, stage: _P3Stage) -> None:
        total = stage.valid_records * P3_FRAGMENTS_PER_RECORD
        if stage.next_fragment == total and len(stage.sidecar_positions) == stage.valid_records:
            stage.state = P3StageState.COMPLETE

    def _fault_bound_group(self, stage: _P3Stage) -> None:
        if stage.group_id is not None:
            group = self._groups.get(stage.group_id)
            if group is not None and group.state is not M2GroupState.PUBLISHED:
                group.state = M2GroupState.FAULTED

    def _validate_m2_operation(self, request: M2Operation) -> None:
        self._require(bool(request.operation_id) and bool(request.address_ref) and bool(request.owner), "M2 operation identity/address/owner are required")
        self._require(0 <= request.bank < M2_BANK_COUNT, "M2 bank is outside the eight-bank contract")
        self._require((request.group_id is None) == (request.member is None), "M2 transaction-group tag and member must appear together")

    def _validate_group_member_shape(self, request: M2Operation) -> None:
        self._require(request.access is M2Access.RMW, "frozen metadata group members are RMW operations")
        expected_object = M2Object.HEAD_CONTROL if request.member is M2Member.HEAD_CONTROL_RMW else M2Object.SPAN_OWNER
        self._require(request.object_kind is expected_object, "M2 group member/object identity mismatch")

    def _validate_layer_head(self, layer: int, kv_head: int) -> None:
        self._require(0 <= layer < P3_LOGICAL_SLOT_COUNT, "layer exceeds the 36-slot P3 anchor")
        self._require(0 <= kv_head < M2_BANK_COUNT, "KV head exceeds the eight-bank M2 anchor")

    def _stage(self, layer: int, generation: int) -> _P3Stage:
        self._require(0 <= layer < P3_LOGICAL_SLOT_COUNT, "P3 layer is outside the selected anchor")
        stage = self._stages[layer]
        self._require(stage.generation == generation, "P3 stage generation is stale")
        return stage

    def _group(self, group_id: str) -> _M2Group:
        group = self._groups.get(group_id)
        self._require(group is not None, "unknown M2 transaction group")
        return group

    def _clear_stage(self, stage: _P3Stage, *, keep_generation: bool = False) -> None:
        if not keep_generation:
            stage.generation += 1
        stage.state = P3StageState.EMPTY
        stage.owner = stage.kv_head = stage.page_ref = stage.group_id = None
        stage.valid_records = stage.next_fragment = 0
        stage.sidecar_positions.clear()

    def _require_ready(self) -> None:
        self._require(self._initialized, "R3 wrapper accepts no traffic before init_done")

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise M2P3Violation(message)
