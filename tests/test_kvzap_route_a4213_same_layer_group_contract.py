from tools.analyze_kvzap_route_a4213_same_layer_group_contract import analyze


def event(sequence, query_head):
    return {"logical_event_sequence": sequence, "layer": 0, "kv_head": 0, "query_head": query_head, "packed_page_count": 1, "packed_full_page_count": 0, "packed_tail_tokens": 3,
            "source_decisions": [{"source": "hot", "outcome": "partial", "record_count": 2, "first_position": 1, "last_position": 2}, {"source": "pending", "outcome": "skip", "record_count": 0, "first_position": None, "last_position": None}, {"source": "packed", "outcome": "partial", "record_count": 3, "first_position": 3, "last_position": 5}]}


def test_shared_dispatch_keeps_per_query_partial_and_merge_state():
    events = [event(0, 0), event(1, 1)]
    epochs = [{"logical_event_sequence": 0, "forward_epoch": 0, "layer_dispatch_epoch": 0, "layer": 0, "kv_head": 0, "query_head": 0}, {"logical_event_sequence": 1, "forward_epoch": 0, "layer_dispatch_epoch": 0, "layer": 0, "kv_head": 0, "query_head": 1}]
    result = analyze(events, epochs)
    assert result["shared_kv_head_group_source_dispatch_control_units_total"] == 2
    assert result["independent_source_dispatch_control_units_total"] == 4
    assert result["partial_softmax_state_instances_unchanged"] == 2
    assert result["online_merge_instances_unchanged"] == 2
