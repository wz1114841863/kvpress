from tools.analyze_kvzap_route_a4133_packed_kv_hbm_realization import (
    PAGE_BYTES,
    POSITION_SIDECAR_BYTES_PER_PAGE,
    phase_rows,
    source_buffer_sensitivity,
    summarize,
)


def event(query_head: int, phase: str = "decode"):
    return {
        "logical_event_sequence": query_head,
        "layer": 0,
        "kv_head": 0,
        "query_head": query_head,
        "cache_position": 127,
        "phase": phase,
        "merge_after_source_decisions": True,
        "packed_page_count": 1,
        "packed_full_page_count": 1,
        "packed_tail_tokens": 0,
        "source_decisions": [
            {"source": "hot", "record_count": 64},
            {"source": "pending", "record_count": 0},
            {"source": "packed", "record_count": 64},
        ],
    }


def test_fair_full_and_packed_gqa_group_accounting_uses_same_one_group():
    events = [event(query) for query in range(4)]
    full = summarize([events[0]], packed=False)
    packed = summarize([events[0]], packed=True)
    assert full["legal_gqa_reference_attention_groups"] == packed["legal_gqa_reference_attention_groups"] == 1
    assert full["page_fetches"] == 2
    assert packed["page_fetches"] == 1
    assert packed["position_sidecar_bytes"] == POSITION_SIDECAR_BYTES_PER_PAGE
    assert full["page_rounded_payload_bytes"] == 2 * PAGE_BYTES


def test_source_buffer_has_only_single_and_ping_pong_sensitivity():
    route = summarize([event(0)], packed=True)
    candidates = source_buffer_sensitivity(route)
    assert [row["candidate"] for row in candidates[:2]] == [
        "S1_one_32KiB_page_source_buffer",
        "S2_two_32KiB_ping_pong_page_source_buffers",
    ]
    assert candidates[0]["source_buffer_capacity_bytes"] == PAGE_BYTES
    assert candidates[1]["source_buffer_capacity_bytes"] == 2 * PAGE_BYTES


def test_phase_report_separates_multi_token_and_decode():
    rows = phase_rows([event(0, "multi_token"), event(1, "decode")])
    assert set(rows) == {"multi_token", "decode"}
    assert rows["decode"]["observed_unique_cache_positions"] == 1
