from tools.analyze_kvzap_llama31_m41_summarization_ulp_diagnostic import M41_SCHEMA, summarize_route_breaches


def test_m41_schema_is_versioned():
    assert M41_SCHEMA == "kvzap-llama31-m41-summarization-ulp-diagnostic-1.0"


def test_m41_breach_summary_keeps_ulp_and_absolute_context_separate():
    manifest = {
        "outcomes": {
            "pending_budget_one": {"replayed_same_mask_route_a": {"execution_dtype_ulp_breach_summary": {"layers": [{"layer": 2, "samples": [{"max_executed_dtype_ulps": 199.0, "executed_dtype_ulp_limit": 16.0, "max_executed_dtype_ulps_is_infinite": False, "max_fp32_abs_difference": 2.0e-8, "dense_fp32_value_at_max_ulp": 1.0e-10, "route_fp32_value_at_max_ulp": 2.0e-10, "kv_head": 6, "query_head": 26, "cache_position": 927}]}]}}},
            "packed_budget_512": {"replayed_same_mask_route_a": {"execution_dtype_ulp_breach_summary": {"layers": [{"layer": 2, "samples": [{"max_executed_dtype_ulps": 199.0, "executed_dtype_ulp_limit": 16.0, "max_executed_dtype_ulps_is_infinite": False, "max_fp32_abs_difference": 2.0e-8, "dense_fp32_value_at_max_ulp": 1.0e-10, "route_fp32_value_at_max_ulp": 2.0e-10, "kv_head": 6, "query_head": 26, "cache_position": 927}]}]}}},
        }
    }
    summary = summarize_route_breaches(manifest, atol=1.0e-5)
    assert summary["recorded_breach_occurrence_count"] == 2
    assert summary["unique_location_count"] == 1
    assert summary["all_recorded_fp32_maxima_within_declared_atol"] is True
    assert summary["all_sample_values_below_declared_atol_magnitude"] is True
