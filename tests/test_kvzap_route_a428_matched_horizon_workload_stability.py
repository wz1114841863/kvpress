import pytest

from tools.run_kvzap_route_a428_matched_horizon_workload_stability import policy_decode_calls, require_source, summarize_events


def event(active, pages=2, tail=5):
    return {"packed_page_count": pages, "packed_tail_tokens": tail, "source_decisions": [{"source": name, "outcome": "partial" if name in active else "skip", "record_count": 3 if name in active else 0} for name in ("hot", "pending", "packed")]}


def test_a428_summary_is_logical_and_tracks_record_and_page_witnesses():
    row = summarize_events([event({"hot", "packed"}), event({"hot", "pending", "packed"}, pages=3, tail=9)])
    assert row["event_count"] == 2
    assert row["source_outcome_counts"]["pending"] == {"partial": 1, "skip": 1}
    assert row["source_record_count_distribution"]["packed"]["sum"] == 6
    assert row["packed_page_witness_distribution"]["max"] == 3


def test_a428_requires_shared_source_contract_without_equating_cap_and_calls():
    source = {"config": {"max_new_tokens": 8}, "policy_decode_call_count_by_layer": {str(i): 7 for i in range(36)}, "replay_event_coverage": {"layers": [{"layer": i, "expected_kv_heads": list(range(8)), "observed_kv_heads": list(range(8)), "missing_kv_heads": [], "unexpected_kv_heads": []} for i in range(36)]}}
    assert require_source(source, cap=8) == 7
    source["policy_decode_call_count_by_layer"]["0"] = 6
    with pytest.raises(ValueError, match="consistent"):
        policy_decode_calls(source)
