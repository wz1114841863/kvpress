from tools.analyze_kvzap_route_a4132_packed_cold_hbm_traffic import (
    PAGE_BYTES,
    accounting,
    gqa_groups,
    metric,
)


def event(query_head: int):
    return {
        "logical_event_sequence": query_head,
        "layer": 0,
        "kv_head": 0,
        "query_head": query_head,
        "cache_position": 127,
        "phase": "decode",
        "merge_after_source_decisions": True,
        "packed_page_count": 1,
        "packed_full_page_count": 0,
        "packed_tail_tokens": 10,
        "source_decisions": [
            {"source": "hot", "record_count": 128},
            {"source": "pending", "record_count": 0},
            {"source": "packed", "record_count": 10},
        ],
    }


def test_event_level_gqa_group_deduplicates_only_verified_identical_sources():
    events = [event(query) for query in range(4)]
    grouped = gqa_groups(events)
    assert len(grouped) == 1
    no_reuse, reuse = metric(events), metric(grouped)
    assert no_reuse["packed_page_rounded_hbm_bytes"] == 4 * (128 * 512 + PAGE_BYTES)
    assert reuse["packed_page_rounded_hbm_bytes"] == 128 * 512 + PAGE_BYTES


def test_gqa_group_rejects_different_packed_page_state():
    events = [event(query) for query in range(4)]
    events[-1]["packed_tail_tokens"] = 11
    events[-1]["source_decisions"][-1]["record_count"] = 11
    try:
        gqa_groups(events)
    except ValueError as error:
        assert "source/page state differs" in str(error)
    else:
        raise AssertionError("GQA grouping accepted unequal source state")


def test_exact_full_packed_page_uses_zero_tail_encoding():
    events = [event(query) for query in range(4)]
    for row in events:
        row["packed_full_page_count"] = 1
        row["packed_tail_tokens"] = 0
        row["source_decisions"][-1]["record_count"] = 64
    assert metric(events)["packed_page_requests"] == 4
