import pytest

from kvpress.route_a_architecture_reference import RouteAArchitectureReference
from kvpress.route_a_arbitration_reference import ReadCandidate, RouteAArbitrationReference
from kvpress.route_a_core_memory_reference import (
    CORE_MEM_FRAGMENT_BYTES,
    CoreMemoryWrapperReference,
    CoreWriteData,
    CoreWriteRequest,
    MemoryStatus,
    TransactionIdentity,
)
from kvpress.route_a_m2_p3_reference import (
    M2Access,
    M2GroupState,
    M2Member,
    M2Object,
    M2Operation,
    M2P3Violation,
    P3_PAYLOAD_STAGE_BYTES,
    P3_RECORDS_PER_STAGE,
    P3StageState,
    RouteAM2P3Reference,
)


def _reference() -> RouteAM2P3Reference:
    reference = RouteAM2P3Reference()
    reference.acknowledge_init_done(core_mem_initialized=True)
    return reference


def _stage_and_group(reference: RouteAM2P3Reference, *, layer: int = 0, group_id: str = "g0") -> tuple[int, str]:
    owner = f"stream:{layer}:0"
    generation = reference.claim_p3_stage(
        layer=layer,
        kv_head=0,
        owner=owner,
        page_ref=f"page:{layer}",
        valid_records=1,
    )
    reference.open_m2_group(group_id, layer=layer, kv_head=0, owner=owner, stage_generation=generation)
    return generation, owner


def _stage_m2_members(reference: RouteAM2P3Reference, *, group_id: str, owner: str) -> None:
    head = M2Operation("head", 0, M2Object.HEAD_CONTROL, M2Access.RMW, "head:0", owner, group_id, M2Member.HEAD_CONTROL_RMW)
    span = M2Operation("span", 0, M2Object.SPAN_OWNER, M2Access.RMW, "span:0", owner, group_id, M2Member.SPAN_OWNER_RMW)
    assert reference.submit_m2_op(head)
    assert reference.submit_m2_op(span)
    reference.receive_m2_op_rsp("head", status=MemoryStatus.OK)
    reference.receive_m2_op_rsp("span", status=MemoryStatus.OK)
    assert reference.m2_group_state(group_id) is M2GroupState.STAGED


def _complete_p3_stage(reference: RouteAM2P3Reference, *, layer: int, generation: int, owner: str) -> None:
    reference.bind_position_sidecar(layer=layer, generation=generation, owner=owner, record_ordinal=0, logical_position=128)
    assert reference.begin_p3_read(layer=layer, generation=generation, owner=owner)
    for fragment_index in range(8):
        reference.receive_p3_read_fragment(
            layer=layer,
            generation=generation,
            owner=owner,
            fragment_index=fragment_index,
            last=fragment_index == 7,
            data=bytes(CORE_MEM_FRAGMENT_BYTES),
        )
    assert reference.p3_stage_state(layer=layer, generation=generation) is P3StageState.COMPLETE


def test_p3_anchor_capacity_and_sidecar_binding_are_logical_and_non_authoritative():
    reference = _reference()
    generation, owner = _stage_and_group(reference)
    assert P3_RECORDS_PER_STAGE == 64
    assert P3_PAYLOAD_STAGE_BYTES == 32_768
    assert reference.p3_stage_payload_bytes(layer=0, generation=generation) == 512
    assert not reference.p3_stage_is_authoritative(layer=0, generation=generation)
    reference.bind_position_sidecar(layer=0, generation=generation, owner=owner, record_ordinal=0, logical_position=128)
    with pytest.raises(M2P3Violation, match="duplicated"):
        reference.bind_position_sidecar(layer=0, generation=generation, owner=owner, record_ordinal=0, logical_position=128)
    with pytest.raises(M2P3Violation, match="64-record"):
        reference.claim_p3_stage(layer=1, kv_head=0, owner="stream:1:0", page_ref="page:1", valid_records=65)


def test_m2_req_ready_low_delays_without_staging_and_grouped_rmw_shape_is_fixed():
    reference = _reference()
    _, owner = _stage_and_group(reference)
    request = M2Operation("head", 0, M2Object.HEAD_CONTROL, M2Access.RMW, "head:0", owner, "g0", M2Member.HEAD_CONTROL_RMW)
    reference.set_channel_ready(m2_req=False)
    assert not reference.submit_m2_op(request)
    assert reference.m2_group_state("g0") is M2GroupState.OPEN
    reference.set_channel_ready(m2_req=True)
    assert reference.submit_m2_op(request)
    with pytest.raises(M2P3Violation, match="member/object"):
        reference.submit_m2_op(M2Operation("bad", 0, M2Object.SPAN_OWNER, M2Access.RMW, "span:0", owner, "g0", M2Member.HEAD_CONTROL_RMW))
    reference.receive_m2_op_rsp("head", status=MemoryStatus.OK)
    assert reference.m2_group_state("g0") is M2GroupState.OPEN


def test_p3_uses_one_logical_fill_and_one_logical_write_stream_without_selecting_physical_ports():
    reference = _reference()
    generation0, owner0 = _stage_and_group(reference, layer=0, group_id="g0")
    generation1, owner1 = _stage_and_group(reference, layer=1, group_id="g1")
    reference.set_channel_ready(p3_read=False)
    assert not reference.begin_p3_read(layer=0, generation=generation0, owner=owner0)
    assert reference.p3_stage_state(layer=0, generation=generation0) is P3StageState.RESERVED
    reference.set_channel_ready(p3_read=True)
    assert reference.begin_p3_read(layer=0, generation=generation0, owner=owner0)
    with pytest.raises(M2P3Violation, match="one logical P3 fill stream"):
        reference.begin_p3_read(layer=1, generation=generation1, owner=owner1)
    reference.fault_p3_read(layer=0, generation=generation0, owner=owner0)
    assert reference.m2_group_state("g0") is M2GroupState.FAULTED
    reference.abort_faulted_group("g0")
    assert reference.p3_slot_state(layer=0) is P3StageState.EMPTY


