import pytest

from tools.validate_kvzap_route_a313_short_horizon_guard import validate_rows


def row(**overrides):
    base = {"request_id": "unit", "deferred_decode_steps": "17", "admission_flush_token_budget": "512", "bank_count": "16", "burst_bytes": "128", "bank_bytes_per_cycle": "64", "pending_layout": "round_robin_token", "staging_capacity_tokens_per_layer": "8192", "decode_steps": "17", "initial_full_kv_call_count": "17", "staging_full_kv_call_count": "0", "staging_full_kv_layer_count": "0", "full_kv_cumulative_bytes": "100", "candidate_cumulative_bytes": "100", "full_kv_cumulative_cycle_proxy": "20", "candidate_cumulative_cycle_proxy": "20", "net_bytes_saved_fraction": "0", "net_cycle_proxy_saved_fraction": "0"}
    return {**base, **overrides}


def test_guard_accepts_exact_no_service_full_kv_control():
    checked = validate_rows([row()], horizons={17})
    assert checked[0]["guard_passed"] is True


def test_guard_rejects_last_step_admission_or_nonzero_cost():
    with pytest.raises(ValueError, match="did not degenerate"):
        validate_rows([row(candidate_cumulative_cycle_proxy="21")], horizons={17})
