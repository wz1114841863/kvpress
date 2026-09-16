import pytest
from pathlib import Path

from tools.archive_cross_frontend_c0_evidence_index import C0_SCHEMA, require_archive_binding, require_guard_values, require_snapkv_boundary


def test_c0_schema_is_versioned():
    assert C0_SCHEMA == "cross-frontend-c0-evidence-index-1.0"


def test_c0_archive_binding_requires_path_and_hash(tmp_path: Path):
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}", encoding="utf-8")
    require_archive_binding(f"{artifact}\nabc", artifact_path=artifact, digest="abc", label="test")
    with pytest.raises(ValueError, match="does not bind"):
        require_archive_binding(str(artifact), artifact_path=artifact, digest="abc", label="test")


def test_c0_guard_validation_rejects_boundary_drift():
    value = {"observational_guards": {"must": True, "must_not": False}}
    assert require_guard_values(value, label="test", true_names=("must",), false_names=("must_not",)) == {"must": True, "must_not": False}
    with pytest.raises(ValueError, match="guard mismatch"):
        require_guard_values({"observational_guards": {"must": False}}, label="test", true_names=("must",))


def test_c0_snapkv_boundary_preserves_decode_unknown():
    value = {"descriptor": {"eligibility": {"bounded_prefill_same_mask_semantic_probe": True, "static_canonical_route_a_mapping": True, "decode_lifecycle_or_pending_contract": False, "native_snapkv_cache_or_decode_semantics": False, "physical_resource_or_hardware_contract": False, "scheduler_or_backpressure_contract": False}, "field_statuses": [{"name": "generated_token_decision_and_decode_continuation", "status": "unavailable", "value": None}]}}
    assert require_snapkv_boundary(value)["decode_lifecycle_or_pending_contract"] is False
    value["descriptor"]["field_statuses"][0]["value"] = 0
    with pytest.raises(ValueError, match="unavailable"):
        require_snapkv_boundary(value)
