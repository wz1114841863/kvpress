"""Pure-software R5 packed-page manager and descriptor-placement reference.

The reference closes descriptor ownership, deterministic logical addressing,
and retirement/reclaim ordering for the Route-A anchor.  It is not an HBM
controller, descriptor-cache implementation, timing model, area estimate, PPA
model, or RTL implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, IntEnum
from typing import Callable, TypeVar

from kvpress.route_a_core_memory_reference import TransactionIdentity
from kvpress.route_a_rtl_profile import (
    PAGE_GENERATION_WRAP_QUIESCENCE,
    PageAllocatorReference,
    PageRef,
    PageState,
    ProfileViolation,
)


ANCHOR_LAYERS = 36
ANCHOR_KV_HEADS = 8
ANCHOR_PAGE_POOL_PAGES = 146_880
PAGE_ID_WIDTH = 18
PAGE_GENERATION_WIDTH = 8
PAGE_TOKENS = 64
KV_PAYLOAD_BYTES_PER_TOKEN = 512
POSITION_SIDECAR_BYTES_PER_TOKEN = 8
PACKED_PAYLOAD_BYTES = PAGE_TOKENS * KV_PAYLOAD_BYTES_PER_TOKEN
PACKED_SIDECAR_BYTES = PAGE_TOKENS * POSITION_SIDECAR_BYTES_PER_TOKEN
PACKED_PAGE_STORAGE_BYTES = PACKED_PAYLOAD_BYTES + PACKED_SIDECAR_BYTES
DESCRIPTOR_BITS = 128
DESCRIPTOR_BYTES = DESCRIPTOR_BITS // 8
CORE_FRAGMENT_BYTES = 64
DESCRIPTORS_PER_CORE_FRAGMENT = CORE_FRAGMENT_BYTES // DESCRIPTOR_BYTES
MAX_DESCRIPTOR_MAINTENANCE_OPS = 2
STREAM_DESCRIPTOR_BITS = 96
STREAM_DESCRIPTOR_BYTES = STREAM_DESCRIPTOR_BITS // 8
ANCHOR_STREAM_DESCRIPTOR_COUNT = ANCHOR_LAYERS * ANCHOR_KV_HEADS
ANCHOR_DESCRIPTOR_REGION_BYTES = ANCHOR_PAGE_POOL_PAGES * DESCRIPTOR_BYTES
ANCHOR_ALLOCATOR_BITMAP_BYTES = (ANCHOR_PAGE_POOL_PAGES + 7) // 8
NEXT_NONE_PAGE_ID = (1 << PAGE_ID_WIDTH) - 1

_Result = TypeVar("_Result")


class PageManagerViolation(AssertionError):
    """A page-manager event violates the selected R5 realization contract."""


class DescriptorState(IntEnum):
    FREE = 0
    ALLOCATED_UNPUBLISHED = 1
    LIVE_PACKED = 2
    RETIRE_PENDING = 3


class PageManagerState(str, Enum):
    ACTIVE = "active"
    RETIRING = "retiring"
    RETIRED = "retired"
    FAULTED = "faulted"
    RESET = "reset"


class DescriptorOperationKind(str, Enum):
    NEW_PAGE = "new_page"
    TAIL_LINK = "tail_link"
    INVALIDATE = "invalidate"


@dataclass(frozen=True)
class PackedPageDescriptor:
    """Selected 128-bit HBM descriptor entry; payload/sidecar handles derive by ID."""

    state: DescriptorState
    owner_layer: int
    owner_kv_head: int
    valid_count: int
    generation: int
    next_ref: PageRef | None

    def encode(self) -> bytes:
        self._validate()
        next_page_id = NEXT_NONE_PAGE_ID if self.next_ref is None else self.next_ref.page_id
        next_generation = 0 if self.next_ref is None else self.next_ref.generation
        word = int(self.state)
        word |= self.owner_layer << 2
        word |= self.owner_kv_head << 8
        word |= self.valid_count << 11
        word |= next_page_id << 18
        word |= next_generation << 36
        word |= self.generation << 44
        return word.to_bytes(DESCRIPTOR_BYTES, byteorder="little", signed=False)

    @classmethod
    def decode(cls, payload: bytes) -> "PackedPageDescriptor":
        if len(payload) != DESCRIPTOR_BYTES:
            raise PageManagerViolation("descriptor payload is not 128 bits")
        word = int.from_bytes(payload, byteorder="little", signed=False)
        if word >> 52:
            raise PageManagerViolation("descriptor reserved bits are nonzero")
        state = DescriptorState(word & 0b11)
        owner_layer = (word >> 2) & 0x3F
        owner_kv_head = (word >> 8) & 0x7
        valid_count = (word >> 11) & 0x7F
        next_page_id = (word >> 18) & ((1 << PAGE_ID_WIDTH) - 1)
        next_generation = (word >> 36) & 0xFF
        generation = (word >> 44) & 0xFF
        next_ref = None if next_page_id == NEXT_NONE_PAGE_ID else PageRef(next_page_id, next_generation)
        descriptor = cls(state, owner_layer, owner_kv_head, valid_count, generation, next_ref)
        descriptor._validate()
        return descriptor

    def _validate(self) -> None:
        if not 0 <= self.owner_layer < ANCHOR_LAYERS or not 0 <= self.owner_kv_head < ANCHOR_KV_HEADS:
            raise PageManagerViolation("descriptor owner exceeds the selected anchor")
        if not 0 <= self.valid_count <= PAGE_TOKENS:
            raise PageManagerViolation("descriptor valid_count exceeds the frozen page size")
        if not 0 <= self.generation < 2**PAGE_GENERATION_WIDTH:
            raise PageManagerViolation("descriptor generation exceeds the selected width")
        if self.next_ref is not None and (
            not 0 <= self.next_ref.page_id < NEXT_NONE_PAGE_ID
            or not 0 <= self.next_ref.generation < 2**PAGE_GENERATION_WIDTH
        ):
            raise PageManagerViolation("descriptor next_ref is not a finite PageRef")


@dataclass(frozen=True)
class DescriptorLocation:
    """Logical table position; region base/address width remains an adapter parameter."""

    page_id: int
    entry_offset_bytes: int
    core_fragment_index: int
    lane: int


@dataclass(frozen=True)
class DescriptorOperation:
    operation_id: str
    kind: DescriptorOperationKind
    subject_ref: PageRef
    target_ref: PageRef
    location: DescriptorLocation


@dataclass
class StreamDescriptor:
    """Selected 96-bit on-chip active-stream logical state."""

    owner_layer: int
    owner_kv_head: int
    first_ref: PageRef | None = None
    tail_ref: PageRef | None = None
    page_count: int = 0
    total_valid_tokens: int = 0

    def tail_valid_count(self) -> int:
        if self.page_count == 0:
            return 0
        remainder = self.total_valid_tokens % PAGE_TOKENS
        return PAGE_TOKENS if remainder == 0 else remainder


@dataclass
class _PendingPublication:
    ref: PageRef
    owner_layer: int
    owner_kv_head: int
    valid_count: int
    prior_tail: PageRef | None
    operations: dict[str, DescriptorOperation]
    completed: set[str]


class RouteAPageManagerReference:
    """R5 event-level manager for descriptor preparation, publication, and retirement.

    A descriptor operation is one logical 64-B line maintenance request with a
    16-B selected entry lane.  It is a separate maintenance obligation, not an
    extra physical HBM port or an R2 read/write arbitration class.  Ready-low
    may delay it and therefore publication/retirement only; it cannot mutate
    the frozen payload-arbiter order or semantic results.
    """

    def __init__(
        self,
        *,
        page_pool_pages: int = ANCHOR_PAGE_POOL_PAGES,
        layer_count: int = ANCHOR_LAYERS,
        kv_head_count: int = ANCHOR_KV_HEADS,
        generation_width: int = PAGE_GENERATION_WIDTH,
    ) -> None:
        if page_pool_pages <= 0 or page_pool_pages >= NEXT_NONE_PAGE_ID:
            raise ValueError("page_pool_pages must fit the selected descriptor next-ref encoding")
        if not 0 < layer_count <= ANCHOR_LAYERS or not 0 < kv_head_count <= ANCHOR_KV_HEADS:
            raise ValueError("test dimensions cannot exceed the selected anchor")
        self._page_pool_pages = page_pool_pages
        self._layer_count = layer_count
        self._kv_head_count = kv_head_count
        self._generation_width = generation_width
        self._allocator = PageAllocatorReference(page_pool_pages, generation_width=generation_width)
        self._streams = {(layer, head): StreamDescriptor(layer, head) for layer in range(layer_count) for head in range(kv_head_count)}
        self._physical: dict[int, PackedPageDescriptor] = {}
        self._visible: dict[int, PackedPageDescriptor] = {}
        self._pending: dict[PageRef, _PendingPublication] = {}
        self._operations: dict[str, DescriptorOperation] = {}
        self._completed_reclaims: set[PageRef] = set()
        self._active_refs: set[PageRef] = set()
        self._state = PageManagerState.ACTIVE
        self._retire_identity: TransactionIdentity | None = None
        self._initialized = True

    @property
    def state(self) -> PageManagerState:
        return self._state

    def descriptor_region_bytes(self) -> int:
        return self._page_pool_pages * DESCRIPTOR_BYTES

    def descriptor_location(self, page_id: int) -> DescriptorLocation:
        self._require(0 <= page_id < self._page_pool_pages, "page ID is outside the selected descriptor table")
        entry_offset = page_id * DESCRIPTOR_BYTES
        return DescriptorLocation(page_id, entry_offset, entry_offset // CORE_FRAGMENT_BYTES, (entry_offset % CORE_FRAGMENT_BYTES) // DESCRIPTOR_BYTES)

    def payload_offset(self, ref: PageRef) -> int:
        self._resolve(ref)
        return ref.page_id * PACKED_PAGE_STORAGE_BYTES

    def sidecar_offset(self, ref: PageRef) -> int:
        return self.payload_offset(ref) + PACKED_PAYLOAD_BYTES

    def migration_reserve_offset(self) -> int:
        """Non-descriptor temporary slot immediately after final packed page IDs."""
        return self._page_pool_pages * PACKED_PAGE_STORAGE_BYTES

    def allocate_page(self, *, layer: int, kv_head: int) -> PageRef:
        self._require_active()
        self._validate_owner(layer, kv_head)
        self._require(not any(p.owner_layer == layer and p.owner_kv_head == kv_head for p in self._pending.values()), "one stream cannot prepare a second unpublished tail")
        ref = self._allocator.allocate()
        self._active_refs.add(ref)
        return ref

    def payload_write_commit(self, ref: PageRef) -> None:
        self._require_active()
        self._allocator_event(lambda: self._allocator.write_commit(ref))

    def begin_descriptor_prepare(self, ref: PageRef, *, layer: int, kv_head: int, valid_count: int) -> tuple[DescriptorOperation, ...]:
        """Create the mandatory descriptor writes after payload durability, before M2 publish."""
        self._require_active()
        self._validate_owner(layer, kv_head)
        self._require(1 <= valid_count <= PAGE_TOKENS, "descriptor prepare requires one to 64 valid records")
        self._require(
            self._allocator_event(lambda: self._allocator.state(ref)) is PageState.WRITE_COMMITTED,
            "descriptor prepare requires payload write commit",
        )
        self._require(ref not in self._pending, "descriptor preparation is already active for this page")
        stream = self._stream(layer, kv_head)
        new_descriptor = PackedPageDescriptor(DescriptorState.LIVE_PACKED, layer, kv_head, valid_count, ref.generation, None)
        operations: dict[str, DescriptorOperation] = {}
        new_id = self._operation_id(DescriptorOperationKind.NEW_PAGE, ref, ref)
        operations[new_id] = DescriptorOperation(new_id, DescriptorOperationKind.NEW_PAGE, ref, ref, self.descriptor_location(ref.page_id))
        if stream.tail_ref is not None:
            tail_id = self._operation_id(DescriptorOperationKind.TAIL_LINK, ref, stream.tail_ref)
            operations[tail_id] = DescriptorOperation(tail_id, DescriptorOperationKind.TAIL_LINK, ref, stream.tail_ref, self.descriptor_location(stream.tail_ref.page_id))
        pending = _PendingPublication(ref, layer, kv_head, valid_count, stream.tail_ref, operations, set())
        self._require(
            len(self._operations) + len(operations) <= MAX_DESCRIPTOR_MAINTENANCE_OPS,
            "descriptor maintenance bound is exhausted",
        )
        self._pending[ref] = pending
        self._operations.update(operations)
        self._prepared_new_descriptor(ref, new_descriptor)
        return tuple(operations.values())

    def complete_descriptor_operation(self, operation_id: str, *, success: bool) -> None:
        """Record a terminal descriptor-line maintenance result, fail-closed on fault."""
        self._require_active_or_retiring()
        operation = self._operations.pop(operation_id, None)
        self._require(operation is not None, "descriptor operation is not live")
        if not success:
            self._state = PageManagerState.FAULTED
            return
        if operation.kind is DescriptorOperationKind.INVALIDATE:
            self._completed_reclaims.add(operation.subject_ref)
            self._physical[operation.target_ref.page_id] = self._free_descriptor_for_next_generation(operation.subject_ref)
            return
        pending = self._pending.get(operation.subject_ref)
        self._require(pending is not None, "descriptor operation lost its unpublished page")
        pending.completed.add(operation_id)
        if operation.kind is DescriptorOperationKind.NEW_PAGE:
            self._physical[operation.target_ref.page_id] = self._prepared_descriptor(operation.subject_ref)
        else:
            prior = self._physical.get(operation.target_ref.page_id) or self._visible.get(operation.target_ref.page_id)
            self._require(prior is not None, "tail link requires a physical prior-tail descriptor")
            self._physical[operation.target_ref.page_id] = replace(prior, next_ref=operation.subject_ref)

    def descriptor_prepare_ready(self, ref: PageRef) -> bool:
        pending = self._pending.get(ref)
        return pending is not None and set(pending.operations) == pending.completed and self._state is PageManagerState.ACTIVE

    def metadata_publish_commit(self, ref: PageRef, *, publication_action: Callable[[], None]) -> None:
        """Atomically bind prepared descriptor visibility to the existing M2 publication action."""
        self._require_active()
        pending = self._pending.get(ref)
        self._require(pending is not None and self.descriptor_prepare_ready(ref), "atomic publication requires durable descriptor preparation")
        publication_action()
        self._allocator_event(lambda: self._allocator.metadata_publish(ref))
        self._visible[ref.page_id] = self._physical[ref.page_id]
        if pending.prior_tail is not None:
            self._visible[pending.prior_tail.page_id] = self._physical[pending.prior_tail.page_id]
        stream = self._stream(pending.owner_layer, pending.owner_kv_head)
        if stream.first_ref is None:
            stream.first_ref = ref
        stream.tail_ref = ref
        stream.page_count += 1
        stream.total_valid_tokens += pending.valid_count
        del self._pending[ref]

    def atomic_metadata_publish(self, ref: PageRef, *, publication_action: Callable[[], None]) -> None:
        """Compatibility spelling for the sole ``metadata_publish_commit`` event."""
        self.metadata_publish_commit(ref, publication_action=publication_action)

    def visible_descriptor(self, ref: PageRef) -> PackedPageDescriptor:
        self._resolve(ref)
        self._require(
            self._allocator_event(lambda: self._allocator.state(ref)) is PageState.LIVE_PACKED,
            "descriptor is not visible before atomic publication",
        )
        descriptor = self._visible.get(ref.page_id)
        self._require(descriptor is not None and descriptor.generation == ref.generation, "descriptor visibility is stale")
        return descriptor

    def stream_descriptor(self, *, layer: int, kv_head: int) -> StreamDescriptor:
        return replace(self._stream(layer, kv_head))

    def retain_live_reference(self, ref: PageRef) -> None:
        self._require_active()
        self._allocator_event(lambda: self._allocator.retain_live_reference(ref))

    def release_live_reference(self, ref: PageRef) -> None:
        self._require_active_or_retiring()
        self._allocator_event(lambda: self._allocator.release_live_reference(ref))

    def request_retire(self, identity: TransactionIdentity) -> None:
        """External runtime starts retirement; new allocation/publication stops immediately."""
        self._require(self._initialized and self._state is PageManagerState.ACTIVE, "retire request requires an active page manager")
        self._require(
            isinstance(identity, TransactionIdentity) and 0 <= identity.request_id < 8 and 0 <= identity.incarnation < 4,
            "retire identity exceeds the selected A3 namespace",
        )
        self._retire_identity = identity
        self._state = PageManagerState.RETIRING

    def mark_page_quiescent(self, ref: PageRef, *, quiescence: set[str] | frozenset[str]) -> None:
        self._require(self._state is PageManagerState.RETIRING, "page quiescence requires a runtime retirement request")
        self._require(set(quiescence) == PAGE_GENERATION_WRAP_QUIESCENCE, "page quiescence predicate is incomplete")
        self._allocator_event(lambda: self._allocator.mark_no_live_reference(ref))

    def authorize_generation_wrap(self, ref: PageRef, *, quiescence: set[str] | frozenset[str]) -> None:
        self._require(self._state is PageManagerState.RETIRING, "generation wrap authorization requires retirement")
        self._allocator_event(lambda: self._allocator.authorize_generation_wrap(ref, quiescence))

    def begin_descriptor_invalidate(self, ref: PageRef) -> DescriptorOperation:
        self._require(self._state is PageManagerState.RETIRING, "descriptor invalidation requires retirement")
        self._require(
            self._allocator_event(lambda: self._allocator.state(ref)) is PageState.RECLAIMABLE,
            "descriptor invalidation requires no live reference",
        )
        self._require(len(self._operations) < MAX_DESCRIPTOR_MAINTENANCE_OPS, "descriptor maintenance bound is exhausted")
        operation_id = self._operation_id(DescriptorOperationKind.INVALIDATE, ref, ref)
        self._require(operation_id not in self._operations, "descriptor invalidation is already live")
        operation = DescriptorOperation(operation_id, DescriptorOperationKind.INVALIDATE, ref, ref, self.descriptor_location(ref.page_id))
        self._operations[operation_id] = operation
        return operation

    def finish_reclaim(self, ref: PageRef) -> None:
        self._require(self._state is PageManagerState.RETIRING, "reclaim requires retirement")
        self._require(ref in self._completed_reclaims, "generation advance requires durable descriptor invalidation")
        self._completed_reclaims.remove(ref)
        self._allocator_event(lambda: self._allocator.reclaim(ref))
        self._active_refs.remove(ref)
        self._visible.pop(ref.page_id, None)

    def retire_ack(self) -> TransactionIdentity:
        self._require(self._state is PageManagerState.RETIRING and self._retire_identity is not None, "retire acknowledgement requires a live retirement")
        self._require(not self._active_refs and not self._pending and not self._operations and not self._completed_reclaims, "retire acknowledgement requires full descriptor/page drain")
        for stream in self._streams.values():
            stream.first_ref = stream.tail_ref = None
            stream.page_count = stream.total_valid_tokens = 0
        self._state = PageManagerState.RETIRED
        return self._retire_identity

    def destructive_reset(self) -> None:
        """Invalidate local ownership; raw HBM bytes are deliberately not erased."""
        self._initialized = False
        self._state = PageManagerState.RESET
        self._pending.clear()
        self._operations.clear()
        self._completed_reclaims.clear()
        self._active_refs.clear()
        self._visible.clear()

    def acknowledge_init_done(self, *, core_mem_initialized: bool) -> None:
        self._require(not self._initialized and self._state is PageManagerState.RESET, "page manager is not awaiting init")
        self._require(core_mem_initialized, "page-manager init requires R1 mem_init_done")
        self._allocator = PageAllocatorReference(self._page_pool_pages, generation_width=self._generation_width)
        self._streams = {(layer, head): StreamDescriptor(layer, head) for layer in range(self._layer_count) for head in range(self._kv_head_count)}
        self._retire_identity = None
        self._initialized = True
        self._state = PageManagerState.ACTIVE

    def _prepared_new_descriptor(self, ref: PageRef, descriptor: PackedPageDescriptor) -> None:
        # The value is retained privately until the corresponding line write commits.
        self._physical.setdefault(ref.page_id, descriptor)

    def _prepared_descriptor(self, ref: PageRef) -> PackedPageDescriptor:
        pending = self._pending[ref]
        return PackedPageDescriptor(DescriptorState.LIVE_PACKED, pending.owner_layer, pending.owner_kv_head, pending.valid_count, ref.generation, None)

    def _free_descriptor_for_next_generation(self, ref: PageRef) -> PackedPageDescriptor:
        modulus = 2**self._generation_width
        generation = 0 if ref.generation + 1 == modulus else ref.generation + 1
        return PackedPageDescriptor(DescriptorState.FREE, 0, 0, 0, generation, None)

    def _operation_id(self, kind: DescriptorOperationKind, subject: PageRef, target: PageRef) -> str:
        return f"{kind.value}:{subject.page_id}:{subject.generation}:{target.page_id}:{target.generation}"

    def _stream(self, layer: int, kv_head: int) -> StreamDescriptor:
        self._validate_owner(layer, kv_head)
        return self._streams[(layer, kv_head)]

    def _resolve(self, ref: PageRef) -> None:
        self._allocator_event(lambda: self._allocator.state(ref))

    @staticmethod
    def _allocator_event(action: Callable[[], _Result]) -> _Result:
        try:
            return action()
        except ProfileViolation as exc:
            raise PageManagerViolation(str(exc)) from exc

    def _validate_owner(self, layer: int, kv_head: int) -> None:
        self._require(0 <= layer < self._layer_count and 0 <= kv_head < self._kv_head_count, "stream owner is outside the selected anchor")

    def _require_active(self) -> None:
        self._require(self._initialized and self._state is PageManagerState.ACTIVE, "page-manager operation requires an active session")

    def _require_active_or_retiring(self) -> None:
        self._require(self._initialized and self._state in {PageManagerState.ACTIVE, PageManagerState.RETIRING}, "page-manager operation requires an initialized session")

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise PageManagerViolation(message)
