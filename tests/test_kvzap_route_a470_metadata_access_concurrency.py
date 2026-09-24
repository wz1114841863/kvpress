from tools.analyze_kvzap_route_a470_metadata_access_concurrency import EDGE_TYPES, contiguous, dependencies


def _op(record_type, identity, phase='steady_state_dequeue', checkpoint=2, head=0, weight=1):
    return {'record_type': record_type, 'record_identity': identity, 'phase': phase, 'logical_checkpoint': checkpoint, 'layer': 0, 'kv_head': head, 'conservative_record_op_count': weight, 'strict_same_record_merged_op_count': weight}


def test_a470_only_preregistered_edges_and_same_record_are_emitted():
    nodes, edges = dependencies([_op('span_descriptor',[0,0,1]), _op('span_descriptor',[0,0,1])], 'strict_same_record')
    assert set(edges) <= set(EDGE_TYPES)
    assert nodes[1]['edges'] == [('same-record', 0)]


def test_a470_span_lifecycle_and_checkpoint_contiguity_are_explicit():
    nodes, _ = dependencies([_op('span_descriptor',[0,0,1],checkpoint=2), _op('span_descriptor',[0,0,1],checkpoint=4)], 'strict_same_record')
    assert ('span-lifecycle', 0) in nodes[1]['edges']
    assert contiguous([2,4,6,10], 'steady_state_dequeue') == 3


def test_a470_head_control_and_ownership_edges_have_fixed_declared_scopes():
    controls, _ = dependencies([
        _op('frontier_control', [0, 0, 'packed'], head=0),
        _op('selection_control', [0, 0, 'packed'], head=0),
    ], 'conservative')
    assert ('same-head-control', 0) in controls[1]['edges']
    ownership, _ = dependencies([
        _op('ownership_link', [0, 0, 'packed'], checkpoint=2),
        _op('ownership_link', [0, 0, 'packed'], checkpoint=4),
    ], 'conservative')
    assert ('ownership-order', 0) in ownership[1]['edges']
