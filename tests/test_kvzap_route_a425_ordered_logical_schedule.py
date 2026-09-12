import copy

import pytest

from tools.analyze_kvzap_route_a425_ordered_logical_schedule import (
    A425_SCHEMA,
    simulate_co_located,
    simulate_split_source,
    validate_events,
    verify_manifest_event_summary,
)


def event(sequence, *, hot="partial", pending="skip", packed="partial"):
    outcomes = {"hot": hot, "pending": pending, "packed": packed}
    return {
        "logical_event_sequence": sequence,
        "layer": 0,
        "kv_head": 0,
        "query_head": 0,
        "cache_position": 128 + sequence,
        "merge_after_source_decisions": True,
        "source_decisions": [
            {"source": source, "outcome": outcomes[source], "record_count": 1 if outcomes[source] == "partial" else 0}
            for source in ("hot", "pending", "packed")
        ],
    }


def test_a425_schema_and_event_source_merge_validation():
    events = [event(0), event(1, packed="skip")]
    validation = validate_events(events)
    assert A425_SCHEMA.endswith("ordered-logical-schedule-1.0")
    assert validation["event_count"] == 2
    assert validation["merge_marker_count"] == 2
    assert validation["source_outcome_counts"]["hot"] == {"partial": 2, "skip": 0}
    assert validation["source_outcome_counts"]["packed"] == {"partial": 1, "skip": 1}


def test_a425_rejects_noncontiguous_or_timestamp_bearing_event():
    with pytest.raises(ValueError, match="contiguous"):
        validate_events([event(1)])
    timed = [event(0)]
    timed[0]["python_timestamp_ns"] = 1
    with pytest.raises(ValueError, match="timestamp"):
        validate_events(timed)


def test_a425_split_obeys_partial_to_merge_dependency_without_fifo_claim():
    events = [event(0), event(1, packed="skip")]
    co_located = simulate_co_located(
        events=events, source_work_units=1.0, merge_work_units=1.0, submission_work_units=1.0
    )
    split = simulate_split_source(
        events=events, source_work_units=1.0, merge_work_units=1.0, transfer_work_units=1.0,
        reduction_dispatch_work_units=0.0, submission_work_units=1.0,
    )
    assert co_located["logical_partial_state_exports"] == 0
    assert split["logical_partial_state_exports"] == 3
    assert split["model_max_partial_ready_to_merge_start_work_units"] >= 0.0
    assert "queue occupancy" in split["interpretation"]
    assert split["model_completion_work_position"] >= 0.0


def test_a425_rejects_partial_skip_record_count_disagreement():
    broken = [event(0)]
    broken[0]["source_decisions"][0]["record_count"] = 0
    with pytest.raises(ValueError, match="agree"):
        validate_events(copy.deepcopy(broken))


def test_a425_binds_gzip_accounting_to_a424_independent_summary():
    validation = validate_events([event(0), event(1, packed="skip")])
    a424 = {"diagnostic": {"trace_on_independent": {"logical_event_summary": {
        "event_count": 2,
        "merge_event_count": 2,
        "by_source": {
            "hot": {"partial_attention_events": 2, "empty_source_skip_events": 0},
            "pending": {"partial_attention_events": 0, "empty_source_skip_events": 2},
            "packed": {"partial_attention_events": 1, "empty_source_skip_events": 1},
        },
        "observed_layer_kv_heads": [{"layer": 0, "kv_heads": [0]}],
    }}}}
    verify_manifest_event_summary(a424, validation)
    a424["diagnostic"]["trace_on_independent"]["logical_event_summary"]["by_source"]["hot"]["partial_attention_events"] = 1
    with pytest.raises(ValueError, match="partial"):
        verify_manifest_event_summary(a424, validation)
