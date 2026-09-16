import pytest

from tools.analyze_kvzap_route_a432_policy_lifecycle_transition_envelope import summarize


def test_a432_summarizes_untimed_transition_rows_without_fifo_claim():
    result = summarize([{"phase": "prefill", "heads": [{"matured_kept_tokens": 3, "admitted_tokens": 1, "pending_tokens_after_maturity": 3, "pending_tokens_after_service": 2}]}, {"phase": "decode", "heads": [{"matured_kept_tokens": 1, "admitted_tokens": 1, "pending_tokens_after_maturity": 3, "pending_tokens_after_service": 2}]}])
    assert result["logical_transition_event_count"] == 2
    assert result["matured_kept_tokens_total"] == 4
    assert result["admitted_tokens_total"] == 2
    assert result["pending_after_service_max"] == 2
    assert result["phase_event_count"]["multi_token"] == 0


def test_a432_summary_rejects_empty_vectors():
    with pytest.raises(ValueError, match="empty"):
        summarize([])
