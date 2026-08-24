from tools.simulate_kvzap_route_a3_traffic import attention_cycles, layer_cycles, parse_args, resolve_workloads, task_cycles


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
