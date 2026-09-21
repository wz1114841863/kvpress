from tools.analyze_kvzap_route_a4670_pending_ownership_reference import PendingOwnershipState, simulate_ownership


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


def test_a4670_activation_enqueue_is_separate_from_append_opportunity_inventory():
    result = simulate_ownership(
        inventory={(0, 0): {"pending": 3, "packed": 0, "hot": 0}},
        arrivals={(0, 0): [0]},
        fixed_schedule=[{(0, 0): (3, 3, 0)}],
        organization="head_local",
        private_quota=None,
    )
    activation = result["activation_logical_operation_and_concurrency_summary"][0]
    append = result["per_layer_append_opportunity_logical_operation_and_concurrency_summary"][0]
    assert activation["private_enqueue_token_units"] == 3
    assert activation["active_spans_after_activation"] == 1
    assert append["private_dequeue_token_units"] == 3
    assert append.get("private_enqueue_token_units", 0) == 0
