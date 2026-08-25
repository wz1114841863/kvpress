from tools.simulate_kvzap_route_a3_hybrid_activation import hybrid_attention, post_call_states


def test_post_call_state_is_visible_only_to_next_model_call():
    progress = [
        {"model_call": "0", "layer": "0", "kv_head": "0", "cold_logical_tokens_after": "2", "cold_allocated_slots_after": "4", "cold_page_count_after": "1", "pending_tokens_after": "3"},
        {"model_call": "1", "layer": "0", "kv_head": "0", "cold_logical_tokens_after": "5", "cold_allocated_slots_after": "8", "cold_page_count_after": "2", "pending_tokens_after": "0"},
    ]
    states = post_call_states(progress)
    assert states[0] == {}
    assert states[1][(0, 0)] == {"packed_logical": 2, "packed_slots": 4, "packed_pages": 1, "pending": 3}


def test_hybrid_attention_accounts_pending_index_and_merge_per_head():
    rows = [{"layer": "0", "kv_head": "0", "cache_tokens_after": "10"}]
    state = {(0, 0): {"packed_logical": 2, "packed_slots": 4, "packed_pages": 1, "pending": 3}}
    result = hybrid_attention(rows, state, window=2, kv_bytes=16, page_tokens=4, bandwidth=16, throughput=64, ops_per_token=1, metadata_bytes=8, metadata_cycles=1, pending_position_bytes=8, merge_bytes=16, merge_cycles=2, pe_count=1, scheduler="static_head", head_dispatch_cycles=0)
    read, index, metadata, merge, pending, cycles, logical, slots, pages, merge_heads = result
    assert (read, index, metadata, merge, pending) == (144, 24, 8, 16, 3)
    assert (logical, slots, pages, merge_heads) == (2, 4, 1, 1)
    assert cycles > 0
