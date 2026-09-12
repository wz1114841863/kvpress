import torch

from kvpress.route_a_attention import RouteALogicalEventRecorder, RouteAPackedAttentionState
from tools.run_kvzap_route_a424_ordered_logical_event_gate import EVENT_SCHEMA, validate_event_summary


def test_a424_records_ordered_untimed_source_decisions_without_changing_attention():
    recorder = RouteALogicalEventRecorder()
    state = RouteAPackedAttentionState(heads=1, head_dim=2, window=1, page_tokens=2, admission_budget=1, elide_empty_sources=True, logical_event_recorder=recorder, logical_layer=3)
    keys = torch.tensor([[[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]])
    keep = torch.tensor([[True, True, True]])
    state.append(keys, keys, keep, start_position=0)
    output = state.attention(torch.tensor([1.0, 0.0]), head=0, logical_query_head=7, logical_cache_position=2, logical_phase="decode")
    assert torch.isfinite(output).all()
    event = recorder.events[0]
    assert EVENT_SCHEMA.endswith("logical-attention-events-1.0")
    assert event["logical_event_sequence"] == 0
    assert event["layer"] == 3 and event["kv_head"] == 0 and event["query_head"] == 7
    assert [row["source"] for row in event["source_decisions"]] == ["hot", "pending", "packed"]
    assert event["merge_after_source_decisions"] is True
    summary = recorder.summary()
    validate_event_summary(summary=summary, expected_heads={3: (0,)})
    assert summary["timestamps_recorded"] is False
