from tools.analyze_kvzap_route_a461_activation_burst_envelope import integer_summary, validate_and_summarize_trace


def test_a461_uses_trace_visible_nearest_rank_integer_summaries():
    assert integer_summary([1, 2, 3, 100]) == {"count": 4, "sum": 106, "min": 1, "p50": 2, "p95": 3, "p99": 3, "max": 100}


def test_a461_checks_per_append_pending_and_packed_conservation():
    head = {"kv_head": 0, "matured_kept_tokens": 2, "matured_dropped_tokens": 1, "admitted_tokens": 3, "pending_tokens_before_maturity": 1, "pending_tokens_after_maturity": 3, "pending_tokens_after_service": 0, "packed_tokens_before": 7, "packed_tokens_after_service": 10, "packed_page_count_after_service": 1}
    events = [{"layer": 0, "phase": "decode", "input_token_count": 1, "timestamps_recorded": False, "heads": [head]}]
    contract, flat = validate_and_summarize_trace(events, expected_layers=1, expected_heads=1)
    assert contract["post_commit_append_opportunities_per_stream"] == 1
    assert flat == [{"layer": 0, "kv_head": 0, "stream_append_opportunity": 0, **head}]
