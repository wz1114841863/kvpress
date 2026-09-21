from tools.analyze_kvzap_route_a4670_pending_ownership_reference import PendingOwnershipState


def _dequeue_sources(state: PendingOwnershipState, count: int) -> list[str]:
    return [str(chunk["source"]) for chunk in state.dequeue(count=count)]


def test_a4670_oldest_shared_entry_wins_over_newer_private_entry_without_migration():
    state = PendingOwnershipState(organization="hierarchical", private_quota=2)
    state.enqueue(count=5, birth_opportunity=1)  # private [0,1], shared [2,3,4]
    assert _dequeue_sources(state, 3) == ["private", "shared"]
    state.enqueue(count=2, birth_opportunity=2)  # newly freed private capacity
    assert _dequeue_sources(state, 1) == ["shared"]  # older shared item precedes newer private items
    assert state.source_age_inversion_count == 0
    assert state.migration_event_count == 0


def test_a4670_q0_hierarchical_is_shared_and_large_quota_is_head_local():
    shared = PendingOwnershipState(organization="layer_shared", private_quota=None)
    q0 = PendingOwnershipState(organization="hierarchical", private_quota=0)
    head_local = PendingOwnershipState(organization="head_local", private_quota=None)
    large_q = PendingOwnershipState(organization="hierarchical", private_quota=16)
    for state in (shared, q0, head_local, large_q):
        state.enqueue(count=5, birth_opportunity=1)
        state.enqueue(count=2, birth_opportunity=2)
    assert _dequeue_sources(shared, 6) == _dequeue_sources(q0, 6)
    assert _dequeue_sources(head_local, 6) == _dequeue_sources(large_q, 6)


def test_a4670_invalid_grant_cannot_change_pending_semantics():
    state = PendingOwnershipState(organization="layer_shared", private_quota=None)
    state.enqueue(count=3, birth_opportunity=1)
    try:
        state.dequeue(count=4)
    except ValueError as error:
        assert "invalid dequeue grant" in str(error)
    else:
        raise AssertionError("overservice must be rejected")
