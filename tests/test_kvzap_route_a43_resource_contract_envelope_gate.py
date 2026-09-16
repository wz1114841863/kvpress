import pytest

from tools.build_kvzap_route_a43_resource_contract_envelope_gate import (
    UNRESOLVED_PARAMETERS,
    conditioned_rows,
    resource_rows,
    verify_qwen_provenance,
)


def test_resource_rows_require_complete_unresolved_contract():
    observed = {"contract": {"unresolved_hardware_contract_parameters": [{"name": name, "reason": name} for name in UNRESOLVED_PARAMETERS]}}
    matrix = {"report": {"matrix": [{"parameter": name, "candidate_modeled_range": {}, "next_binding_needed": name} for name in UNRESOLVED_PARAMETERS]}}
    rows = resource_rows(observed, matrix)
    assert [row["parameter"] for row in rows] == list(UNRESOLVED_PARAMETERS)
    assert all(row["status"] == "unresolved_not_selected" for row in rows)


def test_resource_rows_reject_missing_parameter():
    with pytest.raises(ValueError, match="differ"):
        resource_rows({"contract": {"unresolved_hardware_contract_parameters": []}}, {"report": {"matrix": []}})


def _row(anchor, workload):
    return {"model_anchor": anchor, "workload": workload, "actual_policy_decode_calls": 7}


def test_conditioned_rows_require_six_distinct_model_workload_rows():
    rows = [_row("qwen3_8b_kvzap", item) for item in ("retrieval", "reasoning", "summarization")]
    rows += [_row("nous_llama31_8b_kvzap", item) for item in ("retrieval", "reasoning", "summarization")]
    report = {"per_model_fixed_workload_descriptors": {"qwen": rows[:3], "llama": rows[3:]}}
    assert len(conditioned_rows(report)) == 6


def test_conditioned_rows_rejects_pooled_or_duplicate_rows():
    rows = [_row("qwen3_8b_kvzap", "retrieval")] * 6
    report = {"per_model_fixed_workload_descriptors": {"qwen": rows, "llama": []}}
    with pytest.raises(ValueError, match="six distinct"):
        conditioned_rows(report)


def test_qwen_provenance_requires_a4214_to_bind_a4211_and_m6_to_reconcile_it():
    a4211 = {}
    a4214 = {"config": {"a4211": {"sha256": "a4211"}}}
    m6 = {"qwen_core_provenance_reconciliation": {
        "canonical_projection_matches_m3": True,
        "known_reconciled_raw_input_sha256s": ["a4214"],
    }}
    result = verify_qwen_provenance(a4211, a4214, m6, "a4211", "a4214")
    assert result["a4214_sha256_is_m6_reconciled"] is True


def test_qwen_provenance_rejects_unbound_a4211():
    with pytest.raises(ValueError, match="does not bind"):
        verify_qwen_provenance(
            {}, {"config": {"a4211": {"sha256": "different"}}},
            {"qwen_core_provenance_reconciliation": {"canonical_projection_matches_m3": True, "known_reconciled_raw_input_sha256s": ["a4214"]}},
            "a4211", "a4214",
        )
