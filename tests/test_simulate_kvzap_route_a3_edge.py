import json

import pytest

from tools.simulate_kvzap_route_a3_edge import admission_task, derive_admission_constraints, load_architecture_config, parse_args, resolve_admission_points, schedule_admission, simulate_edge


def test_admission_dse_axes_override_legacy_single_point_flags():
    args = parse_args(["--workload-suite", "conservative_three", "--architecture-config", "edge.json", "--a1-dir", "a1", "--output-dir", "out", "--admission-engine-count", "1", "--admission-pack-bytes-per-cycle", "512", "--admission-engine-counts", "1", "2", "4", "--admission-pack-bytes-per-cycle-points", "512", "1024"])
    assert resolve_admission_points(args) == ([1, 2, 4], [512.0, 1024.0])


def test_admission_dse_axes_reject_duplicates():
    args = parse_args(["--workload-suite", "conservative_three", "--architecture-config", "edge.json", "--a1-dir", "a1", "--output-dir", "out", "--admission-engine-counts", "1", "1"])
    with pytest.raises(ValueError, match="duplicate"):
        resolve_admission_points(args)


def test_constraint_table_reports_minimum_capacity_and_full_fallback():
    common = {"workload": "w", "request_id": "r", "page_tokens": 64, "bandwidth_bytes_per_cycle": 2048.0, "attention_engine_count": 4, "baseline": "packed_deferred_length_aware_head", "policy_kind": "deferred_observed_steps", "policy_threshold_decode_steps": 5, "decode_steps": 17}
    summaries = [
        {**common, "policy_activation_decode_step": 6, "admission_engine_count": 1, "admission_pack_bytes_per_cycle": 512.0, "net_cycles_saved": -3.0, "net_cycles_saved_fraction": -0.1},
        {**common, "policy_activation_decode_step": 6, "admission_engine_count": 1, "admission_pack_bytes_per_cycle": 2048.0, "net_cycles_saved": 2.0, "net_cycles_saved_fraction": 0.02},
        {**common, "policy_activation_decode_step": 6, "admission_engine_count": 2, "admission_pack_bytes_per_cycle": 1024.0, "net_cycles_saved": 3.0, "net_cycles_saved_fraction": 0.03},
        {**common, "policy_activation_decode_step": 6, "admission_engine_count": 4, "admission_pack_bytes_per_cycle": 512.0, "net_cycles_saved": 4.0, "net_cycles_saved_fraction": 0.04},
        {**common, "policy_threshold_decode_steps": 17, "policy_activation_decode_step": "not_activated", "admission_engine_count": 1, "admission_pack_bytes_per_cycle": 512.0, "net_cycles_saved": 0.0, "net_cycles_saved_fraction": 0.0},
    ]
    active, fallback = derive_admission_constraints(summaries)
    assert active["minimum_declared_total_pack_bytes_per_cycle"] == 2048.0
    assert active["minimum_capacity_candidates"] == "E1xP2048.0;E2xP1024.0;E4xP512.0"
    assert active["recommended_admission_engine_count"] == 4
    assert fallback["constraint_status"] == "not_applicable_full_kv_fallback"


def test_admission_task_rounds_to_declared_memory_bursts():
    row = {"hot_to_cold_read_bytes": "50", "cold_write_bytes": "34"}
    page = {"metadata_update_bytes": "16"}
    task = admission_task(row, page, bandwidth=64, burst_bytes=64, pack_bytes_per_cycle=100, page_setup_cycles=2, metadata_bytes_per_page=16)
    assert task == {"bytes": 100.0, "transfer": 2.0, "pack": 1.0, "setup": 2.0, "service": 4.0}


def test_shared_admission_engines_use_lpt_makespan():
    tasks = [{"bytes": 0.0, "transfer": 0.0, "pack": 0.0, "setup": 0.0, "service": value} for value in (8.0, 7.0, 1.0)]
    result = schedule_admission(tasks, engine_count=2)
    assert result["service"] == 8.0
    assert result["task_count"] == 3.0


def test_qwen_edge_descriptor_is_internally_consistent(tmp_path):
    descriptor = {
        "schema_version": "kvzap-route-a3-edge-target-1.0",
        "model": {"hf_id": "model", "num_hidden_layers": 1, "num_attention_heads": 4, "num_key_value_heads": 2, "head_dim": 8, "gqa_group_size": 2, "kv_bytes_per_layer_head_token": 32},
        "edge_execution": {"attention_engine_candidates": [4]},
    }
    path = tmp_path / "target.json"
    path.write_text(json.dumps(descriptor), encoding="utf-8")
    assert load_architecture_config(path)["model"]["gqa_group_size"] == 2


def _edge_two_decode_steps():
    source = [
        {"model_call": "1", "phase": "decode", "layer": "0", "kv_head": "0", "cache_tokens_after": "10", "hot_to_cold_read_bytes": "8", "cold_write_bytes": "8"},
        {"model_call": "2", "phase": "decode", "layer": "0", "kv_head": "0", "cache_tokens_after": "11", "hot_to_cold_read_bytes": "8", "cold_write_bytes": "8"},
    ]
    replay = {
        (1, 0, 0): {"layer": "0", "kv_head": "0", "cache_tokens_after": "10", "cold_logical_tokens": "3", "cold_allocated_slots": "4", "metadata_update_bytes": "2"},
        (2, 0, 0): {"layer": "0", "kv_head": "0", "cache_tokens_after": "11", "cold_logical_tokens": "4", "cold_allocated_slots": "4", "metadata_update_bytes": "0"},
    }
    manifest = {"kv_bytes_per_layer_head_token": 8, "sliding_window": 2, "metadata_bytes_per_cold_page": 2, "request_id": "synthetic"}
    return simulate_edge(source, replay, manifest, workload="synthetic", page_tokens=4, bandwidth=8, attention_engines=1, throughput=64, ops_per_token=1, metadata_lookup_bytes=2, metadata_lookup_cycles=1, head_dispatch_cycles=1, scheduler_queue_bytes_per_head=8, admission_engine_count=1, admission_pack_bytes_per_cycle=16, admission_memory_burst_bytes=8, admission_page_setup_cycles=1, deferred_thresholds=[0, 2])


def test_edge_unactivated_deferred_lpt_is_exactly_full_kv():
    _steps, summaries = _edge_two_decode_steps()
    full = next(row for row in summaries if row["baseline"] == "full_kv")
    deferred = next(row for row in summaries if row["baseline"] == "packed_deferred_length_aware_head" and row["policy_threshold_decode_steps"] == 2)
    assert deferred["policy_activation_decode_step"] == "not_activated"
    assert deferred["baseline_cumulative_bytes"] == full["baseline_cumulative_bytes"]
    assert deferred["baseline_cumulative_cycles"] == full["baseline_cumulative_cycles"]


def test_edge_zero_delay_lpt_is_exactly_fixed_packed_lpt():
    _steps, summaries = _edge_two_decode_steps()
    fixed = next(row for row in summaries if row["baseline"] == "packed_length_aware_head")
    deferred = next(row for row in summaries if row["baseline"] == "packed_deferred_length_aware_head" and row["policy_threshold_decode_steps"] == 0)
    assert deferred["baseline_cumulative_bytes"] == fixed["baseline_cumulative_bytes"]
    assert deferred["baseline_cumulative_cycles"] == fixed["baseline_cumulative_cycles"]
