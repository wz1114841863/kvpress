import json

import pytest

from tools.run_kvzap_llama31_m1_semantic_gate import (
    EXPECTED_STRUCTURE,
    M0_SCHEMA,
    assert_all_layer_head_coverage,
    read_completed_m0,
    source_coverage,
)
from tools.validate_kvzap_llama31_m0_provenance import (
    DEFAULT_MODEL_REPO,
    DEFAULT_MODEL_REVISION,
    OFFICIAL_PREDICTOR_REPO,
)


def m0_report(**updates):
    value = {
        "schema_version": M0_SCHEMA,
        "status": "complete",
        "config": {
            "model_repo_id": DEFAULT_MODEL_REPO,
            "model_revision": DEFAULT_MODEL_REVISION,
            "predictor_repo_id": OFFICIAL_PREDICTOR_REPO,
            "predictor_repo_id_override": OFFICIAL_PREDICTOR_REPO,
            "predictor_revision_resolved": "a" * 40,
        },
        "adapter_contract": {
            "explicit_nondefault_override_bound": True,
            "kvzap_press_model_type": "linear",
            "threshold_for_later_M1": -7.0,
            "hot_window_tokens_for_later_M1": 128,
        },
        "base_model_structure": EXPECTED_STRUCTURE,
        "observational_guards": {
            "fixed_base_snapshot_present": True,
            "declared_safetensors_shards_present": True,
            "llama_structure_matches_expected": True,
            "official_predictor_linear_dimensions_match_base_structure": True,
            "direct_derivation_or_explicit_override_bound": True,
        },
    }
    value.update(updates)
    return value


def test_completed_explicit_override_m0_is_accepted(tmp_path):
    path = tmp_path / "m0.json"
    path.write_text(json.dumps(m0_report()))
    assert read_completed_m0(path)["config"]["predictor_revision_resolved"] == "a" * 40


def test_m1_rejects_m0_without_explicit_override(tmp_path):
    report = m0_report()
    report["adapter_contract"]["explicit_nondefault_override_bound"] = False
    path = tmp_path / "m0.json"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="explicit predictor override"):
        read_completed_m0(path)


def test_all_layer_head_coverage_requires_every_selected_head():
    coverage = {
        "layers": [
            {
                "layer": 0,
                "selected_kv_heads": [0, 1],
                "heads": [
                    {"kv_head": 0, "comparison_count": 1},
                    {"kv_head": 1, "comparison_count": 1},
                ],
            }
        ]
    }
    assert_all_layer_head_coverage(coverage, expected_layers=1, expected_kv_heads=2, label="test")
    coverage["layers"][0]["heads"][1]["comparison_count"] = 0
    with pytest.raises(AssertionError, match="without a policy comparison"):
        assert_all_layer_head_coverage(coverage, expected_layers=1, expected_kv_heads=2, label="test")


def test_source_coverage_does_not_infer_absent_sources():
    assert source_coverage([{"hot_tokens": 128, "pending_tokens": 0, "packed_tokens": 5}]) == {
        "hot_observed": True,
        "pending_observed": False,
        "packed_observed": True,
    }
