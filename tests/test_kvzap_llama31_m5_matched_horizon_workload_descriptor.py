import pytest

from tools.run_kvzap_llama31_m5_matched_horizon_workload_descriptor import (
    M5_SCHEMA,
    summarize_events,
    validate_event_summary,
)


def event(active, *, layer=0, head=0, pages=2, tail=3):
    return {
        "logical_event_sequence": 0,
        "layer": layer,
        "kv_head": head,
        "packed_page_count": pages,
        "packed_tail_tokens": tail,
        "merge_after_source_decisions": True,
        "source_decisions": [
            {"source": source, "outcome": "partial" if source in active else "skip", "record_count": 2 if source in active else 0}
            for source in ("hot", "pending", "packed")
        ],
    }


def test_m5_schema_is_versioned():
    assert M5_SCHEMA == "kvzap-llama31-m5-matched-horizon-workload-descriptor-1.0"


def test_m5_descriptor_keeps_normalized_fanin_and_layer_head_rows():
    result = summarize_events([
        event({"hot", "packed"}),
        event({"hot", "pending", "packed"}, pages=4, tail=5),
    ])
    assert result["logical_event_count"] == 2
    assert result["fan_in_fractions"] == {"2_active_sources": 0.5, "3_active_sources": 0.5}
    assert result["source_combination_fractions"]["hot+packed"] == 0.5
    assert result["packed_page_tail_distribution"]["max"] == 4
    assert result["per_layer_kv_head"] == [
        {
            "layer": 0,
            "kv_head": 0,
            "logical_event_count": 2,
            "fan_in_counts": {"2_active_sources": 1, "3_active_sources": 1},
            "source_combination_counts": {"hot+packed": 1, "hot+pending+packed": 1},
            "source_record_count_distribution": {
                "hot": {"sample_count": 2, "sum": 4, "p50": 2, "p95": 2, "max": 2},
                "pending": {"sample_count": 1, "sum": 2, "p50": 2, "p95": 2, "max": 2},
                "packed": {"sample_count": 2, "sum": 4, "p50": 2, "p95": 2, "max": 2},
            },
            "packed_page_tail_distribution": {"p50": 2, "p95": 2, "max": 4, "tail_p50": 3, "tail_p95": 3, "tail_max": 5},
        }
    ]


def test_m5_event_guard_rejects_timestamp_or_missing_head_coverage():
    summary = {
        "event_count": 1,
        "merge_event_count": 1,
        "timestamps_recorded": False,
        "by_source": {source: {"partial_attention_events": 1, "empty_source_skip_events": 0} for source in ("hot", "pending", "packed")},
        "observed_layer_kv_heads": [{"layer": 0, "kv_heads": [0]}],
    }
    validate_event_summary(summary, layers=1, heads=1)
    summary["timestamps_recorded"] = True
    with pytest.raises(ValueError, match="timestamp"):
        validate_event_summary(summary, layers=1, heads=1)
