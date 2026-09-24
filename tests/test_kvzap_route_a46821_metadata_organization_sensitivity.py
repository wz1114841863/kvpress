from collections import Counter

from tools.analyze_kvzap_route_a46821_metadata_organization_sensitivity import (
    METADATA_CLASSES,
    bucket_for_event,
    expected_contexts_from_a4682,
    summarize_demands,
)


def _event(**updates):
    event = {"layer": 2, "kv_head": 3, "span_id": (2 << 32) + 9, "source": "private", "primitive": "span_create"}
    event.update(updates)
    return event


def test_a46821_bucket_mapping_is_explicit_deterministic_and_compare_has_control_key():
    span = _event()
    assert bucket_for_event(event=span, mapping="span_identity_striped_v1", bucket_count=8) == bucket_for_event(event=span, mapping="span_identity_striped_v1", bucket_count=8)
    compare = _event(primitive="oldest_source_compare", source=None)
    assert bucket_for_event(event=compare, mapping="span_identity_striped_v1", bucket_count=4) == bucket_for_event(event=compare, mapping="head_source_affine_v1", bucket_count=4)


def test_a46821_same_epoch_shortfall_is_observer_only_and_class_attribution_is_complete():
    demands = {
        ("activation", 0, 0, 0): Counter({"creation_link": 3, "source_compare": 1}),
        ("steady_state_dequeue", 0, 2, 0): Counter({"release_update": 2}),
    }
    result = summarize_demands(demands=demands, service=2, context=("Qwen", "reasoning", 8, "layer_shared_unbounded"), mapping="span_identity_striped_v1", bucket_count=1)
    assert result["all_phases"]["same_epoch_shortfall_logical_units"] == 2
    assert result["all_phases"]["metadata_class_totals"]["creation_link"] == 3
    assert set(result["all_phases"]["metadata_class_totals"]) == set(METADATA_CLASSES)
    assert result["top_hotspots"][0]["logical_checkpoint"] == 0


def test_a46821_expected_coverage_is_derived_from_a4682_not_a_literal_count():
    report = {"anchor_rows": [{"anchor": "Qwen", "workload": "reasoning", "horizon_rows": [{"evaluation_horizon_append_opportunities": 8, "access_epoch_rows": [{"label": "shared"}, {"label": "hierarchical"}]}]}]}
    assert expected_contexts_from_a4682(report) == {("Qwen", "reasoning", 8, "shared"), ("Qwen", "reasoning", 8, "hierarchical")}
