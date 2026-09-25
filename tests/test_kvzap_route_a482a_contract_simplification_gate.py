from tools.analyze_kvzap_route_a482a_contract_simplification_gate import lower_group, negative_controls


def group(*, read=(), write=(), rmw=(), release=()):
    ref = lambda record_type, identity: {"record_type": record_type, "record_identity": list(identity)}
    return {
        "read_set": [ref(*item) for item in read], "write_set": [ref(*item) for item in write],
        "rmw_set": [ref(*item) for item in rmw], "release_set": [ref(*item) for item in release],
    }


def test_same_record_read_write_expansion_keeps_identity_and_accounts_extra_work():
    frontier = ("frontier_control", (0, 0, "private"))
    span = ("span_descriptor", (0, 0, 7))
    item = group(read=(frontier,), rmw=(frontier, span))
    eager = lower_group(item, "eager_authoritative_rmw_v1")
    dual = lower_group(item, "same_record_read_write_commit_exclusion_v1")
    assert eager["rmw_record_work"] == 2
    assert eager["total_metadata_record_work"] == 2
    assert dual["rmw_record_work"] == 0
    assert dual["read_record_work"] == dual["write_record_work"] == 2
    assert dual["total_metadata_record_work"] == 4
    assert dual["touched_semantic_record_count"] == eager["touched_semantic_record_count"] == 2
    assert dual["same_record_commit_exclusion_obligation_count"] == 2
    assert dual["additional_semantic_record_count"] == 0


def test_release_stays_a_write_and_negative_controls_reject_partial_visibility():
    owner = ("ownership_link", (0, 0, "private", 7))
    result = lower_group(group(release=(owner,)), "same_record_read_write_commit_exclusion_v1")
    assert result["write_record_work"] == 1
    assert result["rmw_record_work"] == 0
    assert result["same_record_commit_exclusion_obligation_count"] == 0
    assert negative_controls()["status"] == "rejected_as_semantically_observable_or_ambiguous"
