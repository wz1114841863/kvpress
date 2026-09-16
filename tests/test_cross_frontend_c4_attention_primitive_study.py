import pytest

from tools.build_cross_frontend_c4_attention_primitive_study import C2_SCHEMA, C3_SCHEMA, C4_SCHEMA, validate_reports


def reports():
    return {
        "kvzap_route_a_persistent_packed": {"source_cardinality": {"minimum": 1, "maximum": 3}, "source_traversal": {"order": ["hot", "pending", "packed"]}, "semantic_comparator": {"accepted_comparator": "dense"}},
        "snapkv_one_shot_packed": {"source_cardinality": {"minimum": 1, "maximum": 1}, "source_traversal": {"order": "position"}, "semantic_comparator": {"accepted_comparator": "prefill"}},
        "official_dms_dynamic_resident_slot": {"source_cardinality": {"minimum": 1, "maximum": 1}, "source_traversal": {"order": "native", "arrival_order_substitution": "forbidden"}, "semantic_comparator": {"accepted_comparator": "native replay"}},
    }


def c3():
    return {"unresolved_boundaries": [{"name": "universal_multi_source_composition"}]}


def test_c4_schema_is_versioned():
    assert C2_SCHEMA == "cross-frontend-c2-realization-adapters-1.0"
    assert C3_SCHEMA == "cross-frontend-c3-commonality-matrix-1.0"
    assert C4_SCHEMA == "cross-frontend-c4-attention-primitive-study-1.0"


def test_c4_accepts_optional_kvzap_and_single_source_others():
    validate_reports(reports(), c3())


def test_c4_rejects_forced_dms_multi_source():
    candidate = reports()
    candidate["official_dms_dynamic_resident_slot"]["source_cardinality"]["maximum"] = 2
    with pytest.raises(ValueError, match="must not require multi-source"):
        validate_reports(candidate, c3())


def test_c4_rejects_dms_arrival_order_substitution():
    candidate = reports()
    candidate["official_dms_dynamic_resident_slot"]["source_traversal"]["arrival_order_substitution"] = "allowed"
    with pytest.raises(ValueError, match="native-order"):
        validate_reports(candidate, c3())
