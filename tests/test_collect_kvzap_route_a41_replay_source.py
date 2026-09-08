import pytest

from tools.collect_kvzap_route_a41_replay_source import assert_all_kv_heads_covered, replay_event_coverage


def test_replay_event_coverage_records_per_head_mask_events_without_claiming_route_a_state():
    coverage = replay_event_coverage(
        events={0: {(0, 4): (True, -3.0), (0, 5): (False, -5.0), (1, 7): (True, -3.5)}},
        expected_heads={0: (0, 1)},
        window_size=5,
    )
    assert coverage["layer_count"] == 1
    layer = coverage["layers"][0]
    assert layer["missing_kv_heads"] == []
    assert layer["per_head"] == [
        {"kv_head": 0, "event_count": 2, "keep_count": 1, "keep_at_or_after_hot_window_count": 0, "max_cache_position": 5},
        {"kv_head": 1, "event_count": 1, "keep_count": 1, "keep_at_or_after_hot_window_count": 1, "max_cache_position": 7},
    ]
    assert_all_kv_heads_covered(coverage)


def test_replay_event_coverage_rejects_missing_or_unexpected_kv_heads_when_requested():
    coverage = replay_event_coverage(
        events={0: {(0, 4): (True, -3.0), (2, 6): (True, -3.0)}},
        expected_heads={0: (0, 1)},
        window_size=1,
    )
    with pytest.raises(AssertionError, match="KV-head coverage"):
        assert_all_kv_heads_covered(coverage)
