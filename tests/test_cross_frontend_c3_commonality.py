import pytest

from tools.analyze_cross_frontend_c3_commonality import CORE_FIELDS, FRONTENDS, C2_SCHEMA, C3_SCHEMA, field_matrix, invariant_candidates, validate_analysis


def c2_projection(status="observed"):
    return {"core_fields": {field: {"status": status, "value": None, "reason": "unknown" if status == "unknown" else None} for field in CORE_FIELDS}, "realization_extension": "persistent_packed"}


def c2_with_dms_position_unknown():
    projections = {frontend: c2_projection() for frontend in FRONTENDS}
    projections["official_dms_dynamic_resident_slot"]["core_fields"]["position_provenance"] = {"status": "unknown", "value": None, "reason": "not captured"}
    return {"projections": projections}


def test_c3_schema_is_versioned():
    assert C2_SCHEMA == "cross-frontend-c2-realization-adapters-1.0"
    assert C3_SCHEMA == "cross-frontend-c3-commonality-matrix-1.0"


def test_c3_invariant_requires_all_observed():
    matrix = field_matrix(c2_with_dms_position_unknown())
    assert matrix["position_provenance"]["all_observed"] is False
    names = {row["name"] for row in invariant_candidates(matrix)}
    assert "explicit_source_record_identity" in names


def test_c3_rejects_erased_dms_unknown():
    matrix = field_matrix(c2_with_dms_position_unknown())
    matrix["position_provenance"]["all_observed"] = True
    with pytest.raises(ValueError, match="must not erase"):
        validate_analysis(matrix, [], [{"name": "snapkv_generated_decode_and_online_lifecycle"}])
