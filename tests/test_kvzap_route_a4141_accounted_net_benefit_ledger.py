from tools.analyze_kvzap_route_a4141_accounted_net_benefit_ledger import (
    energy_budget,
    inferred_trace_end_pending_residual,
    ratio,
    saving_fraction,
)


def test_energy_budget_charges_only_explicit_route_m2_control_entry_energy():
    result = energy_budget(1000.0, 300.0, 20.0, 8)
    assert result["route_accounted_dynamic_energy_pj"] == 320.0
    assert result["differential_omitted_cost_budget_pj_per_request"] == 680.0
    assert result["differential_omitted_cost_budget_pj_per_observed_attention_position"] == 85.0
    assert result["route_over_full_accounted_dynamic_energy_ratio"] == 0.32


def test_ratio_helpers_do_not_invent_a_value_for_zero_full_baseline():
    assert ratio(1.0, 0.0) is None
    assert saving_fraction(1.0, 0.0) is None
    assert saving_fraction(25.0, 100.0) == 0.75


def test_finalization_uses_observed_admitted_and_packed_totals_not_a_fabricated_field():
    lifecycle = {"admitted_retained_tokens": 12, "final_packed_state": {"packed_tokens": 12}}
    assert inferred_trace_end_pending_residual(lifecycle, "unit") == 0
