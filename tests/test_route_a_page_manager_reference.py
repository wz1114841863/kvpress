import pytest

from kvpress.route_a_architecture_reference import RouteAArchitectureReference
from kvpress.route_a_core_memory_reference import TransactionIdentity
from kvpress.route_a_page_manager_reference import (
    ANCHOR_ALLOCATOR_BITMAP_BYTES,
    ANCHOR_DESCRIPTOR_REGION_BYTES,
    ANCHOR_STREAM_DESCRIPTOR_COUNT,
    DESCRIPTOR_BYTES,
    DescriptorState,
    PageManagerState,
    PageManagerViolation,
    PackedPageDescriptor,
    RouteAPageManagerReference,
)
from kvpress.route_a_rtl_profile import PAGE_GENERATION_WRAP_QUIESCENCE, PageRef


def _manager() -> RouteAPageManagerReference:
    return RouteAPageManagerReference(page_pool_pages=4, layer_count=1, kv_head_count=1, generation_width=2)


def _publish_first_page(manager: RouteAPageManagerReference, *, valid_count: int = 64) -> PageRef:
    ref = manager.allocate_page(layer=0, kv_head=0)
    manager.payload_write_commit(ref)
    for operation in manager.begin_descriptor_prepare(ref, layer=0, kv_head=0, valid_count=valid_count):
        manager.complete_descriptor_operation(operation.operation_id, success=True)
    manager.atomic_metadata_publish(ref, publication_action=lambda: None)
    return ref


def test_anchor_descriptor_capacity_stream_count_and_address_map_are_fixed_but_outside_payload_pool():
    assert ANCHOR_STREAM_DESCRIPTOR_COUNT == 288
    assert ANCHOR_DESCRIPTOR_REGION_BYTES == 146_880 * DESCRIPTOR_BYTES == 2_350_080
    assert ANCHOR_ALLOCATOR_BITMAP_BYTES == 18_360

    manager = _manager()
    ref = manager.allocate_page(layer=0, kv_head=0)
    location = manager.descriptor_location(ref.page_id)
    assert (location.entry_offset_bytes, location.core_fragment_index, location.lane) == (0, 0, 0)
    assert manager.payload_offset(ref) == 0
    assert manager.sidecar_offset(ref) == 32_768
    assert manager.migration_reserve_offset() == 4 * 33_280
    assert manager.descriptor_region_bytes() == 4 * DESCRIPTOR_BYTES


def test_128_bit_descriptor_uses_table_index_for_payload_and_sidecar_handle_derivation():
    descriptor = PackedPageDescriptor(
        DescriptorState.LIVE_PACKED,
        owner_layer=35,
        owner_kv_head=7,
        valid_count=64,
        generation=8,
        next_ref=PageRef(17, 3),
    )
    encoded = descriptor.encode()
    assert len(encoded) == 16
    assert PackedPageDescriptor.decode(encoded) == descriptor
    with pytest.raises(PageManagerViolation, match="reserved"):
        PackedPageDescriptor.decode((int.from_bytes(encoded, "little") | (1 << 52)).to_bytes(16, "little"))


def test_descriptor_visibility_and_stream_update_share_the_existing_atomic_publication_boundary():
    manager = _manager()
    page = manager.allocate_page(layer=0, kv_head=0)
    manager.payload_write_commit(page)
    operations = manager.begin_descriptor_prepare(page, layer=0, kv_head=0, valid_count=64)
    with pytest.raises(PageManagerViolation, match="not visible"):
        manager.visible_descriptor(page)
    for operation in operations:
        manager.complete_descriptor_operation(operation.operation_id, success=True)

    lifecycle = RouteAArchitectureReference()
    lifecycle.seed_pending("t0")
    lifecycle.open_packed_write(1, "t0")
    lifecycle.page_write_commit(1, "t0")
    lifecycle.begin_metadata_group("g0", ("t0",))
    lifecycle.stage_metadata_member("g0", "t0")
    manager.atomic_metadata_publish(page, publication_action=lambda: lifecycle.metadata_atomic_publish("g0"))
    assert lifecycle.authority("t0") == "packed"
    assert manager.visible_descriptor(page).state is DescriptorState.LIVE_PACKED
    stream = manager.stream_descriptor(layer=0, kv_head=0)
    assert (stream.first_ref, stream.tail_ref, stream.page_count, stream.total_valid_tokens) == (page, page, 1, 64)


