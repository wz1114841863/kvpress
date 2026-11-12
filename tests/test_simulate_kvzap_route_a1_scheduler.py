import argparse

import pytest

from kvpress.research.scheduling import (
    PageCostModel,
    build_dynamic_tasks,
    batch_result,
    layer_result,
    make_batches,
    schedule_lpt,
    schedule_static,
    simulate_workloads,
)
from tools.simulate_kvzap_route_a1_scheduler import PageCostModel as LegacyPageCostModel


def test_historical_entrypoint_reexports_shared_cost_model():
    assert LegacyPageCostModel is PageCostModel


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


def test_workloads_keep_short_batch_and_aggregate_dispatch_and_merge():
    heads = [
        {"trace_id": name, "layer": "0", "kv_head": "0", "page_tokens": "4",
         "hot_slots": "2", "cold_page_count": "1"}
        for name in ("a", "b", "c")
    ]
    args = argparse.Namespace(
        page_tokens=[4], batch_sizes=[2], pe_counts=[2], policies=["dynamic_page"],
        drop_incomplete_batch=False, bandwidth_bytes_per_cycle=8,
        throughput_ops_per_cycle=8, attention_ops_per_kv_token=1,
        metadata_lookup_cycles_per_page=0, head_dispatch_cycles=0,
        dynamic_dispatch_cycles=2, merge_cycles_per_extra_segment=5,
    )
    order, layers, batches, summaries = simulate_workloads(heads, 8, args)
    assert order == ["a", "b", "c"]
    assert [row["batch_size_actual"] for row in batches] == [2, 1]
    assert [row["dispatch_cycles"] for row in batches] == [8, 4]
    assert [row["merge_serial_cycles"] for row in batches] == [10, 5]
    assert len(layers) == 2
    assert summaries[0]["batch_count"] == 2
    assert summaries[0]["request_count"] == 3


@pytest.mark.parametrize("policy", ["static_head", "length_aware_head", "dynamic_page"])
def test_cross_layer_finishes_follow_request_identity_not_schedule_order(policy):
    args = argparse.Namespace(batch_size_requested=2, head_dispatch_cycles=0,
                              dynamic_dispatch_cycles=0, merge_cycles_per_extra_segment=0)
    cost = PageCostModel(1, bandwidth=1, throughput=1, ops_per_token=1, metadata_cycles=0)

    def layer(index, a, b):
        heads = [
            {"trace_id": name, "kv_head": 0, "owner": owner, "useful": size,
             "hot_slots": size, "pages": 0}
            for owner, (name, size) in enumerate((("a", a), ("b", b)))
        ]
        return layer_result("batch", ["a", "b"], 4, 2, index, policy, heads, cost, args)

    layers = [layer(0, 1, 9), layer(1, 9, 1)]
    assert layers[0]["_request_finish"] == [1, 9]
    assert layers[1]["_request_finish"] == [9, 1]
    result = batch_result(layers)
    assert result["request_local_finish_cycles_p50"] == 10
    assert result["request_local_finish_cycles_p95"] == 10
    assert result["request_local_finish_cycles_cv"] == 0


def test_dynamic_page_includes_zero_work_request_in_batch_order():
    args = argparse.Namespace(batch_size_requested=2, head_dispatch_cycles=0,
                              dynamic_dispatch_cycles=0, merge_cycles_per_extra_segment=0)
    cost = PageCostModel(1, bandwidth=1, throughput=1, ops_per_token=1, metadata_cycles=0)
    heads = [
        {"trace_id": "a", "kv_head": 0, "owner": 0, "useful": 0, "hot_slots": 0, "pages": 0},
        {"trace_id": "b", "kv_head": 0, "owner": 1, "useful": 3, "hot_slots": 3, "pages": 0},
    ]
    row = layer_result("batch", ["a", "b"], 4, 2, 0, "dynamic_page", heads, cost, args)
    assert row["_request_finish"] == [0, 3]
    assert batch_result([row])["request_local_finish_cycles_p95"] == 3
