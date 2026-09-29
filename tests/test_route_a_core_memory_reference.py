import json
from pathlib import Path

import pytest

from kvpress.route_a_architecture_reference import RouteAArchitectureReference
from kvpress.route_a_core_memory_reference import (
    CORE_MEM_FRAGMENT_BYTES,
    CoreMemoryWrapperReference,
    CoreReadRequest,
    CoreReadResponse,
    CoreWriteData,
    CoreWriteRequest,
    MemoryBackpressure,
    MemoryProtocolViolation,
    MemoryStatus,
    TransactionIdentity,
)


PROFILE = Path("analysis/architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json")


def _data(value: int = 0) -> bytes:
    return bytes([value]) * CORE_MEM_FRAGMENT_BYTES


def _ready_wrapper() -> CoreMemoryWrapperReference:
    wrapper = CoreMemoryWrapperReference()
    wrapper.acknowledge_mem_init_done(adapter_epoch=0)
    return wrapper


def test_r1_anchor_profile_maps_to_single_core_clock_and_finite_core_memory_bounds():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    envelope = profile["deployment_envelope"]
    endpoint = profile["direct_pending_endpoint"]
    wrapper = CoreMemoryWrapperReference(
        max_live_reads=envelope["max_live_read_requests"],
        max_live_writes=envelope["max_live_write_requests"],
        fragment_bytes=endpoint["fragment_bytes"],
        rid_width=profile["transaction_identity"]["rid_width"],
        incarnation_width=profile["transaction_identity"]["incarnation_width"],
    )
    assert wrapper.fragment_bytes == 64
    assert not wrapper.mem_init_done
    with pytest.raises(MemoryBackpressure, match="ready is low"):
        wrapper.accept_read(CoreReadRequest(TransactionIdentity(0, 0), "s2_fill", "S2-A", "page:0", 1))
    wrapper.acknowledge_mem_init_done(adapter_epoch=0)
    for request_id in range(4):
        wrapper.accept_read(CoreReadRequest(TransactionIdentity(request_id, 0), "s2_fill", f"S2-{request_id}", f"page:{request_id}", 1))
    with pytest.raises(MemoryBackpressure, match="ready is low"):
        wrapper.accept_read(CoreReadRequest(TransactionIdentity(4, 0), "pack_read", "P3", "pending:0", 1))


def test_same_transaction_fragments_are_ordered_while_transactions_may_return_reordered():
    wrapper = _ready_wrapper()
    first = TransactionIdentity(0, 0)
    second = TransactionIdentity(1, 0)
    wrapper.accept_read(CoreReadRequest(first, "s2_fill", "S2-A", "page:0", 2))
    wrapper.accept_read(CoreReadRequest(second, "direct_pending", "endpoint", "pending:0", 1))

    assert wrapper.receive_read_response(CoreReadResponse(second, 0, True, MemoryStatus.OK, _data(2)), adapter_epoch=0) == "success"
    assert wrapper.receive_read_response(CoreReadResponse(first, 0, False, MemoryStatus.OK, _data(0)), adapter_epoch=0) == "partial"
    assert wrapper.receive_read_response(CoreReadResponse(first, 1, True, MemoryStatus.OK, _data(1)), adapter_epoch=0) == "success"


def test_fragment_width_last_and_order_are_checked_without_a_cycle_or_hbm_model():
    wrapper = _ready_wrapper()
    identity = TransactionIdentity(0, 0)
    wrapper.accept_read(CoreReadRequest(identity, "pack_read", "P3", "pending:0", 2))
    with pytest.raises(MemoryProtocolViolation, match="ordered"):
        wrapper.receive_read_response(CoreReadResponse(identity, 1, True, MemoryStatus.OK, _data()), adapter_epoch=0)
    with pytest.raises(MemoryProtocolViolation, match="width"):
        wrapper.receive_read_response(CoreReadResponse(identity, 0, False, MemoryStatus.OK, b"short"), adapter_epoch=0)
    with pytest.raises(MemoryProtocolViolation, match="last"):
        wrapper.receive_read_response(CoreReadResponse(identity, 0, True, MemoryStatus.OK, _data()), adapter_epoch=0)


