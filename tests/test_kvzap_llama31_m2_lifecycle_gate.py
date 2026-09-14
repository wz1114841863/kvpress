import json

import pytest

from tools.run_kvzap_llama31_m1_semantic_gate import M1_SCHEMA
from tools.run_kvzap_llama31_m2_lifecycle_gate import M2_SCHEMA, page_witness, read_completed_m1
from tools.validate_kvzap_llama31_m0_provenance import DEFAULT_MODEL_REPO, DEFAULT_MODEL_REVISION, OFFICIAL_PREDICTOR_REPO


def m1_report(**updates):
    report = {
        "schema_version": M1_SCHEMA,
        "status": "complete",
        "config": {"model_name": DEFAULT_MODEL_REPO, "model_revision": DEFAULT_MODEL_REVISION, "predictor_repo_id_override": OFFICIAL_PREDICTOR_REPO, "threshold": -7.0, "window_size": 128, "page_tokens": 64, "predictor_model_type": "linear", "predictor_revision": "b" * 40, "target_layers": "all", "target_kv_heads": "all"},
        "m0_provenance": {"manifest_sha256": "a" * 64},
        "predictor_snapshot": {"repo_id": OFFICIAL_PREDICTOR_REPO},
        "observational_guards": {"m0_complete_explicit_override_bound": True, "all_32_layers_and_all_8_kv_heads_selected": True, "all_selected_groups_have_policy_comparisons": True, "same_mask_dense_events_replayed_exactly_once_by_route_a": True, "same_mask_fp32_and_executed_dtype_guards_executed": True, "route_a_hot_service_observed": True},
    }
    report.update(updates)
    return report


def test_m2_requires_m1_bound_to_supplied_m0(tmp_path):
    path = tmp_path / "m1.json"
    path.write_text(json.dumps(m1_report()))
    assert read_completed_m1(path, m0_sha256="a" * 64)["status"] == "complete"
    with pytest.raises(ValueError, match="hash-bind"):
        read_completed_m1(path, m0_sha256="c" * 64)


def test_page_witness_requires_full_multi_tail_state():
    coverage = {"layers": [{"layer": 0, "heads": [{"kv_head": 0, "ever_sealed_packed_page": True, "ever_multi_page_packed": True, "max_packed_tail_tokens": 3}, {"kv_head": 1, "ever_sealed_packed_page": True, "ever_multi_page_packed": False, "max_packed_tail_tokens": 3}]}]}
    assert page_witness(coverage) == {"requires_one_full_multi_tail_witness": True, "covered": True, "witnesses": [{"layer": 0, "kv_head": 0}]}


def test_page_witness_does_not_infer_tail_from_full_pages():
    coverage = {"layers": [{"layer": 0, "heads": [{"kv_head": 0, "ever_sealed_packed_page": True, "ever_multi_page_packed": True, "max_packed_tail_tokens": 0}]}]}
    assert page_witness(coverage)["covered"] is False


def test_m2_schema_is_versioned():
    assert M2_SCHEMA == "kvzap-llama31-m2-lifecycle-gate-1.0"
