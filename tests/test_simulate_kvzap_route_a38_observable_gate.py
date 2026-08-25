from tools.simulate_kvzap_route_a38_observable_gate import choose_observable_path


def test_observable_gate_uses_only_threshold_features():
    row = {"fallback_full_kv": "False", "pending_dense_tokens": "12", "max_bank_burst_count": "3", "hybrid_total_cycle_proxy": "0.1", "full_layer_cycle_proxy": "999"}
    assert choose_observable_path(row, pending_threshold=16, max_bank_burst_threshold=4) == ("hybrid", "observable_thresholds_passed")
    assert choose_observable_path(row, pending_threshold=8, max_bank_burst_threshold=4) == ("full_kv", "pending_tokens_above_threshold")
    assert choose_observable_path(row, pending_threshold=16, max_bank_burst_threshold=2) == ("full_kv", "max_bank_bursts_above_threshold")


def test_observable_gate_preserves_staging_fallback():
    row = {"fallback_full_kv": "True", "pending_dense_tokens": "0", "max_bank_burst_count": "0"}
    assert choose_observable_path(row, pending_threshold=1024, max_bank_burst_threshold=1024) == ("full_kv", "staging_capacity_fallback")
