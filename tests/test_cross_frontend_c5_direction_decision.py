import pytest

from tools.build_cross_frontend_c5_direction_decision import C5_SCHEMA, decide, validate_decision


def reports():
    return {
        "c3": {
            "frontend_specific_mechanisms": [
                {"frontend": "kvzap_route_a_persistent_packed"},
                {"frontend": "snapkv_one_shot_packed"},
                {"frontend": "official_dms_dynamic_resident_slot"},
            ],
            "unresolved_boundaries": [
                {"name": "literal_dms_original_position"},
                {"name": "snapkv_generated_decode_and_online_lifecycle"},
                {"name": "shared_physical_or_temporal_resource_contract"},
                {"name": "universal_multi_source_composition"},
            ],
        },
        "c4": {"comparison_summary": {"candidate_common_primitive": "frontend-bound ordered variable-length source traversal under each frontend's accepted semantic comparator", "not_established": ["a common cache format", "a common source order", "mandatory multi-source composition", "scheduler/backpressure/temporal resource contract", "allocator/capacity/traffic/timing/hardware interface"]}},
    }


def test_c5_schema_is_versioned():
    assert C5_SCHEMA == "cross-frontend-c5-hardware-direction-decision-1.0"


def test_c5_selects_route_a_only_with_all_boundaries():
    decision = decide(reports())
    assert decision["primary_direction"] == "route_a_persistent_packed_backend"


def test_c5_rejects_missing_common_hardware_boundary():
    candidate = reports()
    candidate["c4"]["comparison_summary"]["not_established"].remove("a common cache format")
    with pytest.raises(ValueError, match="cannot promote"):
        decide(candidate)


def test_c5_rejects_hardware_promotion():
    decision = decide(reports())
    decision["candidate_common_substrate"]["status"] = "selected_hardware"
    with pytest.raises(ValueError, match="must not promote"):
        validate_decision(decision, [{"name": "rtl_authorization", "status": "not_authorized"}])
