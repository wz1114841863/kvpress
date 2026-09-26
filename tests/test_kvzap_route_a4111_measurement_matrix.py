import pytest

from tools.validate_kvzap_route_a4111_measurement_matrix import MEASUREMENT_SCHEMA, validate_measurement


def policy_config():
    return {"model_name": "model", "model_revision": "model-rev", "predictor_name": "predictor", "predictor_revision": "predictor-rev", "threshold": -4.0, "window_size": 128, "page_tokens": 64, "admission_budget": 512, "context_repetitions": 12, "max_new_tokens": 8, "seed": 42, "rtol": 1e-4, "atol": 1e-5, "max_executed_dtype_ulps": 16.0, "target_layers": ["all"], "target_kv_head": "all"}


def distribution(value):
    return {"median": value}


def measurement(workload="retrieval"):
    config = {**policy_config(), "preset": workload, "input_jsonl": None}
    groups = []
    generated = []
    for index, path in enumerate(("full_kv_bypass", "same_mask_dense_replay", "same_mask_route_a_external_storage_replay")):
        groups.append({"path": path, "reported_reset_runs": 3, "callback_count_per_reset_run": distribution(1.0), "wall_ms_sum_per_reset_run": distribution(10.0 + index), "cuda_event_ms_sum_per_reset_run": distribution(9.0 + index), "peak_allocated_bytes_max_per_reset_run": distribution(100.0 + index), "peak_reserved_bytes_max_per_reset_run": distribution(200.0 + index)})
        generated.append({"path": path, "reported_reset_runs": 3, "answer_sha256_values": ["a" * 64], "generated_token_ids_sha256_values": ["d" * 64]})
    return {"schema_version": MEASUREMENT_SCHEMA, "status": "complete", "config": config, "request_id": "request", "request_content_hash": "content", "replay_source": {"event_file_sha256": "event"}, "summary": {"raw_path": "a41_raw_repetitions.jsonl", "reset_run_aggregate_groups": groups, "whole_decode_generated_tokens": generated}, "observational_guards": {"paired_mask_mode": "replayed_dense_mask", "full_kv_bypass_zero_route_a_admission": True, "replay_mask_consumption_complete": True, "all_layers_all_kv_heads_external_storage_substituted": True, "persistent_selected_native_cold_absent": True, "required_any_full_multi_tail_packed_coverage": True, "one_timed_region_per_reset_run": True}}


def test_a4111_accepts_complete_three_path_measurement_and_records_trends():
    result = validate_measurement(measurement(), "retrieval", policy_config())
    assert result["same_mask_dense_route_a_token_digest_equal"] is True
    assert result["route_a_vs_dense_median_ratio"]["wall_ms"] > 1.0


def test_a4111_rejects_route_a_dense_token_drift():
    report = measurement()
    report["summary"]["whole_decode_generated_tokens"][2]["generated_token_ids_sha256_values"] = ["x" * 64]
    with pytest.raises(ValueError, match="token digests differ"):
        validate_measurement(report, "retrieval", policy_config())


def test_a4111_rejects_config_change_after_semantics():
    report = measurement()
    report["config"]["admission_budget"] = 1
    with pytest.raises(ValueError, match="configuration differs"):
        validate_measurement(report, "retrieval", policy_config())
