"""Event-level RTL3.2-A packed-read association-owner reference.

This pure-software reference closes only the cross-owner association that is
required before a packed page can enter the existing R2/R1 typed read path.
It has no cycle model and creates neither a scheduler, page table, authority
table, memory controller, S2 storage implementation, nor payload deposit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from kvpress.route_a_core_memory_reference import TransactionIdentity
from kvpress.route_a_rtl_profile import PageRef


MAX_PAGE_RECORDS = 64
FRAGMENTS_PER_RECORD = 8


class PackedReadAssociationViolation(AssertionError):
    """Raised when a cross-owner packed-read fact is absent or inconsistent."""


class AssociationState(str, Enum):
    WAITING = "waiting_for_complete_grants"
    R2_ALLOCATION_REQUESTED = "r2_allocation_requested"
    ISSUED = "issued_to_r2_r1"
    TERMINAL = "terminal"
    CANCELLED = "cancelled_before_issue"


@dataclass(frozen=True)
class PackedSourceDemand:
    """Immutable preselected packed source; this reference never selects it."""

    identity: TransactionIdentity
    page_ref: PageRef
    arrival_ordinal: int
    candidate_id: int
    eligibility_snapshot: int
    destination_endpoint: int


@dataclass(frozen=True)
class PublicationReadAuthorization:
    """R3 reply proving this page is currently published and packed-authoritative."""

    identity: TransactionIdentity
    page_ref: PageRef
    transaction_group_tag: int
    valid_records: int
    packed_authoritative: bool


@dataclass(frozen=True)
class DescriptorLocationGrant:
    """R5-owned live descriptor/location grant for the exact PageRef generation."""

    identity: TransactionIdentity
    page_ref: PageRef
    payload_handle_or_address: int
    sidecar_handle_or_address: int
    valid_records: int
    sidecar_records: int
    live_reference_held: bool


@dataclass(frozen=True)
class S2FillLease:
    """S2-owned slot/generation lease; it is not an S2 allocation policy."""

    identity: TransactionIdentity
    page_ref: PageRef
    s2_slot: int
    source_generation: int
    requires_sidecar: bool


@dataclass(frozen=True)
class R2PackedReadAllocationRequest:
    """Opaque scheduler facts forwarded to R2; the association owner never edits them."""

    identity: TransactionIdentity
    candidate_class: str
    arrival_ordinal: int
    candidate_id: int
    eligibility_snapshot: int
    destination_endpoint: int
    page_ref: PageRef
    payload_handle_or_address: int
    expected_fragment_count: int
    s2_slot: int
    source_generation: int
    requires_sidecar: bool


@dataclass(frozen=True)
class PackedS2ReadWork:
    """One exact typed-work descriptor for the existing packed-S2 read producer."""

    allocation: R2PackedReadAllocationRequest
    delivery_context_ref: int
    valid_records: int
    sidecar_handle_or_address: int
    sidecar_records: int


@dataclass(frozen=True)
class AssociationRelease:
    """Post-terminal release observation routed to the original R5/S2 owners."""

    identity: TransactionIdentity
    page_ref: PageRef
    s2_slot: int
    source_generation: int
    terminal_status: str


@dataclass
class _Association:
    demand: PackedSourceDemand | None = None
    publication: PublicationReadAuthorization | None = None
    descriptor: DescriptorLocationGrant | None = None
    lease: S2FillLease | None = None
    state: AssociationState = AssociationState.WAITING
    delivery_context_ref: int | None = None


class PackedReadAssociationReference:
    """Sole executable model of the named RTL3.2-A association owner.

    Producers may present the four grants in any event order.  The owner emits
    no R2 request until all four refer to the same live identity/PageRef and
    all R3/R5/S2 obligations are exact.  It does not allocate a page, choose a
    page, choose an S2 slot, choose R2 priority, or deposit a payload.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._associations: dict[TransactionIdentity, _Association] = {}

    def acknowledge_init(self) -> None:
        self._initialized = True

    def destructive_reset(self) -> None:
        self._initialized = False
        self._associations.clear()

    def accept_demand(self, demand: PackedSourceDemand) -> None:
        self._require_initialized()
        self._validate_demand(demand)
        association = self._association(demand.identity)
        self._set_once(association, "demand", demand)

    def accept_publication_authorization(self, authorization: PublicationReadAuthorization) -> None:
        self._require_initialized()
        self._validate_record_count(authorization.valid_records)
        self._require(authorization.packed_authoritative, "R3 authorization is not packed-authoritative")
        association = self._association(authorization.identity)
        self._check_page(association, authorization.page_ref)
        self._set_once(association, "publication", authorization)

    def accept_descriptor_location(self, grant: DescriptorLocationGrant) -> None:
        self._require_initialized()
        self._validate_record_count(grant.valid_records)
        self._require(grant.sidecar_records == grant.valid_records, "R5 sidecar record count must equal valid records")
        self._require(grant.live_reference_held, "R5 must retain a live page reference before packed read association")
        self._require(grant.payload_handle_or_address >= 0 and grant.sidecar_handle_or_address >= 0, "R5 location handles must be non-negative")
        association = self._association(grant.identity)
        self._check_page(association, grant.page_ref)
        self._set_once(association, "descriptor", grant)

    def accept_s2_lease(self, lease: S2FillLease) -> None:
        self._require_initialized()
        self._require(lease.s2_slot >= 0 and lease.source_generation >= 0, "S2 slot/generation must be non-negative")
        self._require(lease.requires_sidecar, "packed S2 fill must retain its sidecar obligation")
        association = self._association(lease.identity)
        self._check_page(association, lease.page_ref)
        self._set_once(association, "lease", lease)

    def request_r2_allocation(self, identity: TransactionIdentity) -> R2PackedReadAllocationRequest:
        association = self._complete(identity)
        self._require(association.state is AssociationState.WAITING, "association is not eligible for a fresh R2 allocation request")
        demand = self._required(association.demand, "packed source demand")
        descriptor = self._required(association.descriptor, "R5 descriptor location")
        lease = self._required(association.lease, "S2 fill lease")
        allocation = R2PackedReadAllocationRequest(
            identity=identity,
            candidate_class="s2_packed",
            arrival_ordinal=demand.arrival_ordinal,
            candidate_id=demand.candidate_id,
            eligibility_snapshot=demand.eligibility_snapshot,
            destination_endpoint=demand.destination_endpoint,
            page_ref=demand.page_ref,
            payload_handle_or_address=descriptor.payload_handle_or_address,
            expected_fragment_count=descriptor.valid_records * FRAGMENTS_PER_RECORD,
            s2_slot=lease.s2_slot,
            source_generation=lease.source_generation,
            requires_sidecar=True,
        )
        association.state = AssociationState.R2_ALLOCATION_REQUESTED
        return allocation

    def accept_r2_allocation(self, identity: TransactionIdentity, *, delivery_context_ref: int) -> PackedS2ReadWork:
        association = self._complete(identity)
        self._require(association.state is AssociationState.R2_ALLOCATION_REQUESTED, "R2 allocation acknowledgement is not currently expected")
        self._require(delivery_context_ref >= 0, "R2 delivery context must be non-negative")
        descriptor = self._required(association.descriptor, "R5 descriptor location")
        allocation = self._allocation_from_association(identity, association)
        association.delivery_context_ref = delivery_context_ref
        association.state = AssociationState.ISSUED
        return PackedS2ReadWork(
            allocation=allocation,
            delivery_context_ref=delivery_context_ref,
            valid_records=descriptor.valid_records,
            sidecar_handle_or_address=descriptor.sidecar_handle_or_address,
            sidecar_records=descriptor.sidecar_records,
        )

    def cancel_before_issue_for_descriptor_invalidation(self, identity: TransactionIdentity) -> None:
        association = self._association(identity)
        self._require(association.state is AssociationState.WAITING, "R5 invalidation must wait for a live issued association to terminally release")
        association.state = AssociationState.CANCELLED

    def terminal(self, identity: TransactionIdentity, *, status: str) -> AssociationRelease:
        association = self._association(identity)
        self._require(association.state is AssociationState.ISSUED, "only an issued packed read may terminally release R5/S2 grants")
        self._require(status in {"ok", "fault"}, "terminal status must be ok or fault")
        demand = self._required(association.demand, "packed source demand")
        lease = self._required(association.lease, "S2 fill lease")
        association.state = AssociationState.TERMINAL
        return AssociationRelease(identity, demand.page_ref, lease.s2_slot, lease.source_generation, status)

    def state(self, identity: TransactionIdentity) -> AssociationState:
        return self._association(identity).state

    def _complete(self, identity: TransactionIdentity) -> _Association:
        association = self._association(identity)
        self._require(association.demand is not None, "missing immutable packed source demand")
        self._require(association.publication is not None, "missing live R3 publication authorization")
        self._require(association.descriptor is not None, "missing live R5 descriptor location grant")
        self._require(association.lease is not None, "missing S2 fill lease")
        demand = self._required(association.demand, "packed source demand")
        publication = self._required(association.publication, "R3 publication authorization")
        descriptor = self._required(association.descriptor, "R5 descriptor location")
        lease = self._required(association.lease, "S2 fill lease")
        self._require(publication.page_ref == demand.page_ref == descriptor.page_ref == lease.page_ref, "cross-owner PageRef/generation mismatch")
        self._require(publication.valid_records == descriptor.valid_records, "R3/R5 valid-record count mismatch")
        return association

    def _allocation_from_association(self, identity: TransactionIdentity, association: _Association) -> R2PackedReadAllocationRequest:
        demand = self._required(association.demand, "packed source demand")
        descriptor = self._required(association.descriptor, "R5 descriptor location")
        lease = self._required(association.lease, "S2 fill lease")
        return R2PackedReadAllocationRequest(
            identity=identity,
            candidate_class="s2_packed",
            arrival_ordinal=demand.arrival_ordinal,
            candidate_id=demand.candidate_id,
            eligibility_snapshot=demand.eligibility_snapshot,
            destination_endpoint=demand.destination_endpoint,
            page_ref=demand.page_ref,
            payload_handle_or_address=descriptor.payload_handle_or_address,
            expected_fragment_count=descriptor.valid_records * FRAGMENTS_PER_RECORD,
            s2_slot=lease.s2_slot,
            source_generation=lease.source_generation,
            requires_sidecar=True,
        )

    def _association(self, identity: TransactionIdentity) -> _Association:
        self._require(isinstance(identity, TransactionIdentity), "association identity must use the frozen R1/R6 identity type")
        return self._associations.setdefault(identity, _Association())

    @staticmethod
    def _set_once(association: _Association, name: str, value: object) -> None:
        current = getattr(association, name)
        if current is not None:
            raise PackedReadAssociationViolation(f"duplicate {name} grant")
        if association.state is not AssociationState.WAITING:
            raise PackedReadAssociationViolation("cannot mutate an association after R2 allocation begins")
        setattr(association, name, value)

    @staticmethod
    def _check_page(association: _Association, page_ref: PageRef) -> None:
        if association.demand is not None and association.demand.page_ref != page_ref:
            raise PackedReadAssociationViolation("grant PageRef/generation mismatches immutable packed source demand")

    @staticmethod
    def _validate_record_count(value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_PAGE_RECORDS:
            raise PackedReadAssociationViolation("packed valid-record count must be within 1..64")

    @staticmethod
    def _validate_demand(demand: PackedSourceDemand) -> None:
        if not isinstance(demand.identity, TransactionIdentity) or not isinstance(demand.page_ref, PageRef):
            raise PackedReadAssociationViolation("packed source demand must carry frozen identity and PageRef")
        if min(demand.arrival_ordinal, demand.candidate_id, demand.eligibility_snapshot, demand.destination_endpoint) < 0:
            raise PackedReadAssociationViolation("opaque R2 scheduler facts must be non-negative")

    def _require_initialized(self) -> None:
        self._require(self._initialized, "packed-read association is gated until reset/init completion")

    @staticmethod
    def _required(value: object | None, description: str):
        if value is None:
            raise PackedReadAssociationViolation(f"missing {description}")
        return value

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise PackedReadAssociationViolation(message)
