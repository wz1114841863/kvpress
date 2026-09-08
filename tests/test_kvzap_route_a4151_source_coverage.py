import pytest
import json

from tools.run_kvzap_route_a4151_guard_elided_execution_semantic_gate import validate_replay_event_coverage
from tools.run_kvzap_route_a4154_empty_source_elision_semantic_gate import validate_cross_workload_route_certificate
from tools.run_kvzap_route_a4155_empty_source_elision_paired_measurement import validate_cross_workload_a4154_coverage
from tools.run_kvzap_route_a4162_cross_workload_three_path_measurement import PATHS, ROUTE_ELIDED_PATH
from tools.run_kvzap_route_a4163_cross_workload_three_path_profiler import REQUIRED_A4162_GUARDS
from tools.summarize_kvzap_route_a4164_component_accounting import build_report
from tools.run_kvzap_route_a4165_long_horizon_semantic_pipeline import A4165_SCHEMA
from tools.run_kvzap_route_a4166_long_horizon_three_path_measurement import A4166_SCHEMA
from tools.run_kvzap_route_a4167_long_horizon_three_path_profiler import A4167_SCHEMA


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


def test_paired_measurement_requires_a4154_provenance_relay():
    certificate = {
        "observational_guards": {"required_cross_workload_source_coverage_verified": True},
        "replay_source": {
            "event_file_sha256": "event-sha",
            "event_coverage": {"all_layers_exact_all_kv_heads": True, "layer_count": 36, "event_count": 271008},
            "certificate_event_coverage": {"required_by_certificate": True, "layer_count": 36, "event_count": 271008},
        },
    }
    assert validate_cross_workload_a4154_coverage(certificate, expected_event_sha256="event-sha") == {"all_layers_exact_all_kv_heads": True, "layer_count": 36, "event_count": 271008}
    with pytest.raises(ValueError, match="does not match"):
        validate_cross_workload_a4154_coverage(certificate, expected_event_sha256="other")


def test_three_path_measurement_declares_distinct_controls():
    assert PATHS == ("full_kv_bypass", "same_mask_dense_replay", ROUTE_ELIDED_PATH)
    assert ROUTE_ELIDED_PATH not in PATHS[:2]


def test_three_path_profiler_requires_the_completed_three_path_guards():
    assert "a4154_empty_source_elision_semantics_certified" in REQUIRED_A4162_GUARDS
    assert "full_kv_bypass_zero_route_a_admission_each_reset_run" in REQUIRED_A4162_GUARDS


def test_component_accounting_rejects_mismatched_replay_sources():
    with pytest.raises(ValueError, match="replay sources differ"):
        build_report(paired={"replay_source": {"event_file_sha256": "a", "event_count": 1}}, three_path={"replay_source": {"event_file_sha256": "b", "event_count": 1}}, profiler={"replay_source": {"event_file_sha256": "a", "event_count": 1}}, profiler_summary={})


def test_long_horizon_pipeline_schema_is_explicit():
    assert A4165_SCHEMA.endswith("semantic-pipeline-1.0")
    assert A4166_SCHEMA.endswith("three-path-measurement-1.0")
    assert A4167_SCHEMA.endswith("three-path-profiler-1.0")
