import pytest
import json

from tools.run_kvzap_route_a4151_guard_elided_execution_semantic_gate import validate_replay_event_coverage
from tools.run_kvzap_route_a4154_empty_source_elision_semantic_gate import validate_cross_workload_route_certificate


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


def test_elision_gate_requires_the_a4151_certificate_to_bind_current_source_coverage(tmp_path):
    path = tmp_path / "certificate.json"
    path.write_text(json.dumps({"observational_guards": {"required_replay_event_coverage_verified": True}, "replay_source": {"event_coverage": {"all_layers_exact_all_kv_heads": True, "layer_count": 36, "event_count": 271008}}}))
    assert validate_cross_workload_route_certificate(path=path, expected_event_count=271008) == {"required_by_certificate": True, "layer_count": 36, "event_count": 271008}
    with pytest.raises(ValueError, match="differs"):
        validate_cross_workload_route_certificate(path=path, expected_event_count=1)
