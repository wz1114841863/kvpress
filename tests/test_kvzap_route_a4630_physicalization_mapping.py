from tools.analyze_kvzap_route_a4630_physicalization_mapping import page_events


def test_a4630_page_mapping_keeps_tail_and_seal_events_explicit():
    assert page_events(15, 2, 16) == {"packed_tokens_after_mapping": 17, "new_page_allocations": 1, "newly_sealed_page_count": 1, "current_tail_tokens": 1, "current_tail_unused_token_slots": 15}


def test_a4630_zero_service_does_not_create_page_event():
    assert page_events(15, 0, 16)["new_page_allocations"] == 0
