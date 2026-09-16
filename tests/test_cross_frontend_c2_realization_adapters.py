import pytest

from tools.build_cross_frontend_c2_realization_adapters import C1_SCHEMA, C2_SCHEMA, CORE_FIELDS, projected_field, validate_projection


def c1_with_statuses(status="observed"):
    return {"frontend_field_availability": {"kvzap_route_a_persistent_packed": {"fields": {field: {"status": status} for field in CORE_FIELDS}}}}


def projection(c1, status="observed"):
    return {
        "frontend": "kvzap_route_a_persistent_packed",
        "realization_extension": "persistent_packed",
        "core_fields": {field: projected_field(status, {"field": field}, evidence=["test"]) for field in CORE_FIELDS},
    }


def test_c2_schema_and_core_fields_are_versioned():
    assert C1_SCHEMA == "cross-frontend-c1-semantic-descriptor-1.0"
    assert C2_SCHEMA == "cross-frontend-c2-realization-adapters-1.0"
    assert len(CORE_FIELDS) == 8


def test_c2_projection_preserves_c1_statuses():
    c1 = c1_with_statuses()
    validate_projection(c1, projection(c1))


def test_c2_rejects_status_drift():
    c1 = c1_with_statuses()
    candidate = projection(c1)
    candidate["core_fields"]["identity"]["status"] = "derived"
    with pytest.raises(ValueError, match="changed C1 status"):
        validate_projection(c1, candidate)


def test_c2_unknown_field_cannot_carry_value():
    c1 = c1_with_statuses()
    c1["frontend_field_availability"]["kvzap_route_a_persistent_packed"]["fields"]["position_provenance"]["status"] = "unknown"
    candidate = projection(c1)
    candidate["core_fields"]["position_provenance"] = {"status": "unknown", "value": "invented", "reason": "bad", "evidence_sources": ["test"]}
    with pytest.raises(ValueError, match="fabricated"):
        validate_projection(c1, candidate)
