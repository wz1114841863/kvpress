import pytest

from kvpress.route_a_arbitration_reference import (
    ArbitrationViolation,
    ReadCandidate,
    RouteAArbitrationReference,
    WriteCandidate,
)
from kvpress.route_a_core_memory_reference import (
    CORE_MEM_FRAGMENT_BYTES,
    CoreMemoryWrapperReference,
    CoreWriteData,
    MemoryStatus,
    TransactionIdentity,
)


def _wrapper(*, initialized: bool = True) -> CoreMemoryWrapperReference:
    wrapper = CoreMemoryWrapperReference()
    if initialized:
        wrapper.acknowledge_mem_init_done(adapter_epoch=0)
    return wrapper


def _read(candidate_id: str, request_id: int, read_kind: str, source_kind: str, ordinal: int) -> ReadCandidate:
    return ReadCandidate(
        candidate_id,
        TransactionIdentity(request_id, 0),
        read_kind,  # type: ignore[arg-type]
        source_kind,  # type: ignore[arg-type]
        f"dst:{candidate_id}",
        f"addr:{candidate_id}",
        1,
        ordinal,
    )


def _common_ready(reference: RouteAArbitrationReference, candidate_id: str) -> None:
    reference.mark_read_common_ready(
        candidate_id,
        fifo_ready=True,
        ownership_ready=True,
        credit_ready=True,
        destination_ready=True,
    )


def test_packed_pending_and_packer_reads_cannot_issue_before_their_distinct_dependency_guards():
    reference = RouteAArbitrationReference()
    reference.register_read(_read("packed", 0, "s2_fill", "packed", 0))
    reference.register_read(_read("pending", 1, "direct_pending", "pending", 1))
    reference.register_read(_read("packer", 2, "pack_read", "pending", 2))
    for candidate_id in ("packed", "pending", "packer"):
        _common_ready(reference, candidate_id)

    assert not reference.read_is_eligible("packed")
    assert not reference.read_is_eligible("pending")
    assert not reference.read_is_eligible("packer")
    reference.mark_packed_metadata_published("packed")
    reference.mark_pending_authoritative("pending")
    reference.mark_pending_authoritative("packer")
    assert reference.read_is_eligible("packed")
    assert reference.read_is_eligible("pending")
    assert not reference.read_is_eligible("packer")
    reference.mark_p3_stage_ready("packer")
    assert reference.read_is_eligible("packer")


def test_read_arbiter_rotates_across_eligible_classes_and_preserves_intra_class_arrival_order():
    reference = RouteAArbitrationReference()
    reference.register_read(_read("s2_late", 0, "s2_fill", "full_kv", 10))
    reference.register_read(_read("s2_early", 1, "s2_fill", "full_kv", 2))
    reference.register_read(_read("pending", 2, "direct_pending", "pending", 3))
    reference.register_read(_read("packer", 3, "pack_read", "pending", 4))
    for candidate_id in ("s2_late", "s2_early", "pending", "packer"):
        _common_ready(reference, candidate_id)
    reference.mark_pending_authoritative("pending")
    reference.mark_pending_authoritative("packer")
    reference.mark_p3_stage_ready("packer")

    wrapper = _wrapper()
    assert reference.grant_next_read(wrapper) == "s2_early"
    assert reference.grant_next_read(wrapper) == "pending"
    assert reference.grant_next_read(wrapper) == "packer"
    assert reference.grant_next_read(wrapper) == "s2_late"
    assert reference.read_cursor_class() == "direct_pending"


def test_core_ready_low_delays_without_advancing_cursor_or_issuing_candidate():
    reference = RouteAArbitrationReference()
    reference.register_read(_read("s2", 0, "s2_fill", "full_kv", 0))
    _common_ready(reference, "s2")
    wrapper = _wrapper(initialized=False)
    assert reference.grant_next_read(wrapper) is None
    assert reference.read_cursor_class() == "s2_fill"
    assert reference.read_is_eligible("s2")
    wrapper.acknowledge_mem_init_done(adapter_epoch=0)
    assert reference.grant_next_read(wrapper) == "s2"


def test_write_requires_all_guards_and_metadata_publication_waits_for_successful_write_commit():
    reference = RouteAArbitrationReference()
    candidate = WriteCandidate("write", TransactionIdentity(4, 0), "packed:0", 2, "group0")
    reference.register_write(candidate)
    reference.mark_write_ready("write", fifo_ready=True, ownership_ready=True, credit_ready=True, page_allocated=True)
    wrapper = _wrapper()
    assert not reference.grant_write("write", wrapper)
    reference.mark_write_ready("write", p3_stage_complete=True, p3_stage_owned=True)
    assert reference.grant_write("write", wrapper)
    assert not reference.metadata_publication_eligible("group0")
    with pytest.raises(ArbitrationViolation, match="R1 durable"):
        reference.record_write_commit("write", wrapper=wrapper, status=MemoryStatus.OK)
    wrapper.accept_write_data(CoreWriteData(candidate.identity, 0, False, bytes(CORE_MEM_FRAGMENT_BYTES)))
    wrapper.accept_write_data(CoreWriteData(candidate.identity, 1, True, bytes(CORE_MEM_FRAGMENT_BYTES)))
    assert wrapper.receive_write_commit(candidate.identity, status=MemoryStatus.OK, adapter_epoch=0) == "payload_durable_only"
    reference.record_write_commit("write", wrapper=wrapper, status=MemoryStatus.OK)
    assert reference.metadata_publication_eligible("group0")


def test_faulted_write_never_enables_metadata_publication_and_invalid_source_ownership_is_rejected():
    reference = RouteAArbitrationReference()
    with pytest.raises(ArbitrationViolation, match="source kind"):
        reference.register_read(_read("bad", 0, "direct_pending", "packed", 0))

    candidate = WriteCandidate("write", TransactionIdentity(0, 0), "packed:0", 1, "group0")
    reference.register_write(candidate)
    reference.mark_write_ready(
        "write",
        fifo_ready=True,
        ownership_ready=True,
        credit_ready=True,
        page_allocated=True,
        p3_stage_complete=True,
        p3_stage_owned=True,
    )
    wrapper = _wrapper()
    assert reference.grant_write("write", wrapper)
    assert wrapper.receive_write_commit(candidate.identity, status=MemoryStatus.FAULT, adapter_epoch=0) == "fault"
    reference.record_write_commit("write", wrapper=wrapper, status=MemoryStatus.FAULT)
    assert not reference.metadata_publication_eligible("group0")
