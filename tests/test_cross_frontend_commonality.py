from tools.analyze_cross_frontend_c3_commonality import CORE_FIELDS, FRONTENDS, analyze_projections


def projections():
    result = {frontend: {"core_fields": {field: {"status": "observed"} for field in CORE_FIELDS},
                         "realization_extension": {}} for frontend in FRONTENDS}
    result["official_dms_dynamic_resident_slot"]["core_fields"]["position_provenance"] = {
        "status": "unknown", "reason": "arrival serial is not an original position"
    }
    return {"projections": result}


def test_common_identity_does_not_erase_frontend_boundaries():
    matrix, invariants, specific, unresolved = analyze_projections(projections())
    assert len(invariants) == 4
    assert len(specific) == 3
    assert not matrix["position_provenance"]["all_observed"]
    assert {row["name"] for row in unresolved} >= {
        "literal_dms_original_position", "snapkv_generated_decode_and_online_lifecycle",
        "shared_physical_or_temporal_resource_contract",
    }


def test_unknown_identity_cannot_become_a_shared_observation():
    data = projections()
    data["projections"]["snapkv_one_shot_packed"]["core_fields"]["identity"]["status"] = "unknown"
    _, invariants, _, _ = analyze_projections(data)
    assert "explicit_source_record_identity" not in {item["name"] for item in invariants}
