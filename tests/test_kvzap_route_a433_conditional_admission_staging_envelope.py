from tools.analyze_kvzap_route_a433_conditional_admission_staging_envelope import conditional_quantum_summary, simulate_layer, verify_budget_one_reproduction


def event(start, matured, reference_pending):
    return {"layer": 0, "phase": "decode", "start_position": start, "end_position": start, "heads": [{"matured_kept_tokens": matured, "pending_tokens_after_service": reference_pending}]}


def test_budget_one_reproduces_scalar_a432_pending_recurrence():
    events = [event(0, 4, 3), event(1, 2, 4)]
    assert verify_budget_one_reproduction(events)["passed"] is True
    assert [row["pending_after_service_head_tokens"] for row in simulate_layer(events, 2)] == [2, 2]


def test_conditional_capacity_is_not_a_fifo_selection():
    result = conditional_quantum_summary([event(0, 4, 3), event(1, 2, 4)], 1, (3, 4))
    assert result["required_conditional_staging_capacity_head_tokens_no_breach"] == 4
    assert result["capacity_rows"][0]["no_breach_on_this_trace"] is False
    assert result["capacity_rows"][1]["no_breach_on_this_trace"] is True
    assert "cannot infer page sealing" in result["boundaries"][1]
