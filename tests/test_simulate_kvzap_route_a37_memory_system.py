from tools.simulate_kvzap_route_a37_adaptive_gate import choose_layer_path
from tools.simulate_kvzap_route_a37_memory_system import layer_cost, pending_bank_profile


def test_round_robin_bursts_spread_across_banks():
    profile = pending_bank_profile(pending_by_head={0: 4}, kv_bytes=16, bank_count=4, burst_bytes=16, layout="round_robin_token")
    assert profile == (4, 4, 64, 4, 1)


def test_head_affine_mapping_exposes_bank_conflict():
    profile = pending_bank_profile(pending_by_head={0: 2, 4: 2}, kv_bytes=16, bank_count=4, burst_bytes=16, layout="head_affine")
    assert profile == (4, 4, 64, 1, 4)


def test_layer_staging_overflow_uses_full_kv_reference():
    result = layer_cost(cache_tokens=10, pending_by_head={0: 3}, packed_by_head={0: (4, 1, 2)}, kv_bytes=16, window=2, bank_count=4, burst_bytes=16, bank_bytes_per_cycle=16, layout="round_robin_token", capacity=2, bandwidth=16, throughput=64, ops_per_token=1, metadata_bytes=8, metadata_cycles=1, position_bytes=8, merge_bytes=16, merge_cycles=2, pe_count=1, scheduler="static_head", head_dispatch_cycles=0)
    assert result["fallback"] is True
    assert result["hybrid_bytes"] == result["full_bytes"] == 160
    assert result["hybrid_cycles"] == result["full_cycles"]


def test_gate_selects_hybrid_only_when_guarded_cost_is_lower():
    row = {"fallback_full_kv": "0", "full_layer_bytes": "100", "hybrid_total_bytes": "85", "full_layer_cycle_proxy": "20", "hybrid_total_cycle_proxy": "18"}
    assert choose_layer_path(row, objective="bytes", guard_fraction=0.10)[0] == "hybrid"
    assert choose_layer_path(row, objective="cycles", guard_fraction=0.15)[0] == "full_kv"


def test_gate_preserves_capacity_fallback_reason():
    row = {"fallback_full_kv": "1", "full_layer_bytes": "100", "hybrid_total_bytes": "1", "full_layer_cycle_proxy": "20", "hybrid_total_cycle_proxy": "1"}
    assert choose_layer_path(row, objective="cycles", guard_fraction=0.0) == ("full_kv", "staging_capacity_fallback")
