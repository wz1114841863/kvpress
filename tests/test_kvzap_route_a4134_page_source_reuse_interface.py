from tools.analyze_kvzap_route_a4134_page_source_reuse_interface import (
    PAGE_BYTES,
    PARTIAL_STATE_BYTES_FP32,
    SIDECAR_BYTES_PER_PAGE,
    add_actions,
    blank_actions,
    frozen_interface,
    summarize,
    verify_a4133,
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


def test_packed_page_release_waits_for_four_consumers_and_updates():
    actions = blank_actions()
    add_actions(actions, event(0), packed=True)
    assert actions["packed_payload_fill_actions"] == 1
    assert actions["source_buffer_ready_actions"] == 1
    assert actions["packed_page_multicast_consume_actions"] == 4
    assert actions["source_buffer_release_actions_after_all_four_consumers"] == 1
    assert actions["partial_state_record_update_actions"] == 4 * (64 + 64)
    assert actions["cross_source_online_merge_actions"] == 4


def test_full_kv_has_same_gqa_lifecycle_without_sidecar_or_cross_source_merge():
    summary = summarize([event(0)], packed=False)
    actions = summary["action_counts"]
    assert actions["full_kv_payload_fill_actions"] == 2
    assert actions["full_kv_page_multicast_consume_actions"] == 8
    assert actions["source_buffer_release_actions_after_all_four_consumers"] == 2
    assert actions.get("cross_source_online_merge_actions", 0) == 0
    assert summary["total_internal_interface_beats"] == 2 * (PAGE_BYTES // 256)


def test_interface_keeps_256b_internal_and_partial_state_pipeline_local():
    interface = frozen_interface()
    assert interface["internal_unit"]["not_a_physical_hbm_transaction_or_burst"] is True
    assert interface["partial_state"]["logical_placement"] == "pipeline-local from source initialization through final online merge"
    assert interface["partial_state"]["four_query_head_interface_bytes_if_fp32"] == PARTIAL_STATE_BYTES_FP32
    assert interface["internal_unit"]["sidecar_beats"] == SIDECAR_BYTES_PER_PAGE // 256


def test_a4133_compatibility_guard_uses_current_legal_group_field_name():
    groups = [event(0)]
    full, packed = summarize(groups, packed=False), summarize(groups, packed=True)
    report = {
        "workload_rows": [{
            "workload": "retrieval",
            "all_observed_phases_aggregate": {
                "fair_full_kv_legal_gqa_reuse": {
                    "legal_gqa_reference_attention_groups": full["legal_gqa_groups"],
                    "page_fetches": full["action_counts"]["full_kv_payload_fill_actions"],
                    "declared_256B_transfer_beats": full["total_internal_interface_beats"],
                },
                "route_a_packed_legal_gqa_reuse": {
                    "legal_gqa_reference_attention_groups": packed["legal_gqa_groups"],
                    "page_fetches": packed["action_counts"]["packed_payload_fill_actions"],
                    "declared_256B_transfer_beats": packed["total_internal_interface_beats"],
                },
            },
        }],
    }
    verify_a4133(report, "retrieval", groups)
