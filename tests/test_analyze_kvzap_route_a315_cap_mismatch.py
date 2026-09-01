from tools.analyze_kvzap_route_a315_cap_mismatch import summarize


def manifest(cap: int, decode_calls: int, answer: str = "same"):
    return {
        "request_id": "request-1", "model": "model", "model_revision": "model-rev", "predictor_checkpoint": "predictor", "predictor_revision": "predictor-rev", "threshold": -4.0, "sliding_window": 128, "page_tokens": 64, "kv_bytes_per_layer_head_token": 512, "metadata_bytes_per_cold_page": 16,
        "config": {"request_id": "request-1", "request_content_hash": "content", "model": "model", "model_revision": "model-rev", "predictor": "predictor", "predictor_revision": "predictor-rev", "threshold": -4.0, "sliding_window": 128, "page_tokens": 64, "kv_bytes_per_token": 512, "metadata_bytes_per_page": 16, "seed": 42, "max_new_tokens": cap},
        "decode_lifecycle_observation": {"decode_model_call_count": decode_calls}, "trace_equivalence": {"normal_observer_record_answer_sha256": answer},
    }


def test_high_cap_natural_early_stop_confirms_cap_mismatch_counterexample():
    row = summarize(manifest(32, 17), manifest(128, 17))
    assert row["high_cap_naturally_stopped_before_cap"] is True
    assert row["same_answer_sha256"] is True
    assert row["counterexample_confirmed"] is True
    assert row["high_cap_unused_decode_budget"] == 111


def test_consumed_cap_is_a_valid_negative_result_not_a_counterexample():
    row = summarize(manifest(32, 17), manifest(128, 128))
    assert row["high_cap_naturally_stopped_before_cap"] is False
    assert row["counterexample_confirmed"] is False


def test_different_input_configuration_is_rejected():
    high = manifest(128, 17); high["config"]["request_content_hash"] = "different"
    try:
        summarize(manifest(32, 17), high)
    except ValueError as error:
        assert "request_content_hash" in str(error)
    else:
        raise AssertionError("different request content must be rejected")
