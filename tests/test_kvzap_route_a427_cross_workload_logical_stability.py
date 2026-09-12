import pytest

from tools.run_kvzap_route_a427_cross_workload_logical_stability import (
    A427_SCHEMA,
    child_command,
    compare,
    observed_source_decode_horizon,
    source_combination_summary,
    validate_semantic_source_contract,
    verify_source_coverage,
)


def event(sequence, active):
    return {
        "logical_event_sequence": sequence, "layer": 0, "kv_head": 0, "query_head": 0,
        "cache_position": 128 + sequence, "merge_after_source_decisions": True,
        "source_decisions": [
            {"source": source, "outcome": "partial" if source in active else "skip", "record_count": 1 if source in active else 0}
            for source in ("hot", "pending", "packed")
        ],
    }


def artifact(events):
    scope = {
        "model_name": "Qwen/Qwen3-8B", "model_revision": "model", "predictor_name": "predictor",
        "predictor_revision": "revision", "threshold": -4.0, "window_size": 128, "page_tokens": 64,
        "admission_budget": 512, "max_new_tokens": 32, "target_layers": ["all"], "target_kv_head": "all",
    }
    return {"manifest": {"config": scope}, "summary": source_combination_summary(events)}


def test_a427_child_command_and_exact_event_rates():
    assert A427_SCHEMA.endswith("cross-workload-logical-stability-1.0")
    assert child_command(script="tool.py", args=["--x", "1"])[1:] == ["tool.py", "--x", "1"]
    summary = source_combination_summary([event(0, {"hot"}), event(1, {"hot", "packed"})])
    assert summary["fan_in_counts"] == {"1_active_sources": 1, "2_active_sources": 1}
    assert summary["source_outcome_counts"]["packed"] == {"partial": 1, "skip": 1}


def test_a427_compares_without_declaring_stability():
    reference = artifact([event(0, {"hot"}), event(1, {"hot", "packed"})])
    candidate = artifact([event(0, {"hot", "packed"}), event(1, {"hot", "pending", "packed"})])
    report = compare(reference, candidate)
    assert report["partial_source_fraction_deltas"]["pending"]["candidate_minus_reference_partial_fraction"] == 0.5
    assert "no stability threshold" in report["interpretation"]
    candidate["manifest"]["config"]["page_tokens"] = 32
    with pytest.raises(ValueError, match="non-horizon policy scopes differ"):
        compare(reference, candidate)


def test_a427_requires_exact_all_layer_kv_head_source_coverage():
    manifest = {"replay_event_coverage": {"layer_count": 36, "layers": [
        {"layer": layer, "expected_kv_heads": list(range(8)), "observed_kv_heads": list(range(8)),
         "missing_kv_heads": [], "unexpected_kv_heads": []}
        for layer in range(36)
    ]}}
    verify_source_coverage(manifest)
    manifest["replay_event_coverage"]["layers"][0]["missing_kv_heads"] = [7]
    with pytest.raises(ValueError, match="exact KV-head"):
        verify_source_coverage(manifest)


def test_a427_source_bounded_horizon_and_horizon_normalized_comparison():
    source = {"policy_decode_call_count_by_layer": {str(layer): 8 for layer in range(36)}}
    assert observed_source_decode_horizon(source) == 8
    reference = artifact([event(0, {"hot"}), event(1, {"hot", "packed"})])
    candidate = artifact([event(0, {"hot", "packed"}), event(1, {"hot", "packed"})])
    candidate["manifest"]["config"]["max_new_tokens"] = 8
    report = compare(reference, candidate)
    assert report["declared_effective_horizons"] == {"reference_max_new_tokens": 32, "candidate_max_new_tokens": 8}
    source["policy_decode_call_count_by_layer"]["35"] = 7
    with pytest.raises(ValueError, match="inconsistent"):
        observed_source_decode_horizon(source)


def test_a427_semantic_source_keeps_declared_cap_separate_from_policy_calls():
    # A multi-token question may execute only max_new_tokens - 1 q_len=1
    # forwards; early EOS can shorten it further. This wrapper must leave the
    # actual consumption proof to the downstream replay-complete gates.
    source = {
        "config": {"max_new_tokens": 8},
        "policy_decode_call_count_by_layer": {str(layer): 7 for layer in range(36)},
    }
    assert validate_semantic_source_contract(source, declared_max_new_tokens=8) == 7
    with pytest.raises(ValueError, match="max-new-tokens differs"):
        validate_semantic_source_contract(source, declared_max_new_tokens=7)
