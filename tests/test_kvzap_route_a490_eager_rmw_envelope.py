from tools.analyze_kvzap_route_a490_eager_rmw_envelope import (
    joint_safe_persistent_references,
    persistent_envelope,
    summarize_temporary_state,
)


def test_persistent_envelope_groups_only_existing_zero_slack_references():
    rows = [
        {"anchor": "a", "workload": "w", "evaluation_horizon_append_opportunities": 8, "organization_label": "o", "layout": "both_colocated_direct_v1", "storage_scope": "per_head", "namespace_policy": "reuse_after_terminal_commit", "generation_bits": 0, "width_slack_bits": 0, "namespace_width_sufficient": True, "modeled_peak_metadata_bits": 11, "field_widths_bits": {"span_slot_bits": 4}, "modeled_peak_storage_object_counts": {"span_owner": 2}},
        {"anchor": "b", "workload": "w", "evaluation_horizon_append_opportunities": 8, "organization_label": "o", "layout": "both_colocated_direct_v1", "storage_scope": "per_head", "namespace_policy": "reuse_after_terminal_commit", "generation_bits": 0, "width_slack_bits": 0, "namespace_width_sufficient": True, "modeled_peak_metadata_bits": 13, "field_widths_bits": {"span_slot_bits": 5}, "modeled_peak_storage_object_counts": {"span_owner": 3}},
    ]
    result = persistent_envelope(rows)
    assert len(result) == 1
    assert result[0]["context_count"] == 2
    assert result[0]["modeled_peak_metadata_bits"]["max"] == 13
    assert result[0]["maximum_field_widths_bits"] == {"span_slot_bits": 5}


def test_joint_safe_reference_is_retained_as_the_cross_context_candidate_bound():
    report = {"static_candidate_rows": [{
        "layout": "both_colocated_direct_v1", "storage_scope": "per_head",
        "namespace_policy": "reuse_after_terminal_commit", "generation_bits": 0,
        "context_count": 168, "cross_context_joint_safe_modeled_metadata_bits": 43975,
        "cross_context_joint_safe_field_widths_bits": {"span_slot_bits": 6},
        "cross_context_joint_safe_modeled_storage_object_counts": {"span_owner": 614},
        "joint_safe_footprint_rule": "max fields and counts across contexts", "physical_entry_not_selected": True,
    }]}
    result = joint_safe_persistent_references(report)
    assert result[0]["context_count"] == 168
    assert result[0]["cross_context_joint_safe_modeled_metadata_bits"] == 43975


def test_temporary_summary_never_implies_multi_group_queue_depth():
    rows = [
        {"atomic_group_touched_modeled_storage_objects": 3, "atomic_group_commit_guarded_modeled_storage_objects": 2, "atomic_group_rmw_exclusion_objects": 1, "atomic_group_read_only_modeled_storage_objects": 1, "atomic_group_modeled_bank_fanout": 2, "atomic_group_cross_bank_commit": True, "operation_mix": {"read": 1, "write": 1, "rmw": 1}},
        {"atomic_group_touched_modeled_storage_objects": 1, "atomic_group_commit_guarded_modeled_storage_objects": 1, "atomic_group_rmw_exclusion_objects": 1, "atomic_group_read_only_modeled_storage_objects": 0, "atomic_group_modeled_bank_fanout": 1, "atomic_group_cross_bank_commit": False, "operation_mix": {"read": 0, "write": 0, "rmw": 1}},
    ]
    result = summarize_temporary_state(rows)
    assert result["per_atomic_group"]["atomic_group_rmw_exclusion_objects"]["max"] == 1
    assert result["cross_bank_atomic_group_count"] == 1
    assert "unselected" in result["temporary_state_scope"]
