import torch

from kvpress.route_a_attention import _Record, RouteAPackedAttentionState, RouteAPolicy, dense_same_mask_attention, online_softmax_merge, policy_attention


def make_state(*, heads=1, window=2, page_tokens=2, budget=1):
    return RouteAPackedAttentionState(heads=heads, head_dim=2, window=window, page_tokens=page_tokens, admission_budget=budget)


def test_fast_path_preserves_mask_positions_hot_window_fifo_and_page_order():
    state = make_state(budget=1)
    keys = torch.arange(12, dtype=torch.float32).reshape(1, 6, 2)
    state.append(keys, keys + 100, torch.tensor([[True, False, True, True, False, True]]), start_position=0)
    sources = state.records(0)
    # One shared token of service is available for this append/model-call.
    assert [item.position for item in sources["packed"]] == [0]
    assert [item.position for item in sources["pending"]] == [2, 3]
    assert [item.position for item in sources["hot"]] == [4, 5]
    assert state.state_summary(0) == {"hot_tokens": 2, "pending_tokens": 2, "packed_tokens": 1, "packed_page_count": 1}
    state.assert_conservation()


def test_three_store_attention_matches_dense_same_mask_and_online_merge():
    state = make_state(budget=1)
    keys = torch.tensor([[[1., 0.], [0., 1.], [2., 0.], [0., 2.], [3., 0.], [0., 3.]]])
    state.append(keys, keys + 10, torch.tensor([[True, True, True, True, True, True]]), start_position=0)
    query = torch.tensor([0.3, -0.2])
    expected = dense_same_mask_attention(query, state.same_mask_records(0))
    torch.testing.assert_close(state.attention(query, head=0), expected, rtol=1e-6, atol=1e-6)
    # Fast-path selection has no Full-KV argument and therefore cannot silently
    # substitute dense cold K/V for the three Route-A stores.
    torch.testing.assert_close(policy_attention(RouteAPolicy.ROUTE_A_FAST_PATH, query, state=state, head=0), expected)


def test_empty_pending_empty_cold_tail_cross_page_and_different_head_lengths():
    state = make_state(heads=2, window=2, page_tokens=2, budget=8)
    keys = torch.arange(24, dtype=torch.float32).reshape(2, 6, 2)
    state.append(keys, keys, torch.tensor([[False, False, False, False, True, True], [True, True, True, True, True, True]]), start_position=0)
    assert state.state_summary(0) == {"hot_tokens": 2, "pending_tokens": 0, "packed_tokens": 0, "packed_page_count": 0}
    assert state.state_summary(1) == {"hot_tokens": 2, "pending_tokens": 0, "packed_tokens": 4, "packed_page_count": 2}
    for head in range(2):
        query = torch.tensor([1.0, -1.0])
        torch.testing.assert_close(state.attention(query, head=head), dense_same_mask_attention(query, state.same_mask_records(head)))


def test_online_merge_handles_empty_sources_and_matches_concatenation():
    zero = torch.zeros(2)
    assert torch.equal(online_softmax_merge([(torch.tensor(float("-inf")), torch.tensor(0.), zero)]), zero)


def test_full_kv_bypass_is_explicit_and_does_not_construct_route_a_state():
    assert RouteAPolicy.FULL_KV_BYPASS.value == "full_kv_bypass"
    state = make_state()
    query = torch.tensor([1.0, 0.0])
    full = [_Record(0, torch.tensor([1.0, 0.0]), torch.tensor([7.0, 8.0]))]
    torch.testing.assert_close(policy_attention(RouteAPolicy.FULL_KV_BYPASS, query, full_kv_records=full), torch.tensor([7.0, 8.0]))
    assert state.state_summary(0) == {"hot_tokens": 0, "pending_tokens": 0, "packed_tokens": 0, "packed_page_count": 0}


def test_rejects_noncontiguous_positions_and_wrong_mask_shape():
    state = make_state()
    keys = torch.zeros(1, 2, 2)
    try:
        state.append(keys, keys, torch.ones(1, 2, dtype=torch.bool), start_position=1)
    except AssertionError:
        pass
    else:
        raise AssertionError("non-contiguous append was accepted")
    try:
        state.append(keys, keys, torch.ones(2, 1, dtype=torch.bool), start_position=0)
    except ValueError:
        pass
    else:
        raise AssertionError("wrong mask shape was accepted")


def test_mask_decision_stays_with_hot_token_across_append_calls():
    state = make_state(window=2, budget=8)
    keys = torch.arange(8, dtype=torch.float32).reshape(1, 4, 2)
    state.append(keys[:, :2], keys[:, :2], torch.tensor([[False, True]]), start_position=0)
    state.append(keys[:, 2:], keys[:, 2:], torch.tensor([[True, False]]), start_position=2)
    assert [item.position for item in state.records(0)["packed"]] == [1]
    assert [item.position for item in state.records(0)["hot"]] == [2, 3]
