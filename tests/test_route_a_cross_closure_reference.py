import pytest

from kvpress.route_a_arbitration_reference import RouteAArbitrationReference
from kvpress.route_a_architecture_reference import RouteAArchitectureReference
from kvpress.route_a_core_memory_reference import CORE_MEM_FRAGMENT_BYTES, CoreMemoryWrapperReference, CoreWriteData, CoreWriteRequest, MemoryStatus, TransactionIdentity
from kvpress.route_a_cross_closure_reference import (
    CrossClosureViolation,
    DescriptorMaintenanceBinding,
    DescriptorMaintenanceTransportReference,
    metadata_publish_commit,
)
from kvpress.route_a_m2_p3_reference import M2Access, M2Member, M2Object, M2Operation, M2GroupState, P3StageState, RouteAM2P3Reference
from kvpress.route_a_page_manager_reference import DescriptorState, PageManagerViolation, RouteAPageManagerReference


def _transport() -> tuple[RouteAPageManagerReference, DescriptorMaintenanceTransportReference]:
    manager = RouteAPageManagerReference(page_pool_pages=4, layer_count=1, kv_head_count=1, generation_width=2)
    memory = CoreMemoryWrapperReference()
    memory.acknowledge_mem_init_done(adapter_epoch=0)
    transport = DescriptorMaintenanceTransportReference(
        arbitration=RouteAArbitrationReference(),
        memory=memory,
        page_manager=manager,
    )
    return manager, transport


def test_r5_descriptor_maintenance_has_one_r2_to_r1_path_and_is_durable_only_before_publication():
    manager, transport = _transport()
    page = manager.allocate_page(layer=0, kv_head=0)
    manager.payload_write_commit(page)
    operation = manager.begin_descriptor_prepare(page, layer=0, kv_head=0, valid_count=64)[0]
    transport.bind(DescriptorMaintenanceBinding(operation, TransactionIdentity(0, 0), bytes(64), 0))
    assert transport.grant_next() == operation.operation_id
    transport.send_line_data(operation.operation_id)
    assert transport.terminal(operation.operation_id, status=MemoryStatus.OK, adapter_epoch=0) == "descriptor_durable_only"

    assert manager.descriptor_prepare_ready(page)
    with pytest.raises(PageManagerViolation, match="not visible"):
        manager.visible_descriptor(page)
    manager.metadata_publish_commit(page, publication_action=lambda: None)
    assert manager.visible_descriptor(page).state is DescriptorState.LIVE_PACKED


def test_descriptor_transport_rejects_non_fragment_line_and_faults_without_publication_or_fallback():
    manager, transport = _transport()
    page = manager.allocate_page(layer=0, kv_head=0)
    manager.payload_write_commit(page)
    operation = manager.begin_descriptor_prepare(page, layer=0, kv_head=0, valid_count=1)[0]
    with pytest.raises(CrossClosureViolation, match="64-B"):
        transport.bind(DescriptorMaintenanceBinding(operation, TransactionIdentity(0, 0), bytes(63), 0))

    transport.bind(DescriptorMaintenanceBinding(operation, TransactionIdentity(0, 0), bytes(64), 0))
    assert transport.grant_next() == operation.operation_id
    assert transport.terminal(operation.operation_id, status=MemoryStatus.FAULT, adapter_epoch=0) == "fault"
    with pytest.raises(PageManagerViolation, match="active session"):
        manager.metadata_publish_commit(page, publication_action=lambda: None)


def test_r3_r5_and_lifecycle_share_exactly_one_metadata_publish_commit():
    manager, transport = _transport()
    page = manager.allocate_page(layer=0, kv_head=0)
    manager.payload_write_commit(page)
    operation = manager.begin_descriptor_prepare(page, layer=0, kv_head=0, valid_count=1)[0]
    transport.bind(DescriptorMaintenanceBinding(operation, TransactionIdentity(0, 0), bytes(64), 0))
    assert transport.grant_next() == operation.operation_id
    transport.send_line_data(operation.operation_id)
    assert transport.terminal(operation.operation_id, status=MemoryStatus.OK, adapter_epoch=0) == "descriptor_durable_only"

    m2 = RouteAM2P3Reference()
    m2.acknowledge_init_done(core_mem_initialized=True)
    generation = m2.claim_p3_stage(layer=0, kv_head=0, owner="owner", page_ref="page:0", valid_records=1)
    m2.open_m2_group("g0", layer=0, kv_head=0, owner="owner", stage_generation=generation)
    for operation_id, object_kind, member in (
        ("head", M2Object.HEAD_CONTROL, M2Member.HEAD_CONTROL_RMW),
        ("span", M2Object.SPAN_OWNER, M2Member.SPAN_OWNER_RMW),
    ):
        assert m2.submit_m2_op(M2Operation(operation_id, 0, object_kind, M2Access.RMW, operation_id, "owner", "g0", member))
        m2.receive_m2_op_rsp(operation_id, status=MemoryStatus.OK)
    assert m2.m2_group_state("g0") is M2GroupState.STAGED
    m2.bind_position_sidecar(layer=0, generation=generation, owner="owner", record_ordinal=0, logical_position=128)
    assert m2.begin_p3_read(layer=0, generation=generation, owner="owner")
    for index in range(8):
        m2.receive_p3_read_fragment(layer=0, generation=generation, owner="owner", fragment_index=index, last=index == 7, data=bytes(CORE_MEM_FRAGMENT_BYTES))
    assert m2.p3_stage_state(layer=0, generation=generation) is P3StageState.COMPLETE
    assert m2.begin_p3_write(layer=0, generation=generation, owner="owner")
    memory = CoreMemoryWrapperReference()
    memory.acknowledge_mem_init_done(adapter_epoch=0)
    identity = TransactionIdentity(1, 0)
    memory.accept_write(CoreWriteRequest(identity, "packed:0", 8))
    for index in range(8):
        memory.accept_write_data(CoreWriteData(identity, index, index == 7, bytes(CORE_MEM_FRAGMENT_BYTES)))
    assert memory.receive_write_commit(identity, status=MemoryStatus.OK, adapter_epoch=0) == "payload_durable_only"
    m2.record_p3_write_terminal(layer=0, generation=generation, owner="owner", status=MemoryStatus.OK, r1_payload_durable=memory.durable(identity))
    m2.mark_payload_durable("g0", stage_generation=generation, r1_payload_durable=memory.durable(identity))

    lifecycle = RouteAArchitectureReference()
    lifecycle.seed_pending("t0")
    lifecycle.open_packed_write(1, "t0")
    lifecycle.page_write_commit(1, "t0")
    lifecycle.begin_metadata_group("g0", ("t0",))
    lifecycle.stage_metadata_member("g0", "t0")
    assert metadata_publish_commit(
        m2_p3=m2,
        group_id="g0",
        page_manager=manager,
        page_ref=page,
        lifecycle_publication=lambda: lifecycle.metadata_atomic_publish("g0"),
    )
    assert lifecycle.authority("t0") == "packed"
    assert manager.visible_descriptor(page).state is DescriptorState.LIVE_PACKED
    assert m2.m2_group_state("g0") is M2GroupState.PUBLISHED
