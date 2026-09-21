from tools.analyze_kvzap_route_a4670_pending_ownership_reference import PendingOwnershipState
from tools.analyze_kvzap_route_a4681_representation_access_contract import (
    AccessStatistics,
    BirthOrderedAccessState,
    assert_access_contract_sufficient,
)


def _enqueue(reference, state, count, birth, phase="activation"):
    state.append_from_reference(events=reference.enqueue(count=count, birth_opportunity=birth), birth_opportunity=birth, phase=phase)
    assert_access_contract_sufficient(reference=reference, state=state)


def test_a4681_old_shared_front_is_selected_before_new_private_front():
    reference = PendingOwnershipState(organization="hierarchical", private_quota=2)
    state = BirthOrderedAccessState(statistics=AccessStatistics(), layer=0)
    _enqueue(reference, state, 5, 1)  # private [0,1], shared [2,3,4]
    expected = [(str(item["source"]), int(item["count"])) for item in reference.dequeue(count=3)]
    assert state.dequeue(count=3, phase="steady_state_dequeue", opportunity=1) == expected
    _enqueue(reference, state, 2, 2, phase="steady_state_append")
    expected = [(str(item["source"]), int(item["count"])) for item in reference.dequeue(count=1)]
    assert state.dequeue(count=1, phase="steady_state_dequeue", opportunity=2) == expected == [("shared", 1)]
    assert_access_contract_sufficient(reference=reference, state=state)


def test_a4681_partial_dequeue_keeps_span_and_full_dequeue_releases_it():
    reference = PendingOwnershipState(organization="layer_shared", private_quota=None)
    statistics = AccessStatistics()
    state = BirthOrderedAccessState(statistics=statistics, layer=0)
    _enqueue(reference, state, 5, 0)
    reference.dequeue(count=2)
    assert state.dequeue(count=2, phase="steady_state_dequeue", opportunity=1) == [("shared", 2)]
    assert state.created_span_count == 1 and state.released_span_count == 0
    reference.dequeue(count=3)
    assert state.dequeue(count=3, phase="steady_state_dequeue", opportunity=2) == [("shared", 3)]
    assert state.released_span_count == 1
    summary = statistics.phase_summary("steady_state_dequeue")["logical_primitive_counts"]
    assert summary["span_partial_dequeue"] == 2
    assert summary["span_release"] == 1


def test_a4681_tail_extension_rejects_birth_boundary_and_accepts_legal_tail():
    state = BirthOrderedAccessState(statistics=AccessStatistics(), layer=0)
    state.append_from_reference(events=[{"source": "private", "count": 2}], birth_opportunity=1, phase="activation")
    state.extend_tail(source="private", birth_opportunity=1, sequence_start=2, count=3, phase="activation")
    assert state.sources["private"][0].count == 5
    try:
        state.extend_tail(source="private", birth_opportunity=2, sequence_start=5, count=1, phase="steady_state_append")
    except ValueError as error:
        assert "cross birth/order boundary" in str(error)
    else:
        raise AssertionError("cross-birth tail extension must be rejected")


def test_a4681_payload_reference_lifecycle_is_not_payload_movement():
    reference = PendingOwnershipState(organization="head_local", private_quota=None)
    statistics = AccessStatistics()
    state = BirthOrderedAccessState(statistics=statistics, layer=0)
    _enqueue(reference, state, 1, 0)
    reference.dequeue(count=1)
    state.dequeue(count=1, phase="steady_state_dequeue", opportunity=1)
    assert "payload_reference_create" in statistics.phase_summary("activation")["logical_primitive_counts"]
    assert "payload_reference_release" in statistics.phase_summary("steady_state_dequeue")["logical_primitive_counts"]
    assert all("kv_" not in name and "byte" not in name for phase in statistics.by_phase.values() for name in phase)
