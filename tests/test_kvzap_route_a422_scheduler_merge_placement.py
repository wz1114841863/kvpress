import copy

import pytest

from tools.analyze_kvzap_route_a422_scheduler_merge_placement import A422_SCHEMA, placement_rows, source_counts


def horizon():
    return {"merge_calls": 2, "actual_partial_calls": 4, "source_rows": [
        {"source": "hot", "partial_attention_calls": 2, "empty_source_skip_calls": 0, "source_decisions": 2},
        {"source": "pending", "partial_attention_calls": 0, "empty_source_skip_calls": 2, "source_decisions": 2},
        {"source": "packed", "partial_attention_calls": 2, "empty_source_skip_calls": 0, "source_decisions": 2},
    ]}


def test_a422_schema_and_source_merge_conservation():
    assert A422_SCHEMA.endswith("scheduler-merge-placement-1.0")
    assert source_counts(horizon()) == (2, {"hot": 2, "pending": 0, "packed": 2})


def test_a422_rejects_source_merge_conservation_failure():
    bad = copy.deepcopy(horizon())
    bad["source_rows"][2]["empty_source_skip_calls"] = 1
    with pytest.raises(ValueError, match="conservation"):
        source_counts(bad)


def test_a422_split_explicitly_exports_each_active_partial_and_co_located_does_not():
    rows = placement_rows(label="unit", horizon=horizon(), state_bytes=[16], merge_work=[1.0], schedulers=["static_head"])
    co_located = [row for row in rows if row["organization"] == "co_located"]
    split = [row for row in rows if row["organization"] == "split_source"]
    assert len(co_located) == 1
    assert co_located[0]["cross_engine_partial_state_transfers"] == 0
    assert split
    assert all(row["cross_engine_partial_state_transfers"] == 4 for row in split)
    assert all(row["cross_engine_state_payload_bytes"] == 64 for row in split)
    assert {row["modeled_inflight_partial_state_capacity_axis"] for row in split} == {1, 2, 3}
