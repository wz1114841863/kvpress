import random

import pytest

from kvpress.route_a_architecture_reference import (
    BackpressureStall,
    ContractViolation,
    RouteAArchitectureReference,
    SlotState,
    SourcePartial,
    merge_source_partials,
)


@pytest.mark.parametrize(
    "sources",
    [
        {"hot": SourcePartial(0.0, 1.0, 2.0)},
        {"pending": SourcePartial(0.0, 1.0, 2.0)},
        {"packed": SourcePartial(0.0, 1.0, 2.0)},
        {"hot": SourcePartial(0.0, 1.0, 2.0), "pending": SourcePartial(1.0, 1.0, 3.0)},
        {"hot": SourcePartial(0.0, 1.0, 2.0), "packed": SourcePartial(1.0, 1.0, 3.0)},
        {"pending": SourcePartial(0.0, 1.0, 2.0), "packed": SourcePartial(1.0, 1.0, 3.0)},
        {"hot": SourcePartial(0.0, 1.0, 2.0), "pending": SourcePartial(1.0, 1.0, 3.0), "packed": SourcePartial(-1.0, 1.0, 4.0)},
    ],
)
def test_canonical_merge_covers_all_nonempty_source_subsets(sources):
    merged = merge_source_partials(sources)
    assert merged.source_order == ("hot", "pending", "packed")
    assert merged.partial.l > 0.0
    assert merged.normalized() == pytest.approx(merged.partial.o / merged.partial.l)


def test_absent_source_identity_is_neutral_and_empty_logical_source_set_fails():
    pending = SourcePartial(2.0, 3.0, 9.0)
    merged = merge_source_partials({"hot": SourcePartial.absent_identity(), "pending": pending, "packed": None})
    assert merged.partial == pending
    with pytest.raises(ContractViolation, match="entirely empty"):
        merge_source_partials({"hot": None, "pending": None, "packed": None})
    with pytest.raises(ContractViolation, match="l > 0"):
        merge_source_partials({"hot": SourcePartial.absent_identity()}).normalized()


def test_write_commit_does_not_transfer_authority_before_atomic_metadata_publication():
    reference = RouteAArchitectureReference()
    reference.seed_pending("t0")
    reference.open_packed_write(1, "t0")
    reference.page_write_commit(1, "t0")
    assert reference.authority("t0") == "pending"
    reference.begin_metadata_group("g0", ("t0",))
    reference.stage_metadata_member("g0", "t0")
    reference.metadata_atomic_publish("g0")
    assert reference.visible_group("g0")
    assert reference.authority("t0") == "packed"


def test_write_commit_cannot_be_retargeted_to_another_pending_token():
    reference = RouteAArchitectureReference()
    reference.seed_pending("t0")
    reference.seed_pending("t1")
    reference.open_packed_write(1, "t0")
    with pytest.raises(ContractViolation, match="token differs"):
        reference.page_write_commit(1, "t1")
    reference.page_write_commit(1, "t0")


def test_partial_metadata_group_is_never_visible():
    reference = RouteAArchitectureReference()
    for request_id, token in enumerate(("t0", "t1"), start=10):
        reference.seed_pending(token)
        reference.open_packed_write(request_id, token)
        reference.page_write_commit(request_id, token)
    reference.begin_metadata_group("g0", ("t0", "t1"))
    reference.stage_metadata_member("g0", "t0")
    with pytest.raises(ContractViolation, match="partial metadata group"):
        reference.metadata_atomic_publish("g0")
    assert not reference.visible_group("g0")
    assert reference.authority("t0") == reference.authority("t1") == "pending"


def test_s2_ready_requires_complete_response_and_release_requires_four_consumers():
    reference = RouteAArchitectureReference()
    generation = reference.accept_s2_read(17, "S2-A", requires_sidecar=True)
    assert reference.receive_s2_response(17, generation, payload_last=True) == "partial"
    assert reference.slot_state("S2-A") is SlotState.FILLING
    assert reference.receive_s2_response(17, generation, sidecar_last=True) == "ready"
    reference.begin_s2_consume("S2-A")
    for consumer in range(3):
        reference.commit_s2_consumer("S2-A", consumer)
    with pytest.raises(ContractViolation, match="all GQA"):
        reference.release_s2("S2-A")
    reference.commit_s2_consumer("S2-A", 3)
    reference.release_s2("S2-A")
    assert reference.slot_state("S2-A") is SlotState.EMPTY


