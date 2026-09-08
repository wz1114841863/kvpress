import pytest

from tools.run_kvzap_route_a4151_guard_elided_execution_semantic_gate import validate_replay_event_coverage


def source_with_coverage(rows):
    return {"replay_event_coverage": {"layers": rows}}


def test_execution_semantic_gate_binds_exact_collector_layer_head_coverage():
    source = source_with_coverage([
        {"layer": 0, "expected_kv_heads": [0, 1], "observed_kv_heads": [0, 1], "missing_kv_heads": [], "unexpected_kv_heads": [], "event_count": 10},
        {"layer": 1, "expected_kv_heads": [0, 1], "observed_kv_heads": [0, 1], "missing_kv_heads": [], "unexpected_kv_heads": [], "event_count": 12},
    ])
    assert validate_replay_event_coverage(source=source, expected_heads={0: (0, 1), 1: (0, 1)}) == {"layer_count": 2, "all_layers_exact_all_kv_heads": True, "event_count": 22}


def test_execution_semantic_gate_rejects_source_without_exact_head_coverage():
    with pytest.raises(ValueError, match="replay_event_coverage"):
        validate_replay_event_coverage(source={}, expected_heads={0: (0,)})
    source = source_with_coverage([
        {"layer": 0, "expected_kv_heads": [0, 1], "observed_kv_heads": [0], "missing_kv_heads": [1], "unexpected_kv_heads": [], "event_count": 10},
    ])
    with pytest.raises(AssertionError, match="does not bind"):
        validate_replay_event_coverage(source=source, expected_heads={0: (0, 1)})