def test_append_tail_link_is_private_until_the_second_page_publication():
    manager = _manager()
    first = _publish_first_page(manager)
    second = manager.allocate_page(layer=0, kv_head=0)
    manager.payload_write_commit(second)
    operations = manager.begin_descriptor_prepare(second, layer=0, kv_head=0, valid_count=5)
    assert {operation.kind.value for operation in operations} == {"new_page", "tail_link"}
    for operation in operations:
        manager.complete_descriptor_operation(operation.operation_id, success=True)
    assert manager.visible_descriptor(first).next_ref is None
    manager.atomic_metadata_publish(second, publication_action=lambda: None)
    assert manager.visible_descriptor(first).next_ref == second
    stream = manager.stream_descriptor(layer=0, kv_head=0)
    assert (stream.page_count, stream.total_valid_tokens, stream.tail_valid_count()) == (2, 69, 5)


def test_descriptor_fault_is_fail_closed_and_cannot_publish_or_fallback():
    manager = _manager()
    page = manager.allocate_page(layer=0, kv_head=0)
    manager.payload_write_commit(page)
    operation = manager.begin_descriptor_prepare(page, layer=0, kv_head=0, valid_count=1)[0]
    manager.complete_descriptor_operation(operation.operation_id, success=False)
    assert manager.state is PageManagerState.FAULTED
    with pytest.raises(PageManagerViolation, match="active session"):
        manager.atomic_metadata_publish(page, publication_action=lambda: None)


def test_two_live_descriptor_maintenance_operations_are_a_logical_bound_not_a_port_claim():
    manager = RouteAPageManagerReference(page_pool_pages=4, layer_count=1, kv_head_count=2, generation_width=2)
    _publish_first_page(manager)
    second = manager.allocate_page(layer=0, kv_head=0)
    manager.payload_write_commit(second)
    assert len(manager.begin_descriptor_prepare(second, layer=0, kv_head=0, valid_count=1)) == 2

    other = manager.allocate_page(layer=0, kv_head=1)
    manager.payload_write_commit(other)
    with pytest.raises(PageManagerViolation, match="bound is exhausted"):
        manager.begin_descriptor_prepare(other, layer=0, kv_head=1, valid_count=1)


def test_retirement_serializes_new_admission_and_requires_descriptor_invalidation_before_generation_reuse():
    manager = _manager()
    page = _publish_first_page(manager)
    manager.retain_live_reference(page)
    retirement = TransactionIdentity(3, 1)
    manager.request_retire(retirement)
    with pytest.raises(PageManagerViolation, match="active session"):
        manager.allocate_page(layer=0, kv_head=0)
    manager.release_live_reference(page)
    manager.mark_page_quiescent(page, quiescence=PAGE_GENERATION_WRAP_QUIESCENCE)
    operation = manager.begin_descriptor_invalidate(page)
    manager.complete_descriptor_operation(operation.operation_id, success=True)
    manager.finish_reclaim(page)
    assert manager.retire_ack() == retirement
    assert manager.state is PageManagerState.RETIRED
    with pytest.raises(PageManagerViolation, match="stale or free"):
        manager.visible_descriptor(page)


def test_retirement_identity_is_limited_to_the_selected_a3_namespace():
    manager = _manager()
    with pytest.raises(PageManagerViolation, match="selected A3 namespace"):
        manager.request_retire(TransactionIdentity(8, 0))


def test_destructive_reset_invalidates_local_ownership_until_r1_initialization_is_reacknowledged():
    manager = _manager()
    page = manager.allocate_page(layer=0, kv_head=0)
    manager.destructive_reset()
    with pytest.raises(PageManagerViolation, match="active session"):
        manager.allocate_page(layer=0, kv_head=0)
    manager.acknowledge_init_done(core_mem_initialized=True)
    assert manager.state is PageManagerState.ACTIVE
    # Old-page transport responses are R1's responsibility; R5 only restores
    # a fresh local ownership namespace after that adapter handshake.
    assert manager.allocate_page(layer=0, kv_head=0).page_id == page.page_id