def test_late_response_after_slot_reuse_cannot_change_new_fill_or_ready_state():
    reference = RouteAArchitectureReference()
    old_generation = reference.accept_s2_read(17, "S2-A", requires_sidecar=False)
    assert reference.receive_s2_response(17, old_generation, payload_last=True) == "ready"
    reference.begin_s2_consume("S2-A")
    for consumer in range(4):
        reference.commit_s2_consumer("S2-A", consumer)
    reference.release_s2("S2-A")
    new_generation = reference.accept_s2_read(23, "S2-A", requires_sidecar=False)
    assert new_generation != old_generation
    assert reference.receive_s2_response(17, old_generation, payload_last=True) == "stale_rejected"
    assert reference.slot_state("S2-A") is SlotState.FILLING
    assert reference.receive_s2_response(23, new_generation, payload_last=True) == "ready"


def test_fault_is_one_terminal_outcome_and_late_faulted_response_is_stale():
    reference = RouteAArchitectureReference()
    generation = reference.accept_s2_read(17, "S2-A", requires_sidecar=False)
    assert reference.receive_s2_response(17, generation, fault=True) == "fault"
    assert reference.receive_s2_response(17, generation, payload_last=True) == "stale_rejected"
    with pytest.raises(ContractViolation, match="reallocated"):
        reference.accept_s2_read(17, "S2-A", requires_sidecar=False)


def test_request_id_cannot_be_reallocated_and_direct_pending_preserves_fifo_and_completion():
    reference = RouteAArchitectureReference()
    reference.seed_pending("t0")
    reference.seed_pending("t1")
    reference.open_direct_pending_source(31, ("t0", "t1"))
    with pytest.raises(ContractViolation, match="reallocated"):
        reference.open_direct_pending_source(31, ("t0", "t1"))
    with pytest.raises(ContractViolation, match="FIFO"):
        reference.receive_direct_pending_record(31, 1, "t1", last=True)
    reference.receive_direct_pending_record(31, 0, "t0", last=False)
    reference.receive_direct_pending_record(31, 1, "t1", last=True)
    for consumer in range(4):
        reference.commit_direct_pending_consumer(31, consumer)
    reference.close_direct_pending_source(31)
    assert reference.authority("t0") == reference.authority("t1") == "pending"


def test_hot_maturity_drop_and_admission_preserve_authoritative_residency():
    reference = RouteAArchitectureReference()
    reference.seed_hot("drop")
    reference.seed_hot("keep")
    assert reference.authority("drop") == "hot" and reference.authoritative_count("drop") == 1
    assert reference.mature_hot("drop", keep=False) == "drop"
    assert reference.disposition("drop") == "drop" and reference.authoritative_count("drop") == 0
    assert reference.mature_hot("keep", keep=True) == "pending"
    assert reference.authority("keep") == "pending" and reference.authoritative_count("keep") == 1
    reference.open_packed_write(41, "keep")
    reference.page_write_commit(41, "keep")
    assert reference.authority("keep") == "pending"
    reference.begin_metadata_group("keep-group", ("keep",))
    reference.stage_metadata_member("keep-group", "keep")
    reference.metadata_atomic_publish("keep-group")
    assert reference.authority("keep") == "packed" and reference.authoritative_count("keep") == 1
    with pytest.raises(ContractViolation, match="packed write requires pending"):
        reference.open_packed_write(42, "drop")


def _assert_stall_is_nonmutating(reference, event, operation):
    before = reference.snapshot()
    reference.set_stall(event, True)
    with pytest.raises(BackpressureStall):
        operation()
    assert reference.snapshot() == before
    reference.set_stall(event, False)


def test_semantic_stalls_and_logical_credits_delay_without_semantic_change():
    reference = RouteAArchitectureReference(logical_admission_credits=1)
    reference.seed_hot("t0")
    reference.seed_hot("t1")
    reference.set_mask_decision("t0", keep=True)
    reference.set_mask_decision("t1", keep=True)
    _assert_stall_is_nonmutating(reference, "credit_availability", lambda: reference.mature_hot("t0"))
    reference.mature_hot("t0")
    with pytest.raises(BackpressureStall, match="credit unavailable"):
        reference.mature_hot("t1")
    _assert_stall_is_nonmutating(reference, "request_accept", lambda: reference.open_packed_write(51, "t0"))
    reference.open_packed_write(51, "t0")
    reference.page_write_commit(51, "t0")
    reference.begin_metadata_group("g0", ("t0",))
    reference.stage_metadata_member("g0", "t0")
    _assert_stall_is_nonmutating(reference, "metadata_publication", lambda: reference.metadata_atomic_publish("g0"))
    _assert_stall_is_nonmutating(reference, "credit_release", lambda: reference.metadata_atomic_publish("g0"))
    reference.metadata_atomic_publish("g0")
    assert reference.credit_state() == (1, 0)
    assert reference.mature_hot("t1") == "pending"
    assert reference.authority("t0") == "packed"


