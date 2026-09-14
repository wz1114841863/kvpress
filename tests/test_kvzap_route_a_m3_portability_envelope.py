import pytest

from tools.compare_kvzap_route_a_m3_portability_envelope import M3_SCHEMA, lifecycle_summary, require_true


def test_m3_schema_is_versioned():
    assert M3_SCHEMA == "kvzap-route-a-m3-portability-envelope-comparison-1.0"


def test_required_guards_reject_false_value():
    with pytest.raises(ValueError, match="lacks required"):
        require_true({"observational_guards": {"a": False}}, ("a",), label="test")


def test_lifecycle_summary_retains_scalar_state_only():
    point = {"admission_budget": 1, "replayed_same_mask_route_a": {"source_coverage": {"hot_observed": True, "pending_observed": True, "packed_observed": True}, "final_lifecycle_state": [{"layer": 0, "heads": [{"hot_tokens": 128, "pending_tokens": 4, "packed_tokens": 1, "packed_page_count": 1, "packed_full_page_count": 0, "packed_tail_tokens": 1}]}], "page_witness": {"covered": False}}}
    summary = lifecycle_summary(point)
    assert summary["layer_kv_head_state_count"] == 1
    assert summary["final_state_maxima"]["pending_tokens"] == 4
    assert "final_lifecycle_state" not in summary
