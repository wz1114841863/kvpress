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
from tools.summarize_kvzap_route_a4168_cross_horizon_accounting import A4168_SCHEMA, normalise_accounting
from tools.build_kvzap_route_a4200_observed_resource_contract import A4200_SCHEMA, extract_horizons
from tools.build_kvzap_route_a4201_contract_sensitivity_matrix import A4201_SCHEMA, build_matrix


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
    assert A4168_SCHEMA.endswith("cross-horizon-accounting-report-1.0")


def test_cross_horizon_accounting_rejects_incomplete_source_decisions():
    accounting = {"merge_calls": 1, "expected_attention_evaluations": 1, "by_source": {"hot": {"partial_attention_calls": 1, "empty_source_skip_calls": 0, "total_source_decisions": 1}, "packed": {"partial_attention_calls": 1, "empty_source_skip_calls": 0, "total_source_decisions": 1}, "pending": {"partial_attention_calls": 1, "empty_source_skip_calls": 0, "total_source_decisions": 2}}}
    page = {"selected_layer_count": 1, "selected_kv_head_count": 1, "max_packed_page_count": 1, "max_packed_full_page_count": 1, "max_packed_tail_tokens": 1, "page_witness_count": 1}
    with pytest.raises(ValueError, match="invalid pending"):
        normalise_accounting(generated=1, accounting=accounting, page_guard=page, source={"event_file_sha256": "x", "event_count": 1})


def test_a4200_requires_both_ordered_horizons_and_complete_page_witnesses():
    page = {"selected_layer_count": 36, "selected_kv_head_count": 288, "max_packed_page_count": 13, "max_packed_full_page_count": 12, "max_packed_tail_tokens": 63, "page_witness_count": 108}
    row = {"generated_token_count": 1, "merge_calls": 1, "partial_call_reduction_fraction_from_three_source_unelided": 0.0, "page_tail_coverage": page}
    assert A4200_SCHEMA.endswith("observed-resource-contract-1.0")
    assert set(extract_horizons({"horizons": [{"label": "h16", **row}, {"label": "h32", **row}]})) == {"h16", "h32"}
    with pytest.raises(ValueError, match="exactly h16 and h32"):
        extract_horizons({"horizons": [{"label": "h16", **row}]})


def test_a4201_rejects_a3_sensitivity_without_the_observed_page_point():
    unresolved = [{"name": x} for x in ("pending_FIFO_depth_and_overflow_policy", "page_table_entry_bits_and_allocator_seal_policy", "bank_mapping_burst_gather_format", "merge_state_precision_and_PE_scheduler_interface", "bypass_switch_timing_and_admission_service_rate")]
    contract = {"contract": {"contract_scope": {"page_tokens": 64}, "unresolved_hardware_contract_parameters": unresolved}}
    hybrid = {"assumptions": {"page_tokens": 64, "pending_staging_capacity_tokens_per_layer_points": [0], "pending_overflow_policy": "fallback", "metadata_lookup_bytes_per_page": 16, "metadata_lookup_cycles_per_page": 1, "pending_gather_bytes_per_token_points": [512], "bandwidth_bytes_per_cycle": [512], "hybrid_merge_state_bytes_per_head_points": [16], "hybrid_merge_cycles_per_head_points": [1], "schedulers": ["static"]}}
    edge = {"assumptions": {"page_tokens": [128], "admission_memory_burst_bytes": 64, "admission_pack_bytes_per_cycle_points": [512], "attention_engine_counts": [4], "admission_engine_counts": [1], "admission_page_setup_cycles": 1, "deferred_admission_decode_steps": [0]}}
    with pytest.raises(ValueError, match="lacks A4200"):
        build_matrix(contract=contract, hybrid=hybrid, edge=edge)
    assert A4201_SCHEMA.endswith("contract-sensitivity-matrix-1.0")
