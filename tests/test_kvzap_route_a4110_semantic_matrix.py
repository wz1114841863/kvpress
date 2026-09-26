import json

import pytest

from tools.validate_kvzap_route_a4110_semantic_matrix import A410_SCHEMA, POLICY_SCHEMA, WORKLOADS, validate_a410, validate_policy_manifest


def a410_report():
    return {
        "schema_version": A410_SCHEMA, "status": "complete",
        "config": {"fixed_execution": "A4.9.2 record-granular only", "candidates": ["ha8_base", "ha8_wide"], "local_capacity_per_bank": 32, "shared_capacity_per_layer": 256, "staging_capacity_per_layer": 512, "queue_reference_word_bits": 64},
        "semantic_guards": {"a492_record_granular_execution_fixed_without_new_variant": True, "ha8_wide_primary_and_ha8_base_control_only": True, "transaction_fifo_ownership_and_single_commit_boundary_unchanged": True, "lossless_credit_only_delays_transactions_without_drop_or_reorder": True, "queue_overflow_reference_and_finite_credit_staging_both_reported": True, "no_model_default_pruning_path_or_hardware_measurement_loaded": True},
    }


def policy_manifest(workload="retrieval"):
    layers = [0, 1]
    heads = [0, 1]
    coverage = {"layers": [{"layer": layer, "selected_kv_heads": heads, "original_mask_sha256": f"mask-{layer}", "original_mask_decision_count": 8, "heads": [{"kv_head": head, "comparison_count": 1, "max_pending_tokens": int(layer == 0 and head == 0)} for head in heads]} for layer in layers]}
    return {
        "schema_version": POLICY_SCHEMA,
        "config": {"preset": workload, "input_jsonl": None, "target_layers": ["all"], "target_kv_head": "all", "with_same_mask_dense_baseline": True, "replay_dense_mask_for_route_a": True, "record_lifecycle_transitions": False, "prefill_maturity_chunk_tokens": 0, "require_pending_nonempty": True, "resolved_target_layers": layers, "model_name": "model", "model_revision": "model-rev", "predictor_name": "predictor", "predictor_revision": "predictor-rev", "threshold": -4.0, "window_size": 128, "page_tokens": 64, "admission_budget": 512, "context_repetitions": 12, "max_new_tokens": 8, "seed": 42, "rtol": 1e-4, "atol": 1e-5, "max_executed_dtype_ulps": 16.0},
        "observational_guards": {"selected_head_original_attention_called_during_policy_decode": False, "route_a_mask_source": "replayed_dense_mask", "replay_mask_consumption_complete": True, "lifecycle_transition_trace_enabled": False, "prefill_micro_event_trace_enabled": False, "dms_press_used": False, "masked_key_indices_created": False, "fake_key_attention_used": False, "model_cache_mutated_by_backend": False},
        "full_kv_bypass_answer_sha256": "f" * 64, "route_a_fast_path_answer_sha256": "r" * 64,
        "policy_coverage": coverage, "policy_decode_call_count_by_layer": {str(layer): 1 for layer in layers}, "comparisons": [{"layer": 0}],
        "same_mask_dense_kvzap": {"pairing_mode": "replayed_dense_mask", "original_mask_digest_matches_route_a": True, "answer_sha256": "d" * 64, "answers_identical_to_full_kv": False, "policy_coverage": coverage, "policy_decode_call_count_by_layer": {str(layer): 1 for layer in layers}, "comparisons": [{"layer": 0}]},
    }


def test_a4110_accepts_fixed_a410_and_complete_trace_off_manifest():
    assert validate_a410(a410_report())["staging_capacity_per_layer"] == 512
    result = validate_policy_manifest(policy_manifest(), "retrieval")
    assert result["selected_kv_head_count"] == 4
    assert set(result["three_path_answer_sha256"]) == {"full_kv_bypass_answer_sha256", "route_a_fast_path_answer_sha256", "same_mask_dense_kvzap_answer_sha256"}


def test_a4110_rejects_trace_on_manifest_before_separate_control_event_phase():
    manifest = policy_manifest()
    manifest["config"]["record_lifecycle_transitions"] = True
    manifest["observational_guards"]["lifecycle_transition_trace_enabled"] = True
    with pytest.raises(ValueError, match="trace-off"):
        validate_policy_manifest(manifest, "retrieval")


def test_a4110_rejects_changed_a410_queue_parameter():
    report = a410_report()
    report["config"]["shared_capacity_per_layer"] = 128
    with pytest.raises(ValueError, match="configuration"):
        validate_a410(report)