def test_write_commit_is_payload_durable_only_and_cannot_transfer_route_a_authority():
    wrapper = _ready_wrapper()
    identity = TransactionIdentity(2, 0)
    wrapper.accept_write(CoreWriteRequest(identity, "packed:0", 2))
    with pytest.raises(MemoryProtocolViolation, match="complete ordered"):
        wrapper.receive_write_commit(identity, status=MemoryStatus.OK, adapter_epoch=0)
    wrapper.accept_write_data(CoreWriteData(identity, 0, False, _data(0)))
    wrapper.accept_write_data(CoreWriteData(identity, 1, True, _data(1)))
    assert wrapper.receive_write_commit(identity, status=MemoryStatus.OK, adapter_epoch=0) == "payload_durable_only"
    assert wrapper.durable(identity)

    lifecycle = RouteAArchitectureReference()
    lifecycle.seed_pending("t0")
    lifecycle.open_packed_write(2, "t0")
    lifecycle.page_write_commit(2, "t0")
    assert lifecycle.authority("t0") == "pending"


def test_fault_is_terminal_and_late_response_cannot_reopen_a_transaction():
    wrapper = _ready_wrapper()
    identity = TransactionIdentity(0, 0)
    wrapper.accept_read(CoreReadRequest(identity, "direct_pending", "endpoint", "pending:0", 1))
    assert wrapper.receive_read_response(CoreReadResponse(identity, 0, True, MemoryStatus.FAULT, None), adapter_epoch=0) == "fault"
    assert wrapper.receive_read_response(CoreReadResponse(identity, 0, True, MemoryStatus.OK, _data()), adapter_epoch=0) == "stale_rejected"


def test_identity_epoch_rules_reject_live_rid_alias_and_exact_reuse_but_allow_new_incarnation_after_terminal():
    wrapper = _ready_wrapper()
    old = TransactionIdentity(0, 0)
    wrapper.accept_read(CoreReadRequest(old, "s2_fill", "S2-A", "page:0", 1))
    with pytest.raises(MemoryProtocolViolation, match="live request_id"):
        wrapper.accept_read(CoreReadRequest(TransactionIdentity(0, 1), "s2_fill", "S2-B", "page:1", 1))
    assert wrapper.receive_read_response(CoreReadResponse(old, 0, True, MemoryStatus.OK, _data()), adapter_epoch=0) == "success"
    with pytest.raises(MemoryProtocolViolation, match="may not be reused"):
        wrapper.accept_read(CoreReadRequest(old, "s2_fill", "S2-A", "page:0", 1))
    wrapper.accept_read(CoreReadRequest(TransactionIdentity(0, 1), "s2_fill", "S2-B", "page:1", 1))
    with pytest.raises(MemoryProtocolViolation, match="finite namespace"):
        wrapper.accept_read(CoreReadRequest(TransactionIdentity(8, 0), "pack_read", "P3", "pending:0", 1))


def test_destructive_reset_requires_adapter_epoch_handoff_and_rejects_pre_reset_responses():
    wrapper = _ready_wrapper()
    identity = TransactionIdentity(0, 0)
    wrapper.accept_read(CoreReadRequest(identity, "s2_fill", "S2-A", "page:0", 1))
    assert wrapper.destructive_reset() == 1
    assert not wrapper.mem_init_done
    assert wrapper.receive_read_response(CoreReadResponse(identity, 0, True, MemoryStatus.OK, _data()), adapter_epoch=0) == "pre_reset_rejected"
    with pytest.raises(MemoryBackpressure, match="ready is low"):
        wrapper.accept_read(CoreReadRequest(identity, "s2_fill", "S2-A", "page:0", 1))
    with pytest.raises(MemoryProtocolViolation, match="stale"):
        wrapper.acknowledge_mem_init_done(adapter_epoch=0)
    wrapper.acknowledge_mem_init_done(adapter_epoch=1)
    wrapper.accept_read(CoreReadRequest(identity, "s2_fill", "S2-A", "page:0", 1))
    assert wrapper.receive_read_response(CoreReadResponse(identity, 0, True, MemoryStatus.OK, _data()), adapter_epoch=0) == "pre_reset_rejected"
    assert wrapper.receive_read_response(CoreReadResponse(identity, 0, True, MemoryStatus.OK, _data()), adapter_epoch=1) == "success"
