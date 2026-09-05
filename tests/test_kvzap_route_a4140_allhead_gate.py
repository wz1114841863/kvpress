from tools.run_kvzap_route_a4140_qwen_allhead_native_storage_gate import aggregate_full_multi_tail_page_coverage


def test_allhead_page_state_requires_one_witness_not_every_head():
    rows = [
        {"kv_head": 0, "ever_sealed_packed_page": False, "ever_multi_page_packed": False, "max_packed_tail_tokens": 0},
        {"kv_head": 2, "ever_sealed_packed_page": True, "ever_multi_page_packed": True, "max_packed_tail_tokens": 63},
        {"kv_head": 7, "ever_sealed_packed_page": False, "ever_multi_page_packed": False, "max_packed_tail_tokens": 0},
    ]
    assert aggregate_full_multi_tail_page_coverage(rows) == {
        "requires_single_head_full_multi_tail": True,
        "witness_kv_heads": [2],
        "covered": True,
    }


def test_allhead_page_state_rejects_split_coverage_across_heads():
    rows = [
        {"kv_head": 0, "ever_sealed_packed_page": True, "ever_multi_page_packed": True, "max_packed_tail_tokens": 0},
        {"kv_head": 1, "ever_sealed_packed_page": False, "ever_multi_page_packed": False, "max_packed_tail_tokens": 5},
    ]
    assert not aggregate_full_multi_tail_page_coverage(rows)["covered"]
