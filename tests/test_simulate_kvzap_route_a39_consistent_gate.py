from tools.simulate_kvzap_route_a39_consistent_gate import total_with_continued_admission


def test_continue_admission_charges_identical_admission_after_both_paths():
    row = {
        "full_layer_bytes": "100",
        "hybrid_layer_bytes": "60",
        "full_layer_cycle_proxy": "20",
        "hybrid_layer_cycle_proxy": "12",
        "admission_bytes": "40",
    }
    assert total_with_continued_admission(row, "full_kv", admission_bandwidth=20) == (140.0, 22.0)
    assert total_with_continued_admission(row, "hybrid", admission_bandwidth=20) == (100.0, 14.0)
