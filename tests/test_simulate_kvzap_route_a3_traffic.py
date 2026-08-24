from tools.simulate_kvzap_route_a3_traffic import attention_cycles, layer_cycles, parse_args, policy_activation_step, policy_active, resolve_workloads, simulate, task_cycles


def test_task_cycles_uses_roofline_and_metadata_cost():
    assert task_cycles(4, 2, kv_bytes=8, bandwidth=8, throughput=16, ops_per_token=1, metadata_lookup_bytes=4, metadata_lookup_cycles=1) == 7.0


def test_lpt_recovers_static_head_collision_for_one_layer():
    tasks = [(0, 8.0), (1, 7.0), (2, 1.0)]
    assert layer_cycles(tasks, pe_count=2, policy="static_head", head_dispatch_cycles=0) == 9.0
    assert layer_cycles(tasks, pe_count=2, policy="length_aware_head", head_dispatch_cycles=0) == 8.0


def test_attention_cycles_distinguishes_logical_and_allocated_cold_slots():
    rows = [{"layer": "0", "kv_head": "0", "cache_tokens_after": "10", "sliding_window": "2", "cold_logical_tokens": "3", "cold_allocated_slots": "4", "cold_page_count": "1"}]
    common = dict(page_tokens=4, window=2, kv_bytes=8, bandwidth=8, throughput=64, ops_per_token=1, metadata_lookup_bytes=4, metadata_lookup_cycles=1, pe_count=1, policy="static_head", head_dispatch_cycles=0)
    assert attention_cycles(rows, kind="ideal", **common) == 5.0
    assert attention_cycles(rows, kind="physical", **common) == 7.5


def test_conservative_three_suite_has_the_three_frozen_a2_workloads():
    args = parse_args(["--workload-suite", "conservative_three", "--a1-dir", "unused", "--output-dir", "new-output"])
    assert [(name, lifecycle.name, replay.name) for name, lifecycle, replay in resolve_workloads(args)] == [
        ("retrieval_qasper", "route_a2_longbench_retrieval_01", "route_a2_longbench_retrieval_01_pages"),
        ("reasoning_2wikimqa", "route_a2_longbench_reasoning_01", "route_a2_longbench_reasoning_01_pages"),
        ("longhorizon_gov_report_row109", "route_a2_longhorizon_gov_report_01", "route_a2_longhorizon_gov_report_01_pages"),
    ]


def test_custom_workload_names_must_be_unique_and_aligned():
    args = parse_args(["--lifecycle-dir", "one", "--lifecycle-dir", "two", "--page-replay-dir", "one-pages", "--page-replay-dir", "two-pages", "--workload-name", "same", "--workload-name", "same", "--a1-dir", "unused", "--output-dir", "new-output"])
    try:
        resolve_workloads(args)
    except ValueError as error:
        assert "unique label" in str(error)
    else:
        raise AssertionError("duplicate workload labels must be rejected")


def _two_decode_steps():
    source = [
        {"model_call": "1", "phase": "decode", "layer": "0", "kv_head": "0", "cache_tokens_after": "10", "hot_to_cold_read_bytes": "8", "cold_write_bytes": "8"},
        {"model_call": "2", "phase": "decode", "layer": "0", "kv_head": "0", "cache_tokens_after": "11", "hot_to_cold_read_bytes": "8", "cold_write_bytes": "8"},
    ]
    replay = {
        (1, 0, 0): {"layer": "0", "kv_head": "0", "cache_tokens_after": "10", "cold_logical_tokens": "3", "cold_allocated_slots": "4", "metadata_update_bytes": "2"},
        (2, 0, 0): {"layer": "0", "kv_head": "0", "cache_tokens_after": "11", "cold_logical_tokens": "4", "cold_allocated_slots": "4", "metadata_update_bytes": "0"},
    }
    manifest = {"kv_bytes_per_layer_head_token": 8, "sliding_window": 2, "request_id": "synthetic"}
    return simulate(source, replay, manifest, workload="synthetic", page_tokens=4, bandwidth=8, throughput=64, ops_per_token=1, pe_count=1, metadata_lookup_bytes=2, metadata_lookup_cycles=1, head_dispatch_cycles=0, scheduler_queue_bytes_per_head=0, oracle_min_decode_steps=[0], deferred_admission_decode_steps=[0, 2])


def test_zero_threshold_gates_degenerate_to_fixed_packed_static():
    _steps, summaries = _two_decode_steps()
    fixed = next(row for row in summaries if row["baseline"] == "packed_static_head")
    oracle = next(row for row in summaries if row["baseline"] == "packed_oracle_static_head" and row["policy_threshold_decode_steps"] == 0)
    deferred = next(row for row in summaries if row["baseline"] == "packed_deferred_static_head" and row["policy_threshold_decode_steps"] == 0)
    assert oracle["baseline_cumulative_bytes"] == fixed["baseline_cumulative_bytes"]
    assert oracle["baseline_cumulative_cycles"] == fixed["baseline_cumulative_cycles"]
    assert deferred["baseline_cumulative_bytes"] == fixed["baseline_cumulative_bytes"]
    assert deferred["baseline_cumulative_cycles"] == fixed["baseline_cumulative_cycles"]


def test_unactivated_deferred_gate_falls_back_to_full_kv():
    _steps, summaries = _two_decode_steps()
    full = next(row for row in summaries if row["baseline"] == "full_kv")
    deferred = next(row for row in summaries if row["baseline"] == "packed_deferred_static_head" and row["policy_threshold_decode_steps"] == 2)
    assert deferred["policy_activation_decode_step"] == "not_activated"
    assert deferred["baseline_cumulative_bytes"] == full["baseline_cumulative_bytes"]
    assert deferred["baseline_cumulative_cycles"] == full["baseline_cumulative_cycles"]


def test_policy_activation_has_no_hidden_horizon_prediction():
    assert policy_active("deferred_observed_steps", 2, decode_step=2, decode_steps=100) is False
    assert policy_active("deferred_observed_steps", 2, decode_step=3, decode_steps=3) is True
    assert policy_activation_step("oracle_horizon_gate", 8, decode_steps=5) == "not_activated"
