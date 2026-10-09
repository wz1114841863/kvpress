import copy

import pytest

from kvpress.route_a_core_memory_reference import TransactionIdentity
from kvpress.route_a_rtl_profile import PageRef
from kvpress.rtl3_2a_packed_read_association_reference import (
    AssociationState,
    DescriptorLocationGrant,
    PackedReadAssociationReference,
    PackedReadAssociationViolation,
    PackedSourceDemand,
    PublicationReadAuthorization,
    S2FillLease,
)


IDENTITY = TransactionIdentity(request_id=2, incarnation=1)
PAGE = PageRef(page_id=17, generation=4)


def demand(page: PageRef = PAGE) -> PackedSourceDemand:
    return PackedSourceDemand(IDENTITY, page, arrival_ordinal=7, candidate_id=3, eligibility_snapshot=0x1F, destination_endpoint=1)


def publication(page: PageRef = PAGE, records: int = 5) -> PublicationReadAuthorization:
    return PublicationReadAuthorization(IDENTITY, page, transaction_group_tag=9, valid_records=records, packed_authoritative=True)


def descriptor(page: PageRef = PAGE, records: int = 5) -> DescriptorLocationGrant:
    return DescriptorLocationGrant(IDENTITY, page, payload_handle_or_address=0x1234, sidecar_handle_or_address=0x5678, valid_records=records, sidecar_records=records, live_reference_held=True)


def lease(page: PageRef = PAGE) -> S2FillLease:
    return S2FillLease(IDENTITY, page, s2_slot=1, source_generation=6, requires_sidecar=True)


def complete(reference: PackedReadAssociationReference) -> None:
    # Grant event ordering is unconstrained; all fields must still join exactly.
    reference.accept_s2_lease(lease())
    reference.accept_descriptor_location(descriptor())
    reference.accept_demand(demand())
    reference.accept_publication_authorization(publication())


def test_exact_cross_owner_join_forwards_opaque_r2_facts_and_page_shape_without_selecting_them():
    reference = PackedReadAssociationReference()
    reference.acknowledge_init()
    complete(reference)
    allocation = reference.request_r2_allocation(IDENTITY)
    assert allocation.candidate_class == "s2_packed"
    assert allocation.arrival_ordinal == 7
    assert allocation.candidate_id == 3
    assert allocation.eligibility_snapshot == 0x1F
    assert allocation.expected_fragment_count == 40
    assert allocation.page_ref == PAGE
    work = reference.accept_r2_allocation(IDENTITY, delivery_context_ref=11)
    assert work.delivery_context_ref == 11
    assert work.valid_records == 5
    assert work.sidecar_handle_or_address == 0x5678
    assert work.sidecar_records == 5
    assert reference.state(IDENTITY) is AssociationState.ISSUED
    release = reference.terminal(IDENTITY, status="ok")
    assert release.page_ref == PAGE
    assert release.s2_slot == 1
    assert reference.state(IDENTITY) is AssociationState.TERMINAL


@pytest.mark.parametrize(
    "bad_grant",
    [
        lambda reference: reference.accept_publication_authorization(publication(page=PageRef(page_id=18, generation=4))),
        lambda reference: reference.accept_descriptor_location(descriptor(records=4)),
        lambda reference: reference.accept_s2_lease(lease(page=PageRef(page_id=17, generation=5))),
    ],
)
def test_mismatched_page_generation_or_population_fails_closed_without_r2_work(bad_grant):
    reference = PackedReadAssociationReference()
    reference.acknowledge_init()
    reference.accept_demand(demand())
    reference.accept_publication_authorization(publication())
    reference.accept_descriptor_location(descriptor())
    before = copy.deepcopy(reference.__dict__)
    with pytest.raises(PackedReadAssociationViolation):
        bad_grant(reference)
    assert reference.__dict__ == before
    with pytest.raises(PackedReadAssociationViolation, match="missing S2 fill lease"):
        reference.request_r2_allocation(IDENTITY)


def test_r3_r5_population_mismatch_is_rejected_at_the_exact_join_before_r2_allocation():
    reference = PackedReadAssociationReference()
    reference.acknowledge_init()
    reference.accept_demand(demand())
    reference.accept_publication_authorization(publication(records=5))
    reference.accept_descriptor_location(descriptor(records=4))
    reference.accept_s2_lease(lease())
    with pytest.raises(PackedReadAssociationViolation, match="valid-record count mismatch"):
        reference.request_r2_allocation(IDENTITY)
    assert reference.state(IDENTITY) is AssociationState.WAITING


def test_invalidation_blocks_preissue_work_and_live_issue_must_terminally_release_before_invalidation():
    reference = PackedReadAssociationReference()
    reference.acknowledge_init()
    complete(reference)
    reference.cancel_before_issue_for_descriptor_invalidation(IDENTITY)
    assert reference.state(IDENTITY) is AssociationState.CANCELLED
    with pytest.raises(PackedReadAssociationViolation, match="not eligible"):
        reference.request_r2_allocation(IDENTITY)

    reference = PackedReadAssociationReference()
    reference.acknowledge_init()
    complete(reference)
    reference.request_r2_allocation(IDENTITY)
    reference.accept_r2_allocation(IDENTITY, delivery_context_ref=1)
    with pytest.raises(PackedReadAssociationViolation, match="must wait"):
        reference.cancel_before_issue_for_descriptor_invalidation(IDENTITY)
    release = reference.terminal(IDENTITY, status="fault")
    assert release.terminal_status == "fault"


def test_reset_gates_new_grants_and_discards_unissued_association_without_reinterpreting_it():
    reference = PackedReadAssociationReference()
    with pytest.raises(PackedReadAssociationViolation, match="gated"):
        reference.accept_demand(demand())
    reference.acknowledge_init()
    reference.accept_demand(demand())
    reference.destructive_reset()
    with pytest.raises(PackedReadAssociationViolation, match="gated"):
        reference.accept_publication_authorization(publication())
    reference.acknowledge_init()
    with pytest.raises(PackedReadAssociationViolation, match="missing immutable"):
        reference.request_r2_allocation(IDENTITY)
