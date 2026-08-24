import argparse

from tools.simulate_kvzap_route_a1_scheduler import (
    PageCostModel,
    build_dynamic_tasks,
    layer_result,
    make_batches,
    schedule_lpt,
    schedule_static,
)


def test_length_aware_lpt_recovers_static_head_imbalance():
    tasks = [
        {"trace_id": "r0", "kv_head": 0, "owner": 0, "useful": 8.0},
        {"trace_id": "r1", "kv_head": 0, "owner": 0, "useful": 1.0},
        {"trace_id": "r0", "kv_head": 1, "owner": 1, "useful": 7.0},
    ]
    static, _, _, _ = schedule_static(tasks, pe_count=2)
    lpt, _, _, _ = schedule_lpt(tasks, pe_count=2, dispatch_cycles=0.0)
    assert max(static) == 9.0
    assert max(lpt) == 8.0


def test_dynamic_pages_count_merge_segments_and_dispatch():
    cost = PageCostModel(8, bandwidth=8, throughput=8, ops_per_token=1, metadata_cycles=0)
    heads = [{"trace_id": "r0", "kv_head": 0, "owner": 0, "useful": 0.0, "hot_slots": 2, "pages": 2}]
    tasks, extra_segments = build_dynamic_tasks(heads, page_tokens=4, cost=cost)
    assert len(tasks) == 3  # one hot segment plus two cold pages
    assert extra_segments == 2.0


def test_layer_result_accounts_dynamic_dispatch_and_merge():
    args = argparse.Namespace(
        batch_size_requested=1,
        head_dispatch_cycles=0.0,
        dynamic_dispatch_cycles=2.0,
        merge_cycles_per_extra_segment=5.0,
    )
    cost = PageCostModel(8, bandwidth=8, throughput=8, ops_per_token=1, metadata_cycles=0)
    heads = [{"trace_id": "r0", "kv_head": 0, "owner": 0, "useful": 0.0, "hot_slots": 2, "pages": 2}]
    row = layer_result("b0", ["r0"], 4, 1, 0, "dynamic_page", heads, cost, args)
    assert row["dynamic_task_count"] == 3
    assert row["dispatch_cycles"] == 6.0
    assert row["merge_serial_cycles"] == 10.0
    assert row["modeled_layer_cycles"] == row["pe_makespan_cycles"] + 10.0


def test_sequential_batches_keep_or_explicitly_drop_short_tail():
    ids = ["r0", "r1", "r2", "r3", "r4"]
    assert make_batches(ids, 2, drop_incomplete=False) == [["r0", "r1"], ["r2", "r3"], ["r4"]]
    assert make_batches(ids, 2, drop_incomplete=True) == [["r0", "r1"], ["r2", "r3"]]
