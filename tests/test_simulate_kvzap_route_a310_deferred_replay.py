from collections import deque

from tools.simulate_kvzap_route_a310_deferred_replay import append_pages, replay_variant, service_oldest_first


def test_service_oldest_first_interleaves_heads_by_exact_position():
    queues = {0: deque([2, 5]), 1: deque([1, 4])}
    served = service_oldest_first(queues, budget=3)
    assert served == {1: [1, 4], 0: [2]}
    assert list(queues[0]) == [5]
    assert list(queues[1]) == []


def test_append_pages_models_full_and_tail_page_without_overwriting_existing_page():
    assert append_pages(prior_tokens=0, prior_slots=0, prior_pages=0, count=4, page_tokens=4) == (4, 4, 1, 1)
    assert append_pages(prior_tokens=4, prior_slots=4, prior_pages=1, count=1, page_tokens=4) == (5, 8, 2, 1)
    assert append_pages(prior_tokens=5, prior_slots=8, prior_pages=2, count=0, page_tokens=4) == (5, 8, 2, 0)


def test_deferred_replay_keeps_predecode_decisions_pending_and_disables_service_during_fallback():
    lifecycle = [
        {"model_call": "0", "phase": "context_prefill", "layer": "0", "kv_head": "0", "cache_tokens_after": "3"},
        {"model_call": "0", "phase": "context_prefill", "layer": "0", "kv_head": "1", "cache_tokens_after": "3"},
        {"model_call": "1", "phase": "decode", "layer": "0", "kv_head": "0", "cache_tokens_after": "4"},
        {"model_call": "1", "phase": "decode", "layer": "0", "kv_head": "1", "cache_tokens_after": "4"},
    ]
    positions = {0: {(0, 0): [0], (0, 1): [1]}, 1: {(0, 0): [2]}}
    heads, layers, summary = replay_variant(lifecycle=lifecycle, positions=positions, request_id="unit", kv_bytes=16, page_tokens=2, deferred_steps=1, budget=1)
    assert summary["packed_tokens"] == 0
    assert summary["pending_tokens_at_end"] == 3
    assert summary["position_conservation_ok"] is True
    assert layers[0]["fallback_full_kv"] is True
    assert sum(row["pending_tokens_after"] for row in heads) == 3
