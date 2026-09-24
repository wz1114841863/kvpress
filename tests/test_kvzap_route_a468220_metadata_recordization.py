from tools.analyze_kvzap_route_a468220_metadata_recordization import merge_compatible, primitive_to_record


def _event(primitive, **extra):
    event = {"anchor": "qwen3_8b", "workload": "reasoning", "evaluation_horizon_append_opportunities": 8, "organization_label": "shared", "phase": "steady_state_dequeue", "logical_checkpoint": 2, "layer": 1, "kv_head": 2, "source": "private", "span_id": 9, "birth_opportunity": 0, "within_head_sequence_start": 0, "primitive": primitive}
    event.update(extra)
    return event


def test_a468220_minimal_record_contract_maps_every_declared_primitive():
    assert primitive_to_record(_event("source_head_metadata_read"))["record_type"] == "frontier_control"
    assert primitive_to_record(_event("oldest_source_compare", source=None))["record_type"] == "selection_control"
    assert primitive_to_record(_event("span_create"))["record_type"] == "span_descriptor"
    assert primitive_to_record(_event("ownership_link"))["record_type"] == "ownership_link"


def test_a468220_strict_merge_accepts_only_adjacent_equivalent_span_rmw_pair():
    first = primitive_to_record(_event("span_partial_dequeue"))
    second = primitive_to_record(_event("span_head_remaining_update"))
    assert merge_compatible(first, second)
    assert not merge_compatible(first, primitive_to_record(_event("span_head_remaining_update", birth_opportunity=1)))
    assert not merge_compatible(first, primitive_to_record(_event("source_head_update")))
