from tools.run_kvzap_route_a460_steady_state_gate import analyze_tail


def event(layer, pending):
    return {
        "phase": "decode",
        "layer": layer,
        "heads": [{"kv_head": 0, "pending_tokens_after_service": value} for value in pending],
    }


def test_a460_tail_analysis_reports_only_sustained_logical_growth():
    stable = [event(0, [2]), event(0, [1]), event(0, [2])]
    summary = analyze_tail(stable, layers=(0,), tail_events=3)
    assert summary["sustained_non_decreasing_pending_growth_witness_count"] == 0
    growing = [event(0, [1]), event(0, [2]), event(0, [3])]
    summary = analyze_tail(growing, layers=(0,), tail_events=3)
    assert summary["sustained_non_decreasing_pending_growth_witnesses"] == [
        {"layer": 0, "kv_head": 0, "tail_start_pending": 1, "tail_end_pending": 3}
    ]