def test_stalled_response_and_consumer_completion_preserve_fifo_ownership_and_no_fallback():
    reference = RouteAArchitectureReference()
    reference.seed_pending("t0")
    reference.seed_pending("t1")
    reference.open_direct_pending_source(61, ("t0", "t1"))
    _assert_stall_is_nonmutating(reference, "response_delivery", lambda: reference.receive_direct_pending_record(61, 0, "t0", last=False))
    assert reference.receive_direct_pending_record(61, 0, "t0", last=False) == "delivered"
    assert reference.receive_direct_pending_record(61, 1, "t1", last=True) == "delivered"
    _assert_stall_is_nonmutating(reference, "consumer_completion", lambda: reference.commit_direct_pending_consumer(61, 0))
    for consumer in range(4):
        reference.commit_direct_pending_consumer(61, consumer)
    _assert_stall_is_nonmutating(reference, "credit_release", lambda: reference.close_direct_pending_source(61))
    reference.close_direct_pending_source(61)
    assert reference.snapshot()["full_kv_substitution_count"] == 0
    assert reference.authority("t0") == reference.authority("t1") == "pending"


def test_epoch_reuse_rejects_old_s2_and_direct_pending_incarnations_after_fault():
    reference = RouteAArchitectureReference(request_id_profile="epoch_reuse")
    first_generation = reference.accept_s2_read(7, "S2-A", requires_sidecar=False, epoch=0)
    with pytest.raises(ContractViolation, match="live request ID"):
        reference.accept_s2_read(7, "S2-B", requires_sidecar=False, epoch=1)
    assert reference.receive_s2_response(7, first_generation, epoch=0, fault=True) == "fault"
    second_generation = reference.accept_s2_read(7, "S2-A", requires_sidecar=False, epoch=1)
    assert reference.receive_s2_response(7, first_generation, epoch=0, payload_last=True) == "stale_rejected"
    assert reference.slot_state("S2-A") is SlotState.FILLING
    assert reference.receive_s2_response(7, second_generation, epoch=1, payload_last=True) == "ready"

    reference.seed_pending("t0")
    reference.open_direct_pending_source(9, ("t0",), epoch=0)
    reference.receive_direct_pending_record(9, 0, "t0", last=True, epoch=0)
    for consumer in range(4):
        reference.commit_direct_pending_consumer(9, consumer, epoch=0)
    reference.close_direct_pending_source(9, epoch=0)
    reference.open_direct_pending_source(9, ("t0",), epoch=1)
    before = reference.snapshot()
    assert reference.receive_direct_pending_record(9, 0, "t0", last=True, epoch=0) == "stale_rejected"
    assert reference.snapshot() == before


def test_fixed_seed_legal_stall_interleavings_are_lossless():
    rng = random.Random(20260928)
    reference = RouteAArchitectureReference(logical_admission_credits=1)

    def maybe_stall(event, operation):
        if rng.choice((False, True)):
            _assert_stall_is_nonmutating(reference, event, operation)
        operation()

    reference.seed_hot("t0")
    maybe_stall("credit_availability", lambda: reference.mature_hot("t0", keep=True))
    maybe_stall("request_accept", lambda: reference.open_packed_write(71, "t0"))
    reference.page_write_commit(71, "t0")
    reference.begin_metadata_group("g0", ("t0",))
    reference.stage_metadata_member("g0", "t0")
    maybe_stall("metadata_publication", lambda: reference.metadata_atomic_publish("g0"))
    if reference.authority("t0") == "pending":
        maybe_stall("credit_release", lambda: reference.metadata_atomic_publish("g0"))
    assert reference.authority("t0") == "packed"
    assert reference.authoritative_count("t0") == 1
    assert reference.credit_state() == (1, 0)
    assert reference.snapshot()["full_kv_substitution_count"] == 0
