from tools.analyze_kvzap_route_a4123_metadata_partial_ledger import benefit_rows


def test_benefit_rows_preserve_unamortized_logical_potential_boundary():
    report={"workloads":[
        {"workload":"retrieval","direct_software_observation":{"logical_admission_service_tokens":20,"matured_kept_tokens":20,"matured_dropped_tokens":80,"trace_end_residual_pending_tokens":0}},
        {"workload":"summarization","direct_software_observation":{"logical_admission_service_tokens":10,"matured_kept_tokens":10,"matured_dropped_tokens":90,"trace_end_residual_pending_tokens":0}},
        {"workload":"reasoning","direct_software_observation":{"logical_admission_service_tokens":25,"matured_kept_tokens":25,"matured_dropped_tokens":75,"trace_end_residual_pending_tokens":0}},
    ]}
    rows=benefit_rows(report)
    assert rows[0]["logical_capacity_potential"]["removed_fraction_of_matured_cold_tokens"] == .8
    assert rows[0]["logical_attention_work_potential"]["future_traversal_count_observed"] is None
    assert rows[0]["logical_attention_work_potential"]["realized_attention_operations_or_traffic"] == "not_observed"
