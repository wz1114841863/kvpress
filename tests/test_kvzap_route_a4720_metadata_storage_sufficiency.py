from tools.analyze_kvzap_route_a4720_metadata_storage_sufficiency import LAYOUTS, ceil_log2_namespace, normalized_object_key


def test_a4720_namespace_width_makes_reuse_and_reserved_encoding_explicit():
    assert ceil_log2_namespace(7, 1, 0) == 3
    assert ceil_log2_namespace(8, 1, 0) == 4
    assert ceil_log2_namespace(8, 1, 2) == 6


def test_a4720_colocation_retains_two_semantic_records_in_one_modeled_object():
    layout = 'span_owner_colocated_direct_v1'
    span = normalized_object_key(layout, 'span_descriptor', [1, 2, 99], layer=1, head=2)
    owner = normalized_object_key(layout, 'ownership_link', [1, 2, 'private', 99], layer=1, head=2)
    assert span == owner == ('span_owner', (99,))
    assert set(LAYOUTS[layout]['storage_object_classes']['span_owner']) == {'span_descriptor', 'ownership_link'}


def test_a4720_control_colocation_keeps_all_frontier_and_selection_semantics():
    layout = 'control_colocated_direct_v1'
    private = normalized_object_key(layout, 'frontier_control', [1, 2, 'private'], layer=1, head=2)
    shared = normalized_object_key(layout, 'frontier_control', [1, 2, 'shared'], layer=1, head=2)
    selection = normalized_object_key(layout, 'selection_control', [1, 2], layer=1, head=2)
    assert private == shared == selection == ('head_control', (1, 2))
