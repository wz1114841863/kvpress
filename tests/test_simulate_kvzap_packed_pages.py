import numpy as np

from tools.simulate_kvzap_packed_pages import PackedKVSimulator, replay_trace


def simulator(page_tokens=4):
    return PackedKVSimulator(page_tokens, kv_bytes_per_token=8, metadata_bytes_per_page=2)


def test_empty_and_full_cold_pages():
    final = np.asarray([[[True, True, True, True, False, False], [False, False, False, False, False, False]]])
    state = simulator().replay(final, np.ones_like(final, dtype=bool), window=2)
    assert state["cold_logical_kept_slots"].tolist() == [[0, 4]]
    assert state["cold_page_count"].tolist() == [[0, 1]]
    assert state["tail_waste_slots"].tolist() == [[0, 0]]
    assert state["tail_page_valid_slots"].tolist() == [[0, 4]]


def test_tail_page_fragmentation():
    final = np.asarray([[[False, False, False, False, False, False, False]]])
    state = simulator().replay(final, np.ones_like(final, dtype=bool), window=2)
    assert state["cold_logical_kept_slots"].item() == 5
    assert state["cold_allocated_slots"].item() == 8
    assert state["tail_waste_slots"].item() == 3
    assert state["tail_page_valid_slots"].item() == 1


def test_hot_window_does_not_enter_cold_pages():
    final = np.asarray([[[False, False, False, False, False, False]]])
    state = simulator().replay(final, np.ones_like(final, dtype=bool), window=2)
    assert state["hot_slots"].item() == 2
    assert state["cold_logical_kept_slots"].item() == 4
    assert state["cold_page_count"].item() == 1


def test_page_size_one_equals_ideal_packed_capacity():
    final = np.asarray([[[False, True, False, False, False, False]]])
    valid = np.ones_like(final, dtype=bool)
    state = simulator(page_tokens=1).replay(final, valid, window=2)
    assert int((state["hot_slots"] + state["cold_allocated_slots"]).sum()) == int(((~final) & valid).sum())
    assert state["tail_waste_slots"].item() == 0


def test_request_summary_matches_head_counts():
    final = np.asarray([[[False, True, False, False, False, False], [True, True, False, False, False, False]]])
    trace = {
        "trace_id": "e0::r0", "manifest": {"sliding_window": 2}, "request": {"request_id": "r0"},
        "final": final, "valid": np.ones_like(final, dtype=bool),
    }
    request, heads = replay_trace(trace, simulator(), {})
    assert request["physical_allocated_slots"] == sum(row["hot_slots"] + row["cold_allocated_slots"] for row in heads)
    assert request["cold_page_count"] == sum(row["cold_page_count"] for row in heads)
    assert request["tail_waste_slots"] == sum(row["tail_waste_slots"] for row in heads)
