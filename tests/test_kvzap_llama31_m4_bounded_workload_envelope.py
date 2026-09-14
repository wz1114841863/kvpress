import pytest

from tools.analyze_kvzap_llama31_m4_bounded_workload_envelope import M4_SCHEMA, summarize_point


def test_m4_schema_is_versioned():
    assert M4_SCHEMA == "kvzap-llama31-m4-bounded-workload-envelope-1.0"


def test_m4_point_summary_keeps_only_bounded_scalars():
    point = {
        "admission_budget": 512,
        "replayed_same_mask_route_a": {
            "policy_coverage": {"layers": [{"original_mask_decision_count": 2, "heads": [{"kv_head": 0}]}]},
            "source_coverage": {"hot_observed": True, "pending_observed": False, "packed_observed": True},
            "page_witness": {"witnesses": [{"layer": 0, "kv_head": 0}]},
            "execution_dtype_ulp_breach_summary": {"layers": [{"mode": "record_only", "executed_dtype_ulp_limit": 16.0, "breach_count": 1, "max_observed_ulps": 33.0, "max_observed_ulps_is_infinite": False}]},
            "final_lifecycle_state": [{"heads": [{"hot_tokens": 128, "pending_tokens": 0, "packed_tokens": 65, "packed_page_count": 2, "packed_full_page_count": 1, "packed_tail_tokens": 1}]}],
        },
    }
    summary = summarize_point(point)
    assert summary["all_layer_mask_decision_count"] == 2
    assert summary["page_witness_count"] == 1
    assert summary["execution_dtype_ulp_diagnostic"]["breach_count"] == 1
    assert summary["final_state_maxima"]["packed_tokens"] == 65
    assert "final_lifecycle_state" not in summary


def test_m4_point_summary_rejects_missing_route_data():
    with pytest.raises(KeyError):
        summarize_point({"admission_budget": 1, "replayed_same_mask_route_a": {}})
