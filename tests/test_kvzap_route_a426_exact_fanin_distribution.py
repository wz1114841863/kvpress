import pytest

from tools.analyze_kvzap_route_a426_exact_fanin_distribution import (
    A426_SCHEMA,
    summarize_exact_fanin,
    verify_against_a423,
)
from tools.analyze_kvzap_route_a425_ordered_logical_schedule import validate_events


def event(sequence, active):
    return {
        "logical_event_sequence": sequence,
        "layer": 0,
        "kv_head": 0,
        "query_head": 0,
        "cache_position": 128 + sequence,
        "merge_after_source_decisions": True,
        "source_decisions": [
            {"source": source, "outcome": "partial" if source in active else "skip", "record_count": 1 if source in active else 0}
            for source in ("hot", "pending", "packed")
        ],
    }


def a423(merges, hot, pending, packed):
    return {"report": {"rows": [{
        "horizon": "h32", "merge_decisions": merges,
        "marginal_source_partial_counts": {"hot": hot, "pending": pending, "packed": packed},
    }]}}


def test_a426_exact_fanin_and_combinations():
    events = [event(0, {"hot"}), event(1, {"hot", "packed"}), event(2, {"hot", "pending", "packed"})]
    summary = summarize_exact_fanin(events)
    assert A426_SCHEMA.endswith("exact-fanin-distribution-1.0")
    assert summary["exact_fan_in_event_counts"] == {
        "one_active_source": 1, "two_active_sources": 1, "three_active_sources": 1,
    }
    assert summary["exact_active_source_combinations"] == {"hot": 1, "hot+packed": 1, "hot+pending+packed": 1}
    assert summary["groups_with_three_source_event"] == 1


def test_a426_exact_counts_must_fit_a423_marginal_bounds():
    events = [event(0, {"hot"}), event(1, {"hot", "packed"}), event(2, {"hot", "pending", "packed"})]
    exact = summarize_exact_fanin(events)
    result = verify_against_a423(exact=exact, a424_validation=validate_events(events), a423=a423(3, 3, 1, 2))
    assert result["exact_counts_within_a423_bounds"] is True
    with pytest.raises(ValueError, match="partial accounting"):
        verify_against_a423(exact=exact, a424_validation=validate_events(events), a423=a423(3, 3, 0, 2))
