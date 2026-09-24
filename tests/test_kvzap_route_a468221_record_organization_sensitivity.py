from tools.analyze_kvzap_route_a468221_record_organization_sensitivity import bucket_for_record, contiguous_run, curve_weight


def _op(**updates):
    op = {"record_type": "span_descriptor", "record_identity": [1, 2, 9], "layer": 1, "kv_head": 2, "source": "private", "conservative_record_op_count": 2, "strict_same_record_merged_op_count": 1}
    op.update(updates)
    return op


def test_a468221_mapping_is_deterministic_and_separate_from_curve_weight():
    op = _op()
    assert bucket_for_record(op, "all_record_striped_v1", 8) == bucket_for_record(op, "all_record_striped_v1", 8)
    assert curve_weight(op, "conservative") == 2
    assert curve_weight(op, "strict_same_record") == 1


def test_a468221_contiguous_runs_use_logical_checkpoint_stride_per_phase():
    assert contiguous_run([1, 3, 5, 9], "steady_state_append") == 3
    assert contiguous_run([0], "activation") == 1