def test_r3_reserved_stage_supplies_only_the_existing_r2_pack_read_ownership_predicate():
    reference = _reference()
    generation, owner = _stage_and_group(reference)
    arbitration = RouteAArbitrationReference()
    candidate = ReadCandidate(
        "pack-read",
        TransactionIdentity(2, 0),
        "pack_read",
        "pending",
        "p3:0",
        "pending:0",
        8,
        0,
    )
    arbitration.register_read(candidate)
    arbitration.mark_read_common_ready("pack-read", fifo_ready=True, ownership_ready=True, credit_ready=True, destination_ready=True)
    arbitration.mark_pending_authoritative("pack-read")
    assert not arbitration.read_is_eligible("pack-read")
    assert reference.p3_read_ready_owned(layer=0, generation=generation, owner=owner)
    arbitration.mark_p3_stage_ready("pack-read")
    assert arbitration.read_is_eligible("pack-read")

    wrapper = CoreMemoryWrapperReference()
    wrapper.acknowledge_mem_init_done(adapter_epoch=0)
    assert arbitration.grant_next_read(wrapper) == "pack-read"
    assert reference.begin_p3_read(layer=0, generation=generation, owner=owner)


def test_r1_durability_m2_commit_and_lifecycle_publication_are_one_ordered_handoff():
    reference = _reference()
    generation, owner = _stage_and_group(reference)
    _stage_m2_members(reference, group_id="g0", owner=owner)
    _complete_p3_stage(reference, layer=0, generation=generation, owner=owner)
    assert reference.begin_p3_write(layer=0, generation=generation, owner=owner)

    wrapper = CoreMemoryWrapperReference()
    wrapper.acknowledge_mem_init_done(adapter_epoch=0)
    identity = TransactionIdentity(0, 0)
    wrapper.accept_write(CoreWriteRequest(identity, "packed:0", 8))
    for fragment_index in range(8):
        wrapper.accept_write_data(CoreWriteData(identity, fragment_index, fragment_index == 7, bytes(CORE_MEM_FRAGMENT_BYTES)))
    assert wrapper.receive_write_commit(identity, status=MemoryStatus.OK, adapter_epoch=0) == "payload_durable_only"
    reference.record_p3_write_terminal(layer=0, generation=generation, owner=owner, status=MemoryStatus.OK, r1_payload_durable=wrapper.durable(identity))
    assert reference.p3_stage_state(layer=0, generation=generation) is P3StageState.DURABLE
    reference.mark_payload_durable("g0", stage_generation=generation, r1_payload_durable=wrapper.durable(identity))

    lifecycle = RouteAArchitectureReference()
    lifecycle.seed_pending("t0")
    lifecycle.open_packed_write(1, "t0")
    lifecycle.page_write_commit(1, "t0")
    lifecycle.begin_metadata_group("g0", ("t0",))
    lifecycle.stage_metadata_member("g0", "t0")
    reference.set_channel_ready(m2_commit=False)
    assert not reference.atomic_publish("g0", publication_action=lambda: lifecycle.metadata_atomic_publish("g0"))
    assert lifecycle.authority("t0") == "pending"
    reference.set_channel_ready(m2_commit=True)
    assert reference.atomic_publish("g0", publication_action=lambda: lifecycle.metadata_atomic_publish("g0"))
    assert lifecycle.authority("t0") == "packed"
    assert reference.metadata_is_published("g0")
    assert reference.p3_slot_state(layer=0) is P3StageState.EMPTY
    with pytest.raises(M2P3Violation, match="stale"):
        reference.p3_stage_state(layer=0, generation=generation)


def test_fault_and_reset_are_fail_closed_and_cannot_make_p3_authoritative_or_reuse_stale_generation():
    reference = _reference()
    generation, owner = _stage_and_group(reference)
    _stage_m2_members(reference, group_id="g0", owner=owner)
    reference.destructive_reset()
    assert not reference.initialized
    with pytest.raises(M2P3Violation, match="before init_done"):
        reference.claim_p3_stage(layer=0, kv_head=0, owner=owner, page_ref="page:new", valid_records=1)
    reference.acknowledge_init_done(core_mem_initialized=True)
    with pytest.raises(M2P3Violation, match="stale"):
        reference.p3_stage_state(layer=0, generation=generation)
    fresh_generation = reference.claim_p3_stage(layer=0, kv_head=0, owner=owner, page_ref="page:new", valid_records=1)
    assert fresh_generation != generation
    assert not reference.p3_stage_is_authoritative(layer=0, generation=fresh_generation)


def test_m2_member_fault_prevents_publication_and_has_no_fallback_path():
    reference = _reference()
    generation, owner = _stage_and_group(reference)
    request = M2Operation("head", 0, M2Object.HEAD_CONTROL, M2Access.RMW, "head:0", owner, "g0", M2Member.HEAD_CONTROL_RMW)
    assert reference.submit_m2_op(request)
    reference.receive_m2_op_rsp("head", status=MemoryStatus.FAULT)
    assert reference.m2_group_state("g0") is M2GroupState.FAULTED
    with pytest.raises(M2P3Violation, match="publication requires"):
        reference.atomic_publish("g0", publication_action=lambda: None)
    assert reference.p3_stage_state(layer=0, generation=generation) is P3StageState.RESERVED
    reference.abort_faulted_group("g0")
    assert reference.p3_slot_state(layer=0) is P3StageState.EMPTY
