from tools.analyze_kvzap_route_a435_microevent_quantum_sweep import summarize


def test_a435_summarizes_logical_microevents_without_hardware_inference():
    events = [
        {"phase": "prefill", "input_token_count": 64, "heads": [{"pending_tokens_after_service": 4, "admitted_tokens": 2, "packed_tokens_after_service": 2, "packed_full_page_count_after_service": 0}]},
        {"phase": "decode", "input_token_count": 1, "heads": [{"pending_tokens_after_service": 3, "admitted_tokens": 1, "packed_tokens_after_service": 3, "packed_full_page_count_after_service": 0}]},
    ]
    result = summarize(events)
    assert result["logical_event_count"] == 2
    assert result["max_prefill_event_tokens"] == 64
    assert result["admitted_tokens_total"] == 3
    assert result["full_pages_max"] == 0
