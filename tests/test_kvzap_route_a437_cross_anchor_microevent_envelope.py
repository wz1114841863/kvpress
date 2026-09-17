import pytest

from tools.analyze_kvzap_route_a437_cross_anchor_microevent_envelope import (
    normalize_workload_row,
    summarize_direction,
)


def test_a437_reports_within_row_direction_without_pooling():
    row = normalize_workload_row(
        {
            "preset": "retrieval",
            "quantum_rows": [
                {"admission_budget": 1, "transition_summary": {"logical_event_count": 2, "prefill_event_count": 1, "max_prefill_event_tokens": 64, "pending_p95": 10, "pending_max": 20, "admitted_tokens_total": 1, "packed_tokens_max": 2, "full_pages_max": 0}},
                {"admission_budget": 8, "transition_summary": {"logical_event_count": 2, "prefill_event_count": 1, "max_prefill_event_tokens": 64, "pending_p95": 8, "pending_max": 19, "admitted_tokens_total": 8, "packed_tokens_max": 8, "full_pages_max": 1}},
                {"admission_budget": 32, "transition_summary": {"logical_event_count": 2, "prefill_event_count": 1, "max_prefill_event_tokens": 64, "pending_p95": 5, "pending_max": 15, "admitted_tokens_total": 20, "packed_tokens_max": 20, "full_pages_max": 2}},
            ],
        }
    )
    result = summarize_direction(row)["within_row_q_sensitivity"]
    assert result["q1_to_q32"]["pending_p95"] == {"absolute_reduction": 5, "relative_reduction_fraction": 0.5}
    assert result["q1_to_q32"]["full_pages_max_absolute_increase"] == 2
    assert all(result["direction_matrix"].values())


def test_a437_rejects_changed_microevent_shape_across_q():
    row = {
        "preset": "reasoning",
        "quantum_rows": [
            {"admission_budget": 1, "transition_summary": {"logical_event_count": 2, "prefill_event_count": 1, "max_prefill_event_tokens": 64, "pending_p95": 1, "pending_max": 1, "admitted_tokens_total": 1, "packed_tokens_max": 1, "full_pages_max": 0}},
            {"admission_budget": 8, "transition_summary": {"logical_event_count": 3, "prefill_event_count": 1, "max_prefill_event_tokens": 64, "pending_p95": 1, "pending_max": 1, "admitted_tokens_total": 1, "packed_tokens_max": 1, "full_pages_max": 0}},
            {"admission_budget": 32, "transition_summary": {"logical_event_count": 2, "prefill_event_count": 1, "max_prefill_event_tokens": 64, "pending_p95": 1, "pending_max": 1, "admitted_tokens_total": 1, "packed_tokens_max": 1, "full_pages_max": 0}},
        ],
    }
    with pytest.raises(ValueError, match="workload changed"):
        normalize_workload_row(row)
