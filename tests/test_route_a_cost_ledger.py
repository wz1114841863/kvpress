import pytest

from tools.analyze_kvzap_route_a4141_accounted_net_benefit_ledger import (
    energy_budget,
    inferred_trace_end_pending_residual,
)


def test_dynamic_energy_budget_accounts_payload_and_metadata_once():
    result = energy_budget(1000.0, 300.0, 20.0, 8)
    assert result["route_accounted_dynamic_energy_pj"] == 320.0
    assert result["differential_omitted_cost_budget_pj_per_request"] == 680.0
    assert result["differential_omitted_cost_budget_pj_per_observed_attention_position"] == 85.0


def test_negative_budget_and_zero_positions_are_not_hidden():
    result = energy_budget(100.0, 90.0, 20.0, 0)
    assert result["differential_omitted_cost_budget_pj_per_request"] == -10.0
    assert result["differential_omitted_cost_budget_pj_per_observed_attention_position"] is None


def test_pending_residual_uses_admitted_and_packed_counts():
    assert inferred_trace_end_pending_residual(
        {"admitted_retained_tokens": 12, "final_packed_state": {"packed_tokens": 10}}, "test"
    ) == 2
    with pytest.raises(ValueError, match="packed tokens exceed"):
        inferred_trace_end_pending_residual(
            {"admitted_retained_tokens": 9, "final_packed_state": {"packed_tokens": 10}}, "test"
        )
