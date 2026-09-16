import pytest

from tools.build_cross_frontend_c1_semantic_descriptor import C0_SCHEMA, C1_SCHEMA, CORE_FIELD_TYPES, availability_matrix, validate_matrix


def test_c1_schema_and_core_fields_are_versioned():
    assert C0_SCHEMA == "cross-frontend-c0-evidence-index-1.0"
    assert C1_SCHEMA == "cross-frontend-c1-semantic-descriptor-1.0"
    assert set(CORE_FIELD_TYPES) == {"model_topology", "identity", "epoch", "decision", "visibility", "position_provenance", "traversal_order", "attention_binding"}


def test_c1_matrix_is_typed_and_unknowns_are_explained():
    matrix = availability_matrix()
    validate_matrix(matrix)
    assert matrix["snapkv_one_shot_packed"]["fields"]["epoch"]["subfields"]["generated_decode_epoch"]["status"] == "unknown"
    assert matrix["official_dms_dynamic_resident_slot"]["fields"]["position_provenance"]["status"] == "unknown"


def test_c1_rejects_unknown_without_reason():
    matrix = availability_matrix()
    del matrix["official_dms_dynamic_resident_slot"]["fields"]["position_provenance"]["reason"]
    with pytest.raises(ValueError, match="requires a reason"):
        validate_matrix(matrix)


def test_c1_rejects_missing_core_field():
    matrix = availability_matrix()
    del matrix["kvzap_route_a_persistent_packed"]["fields"]["identity"]
    with pytest.raises(ValueError, match="exactly the typed v1 core fields"):
        validate_matrix(matrix)
