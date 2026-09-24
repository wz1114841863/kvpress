from tools.analyze_kvzap_route_a471_metadata_transaction_contract import SemanticReplay, build_groups, negative_controls


def _op(primitive, record_type, access_kind, index, *, source='private', span_id=7, birth=0, sequence=0):
    return {
        'anchor': 'qwen3_8b', 'workload': 'reasoning', 'evaluation_horizon_append_opportunities': 8,
        'organization_label': 'layer_shared_unbounded', 'phase': 'steady_state_dequeue',
        'logical_checkpoint': 2, 'layer': 0, 'kv_head': 0, 'source': source,
        'span_id': span_id, 'birth_opportunity': birth, 'within_head_sequence_start': sequence,
        'record_type': record_type, 'record_identity': [record_type, span_id], 'access_kind': access_kind,
        'primitive_sequence': primitive if isinstance(primitive, list) else [primitive],
    }


def test_a471_groups_terminal_dequeue_with_declared_sets_and_boundary():
    ops = [
        _op('source_head_metadata_read', 'frontier_control', 'read', 0),
        _op(['span_partial_dequeue', 'span_head_remaining_update'], 'span_descriptor', 'rmw', 1),
        _op('span_release', 'span_descriptor', 'release', 2),
        _op('ownership_unlink', 'ownership_link', 'release', 3),
        _op('source_head_update', 'frontier_control', 'rmw', 4),
    ]
    group = build_groups(ops)[0]
    assert group['transaction_type'] == 'dequeue_terminal'
    assert group['member_record_node_count'] == 5
    assert group['commit_linearization_boundary'].startswith('after_selection_span_release')
    assert len(group['read_set']) == 1 and len(group['rmw_set']) == 2
    assert len(group['release_set']) == 2 and group['touched_record_count'] == 3


def test_a471_split_multi_record_negative_controls_are_rejected():
    result = negative_controls()
    assert result['status'] == 'rejected_as_semantically_observable_partial_state'
    assert set(result['failures']) == {'split_admission_create_after_span_write', 'split_terminal_release_after_span_release'}


def test_a471_groups_two_source_selection_without_confusing_read_sources_with_chosen_source():
    ops = [
        _op('source_head_metadata_read', 'frontier_control', 'read', 0, source='private', span_id=7),
        _op('source_head_metadata_read', 'frontier_control', 'read', 1, source='shared', span_id=8),
        _op('oldest_source_compare', 'selection_control', 'read', 2, source=None, span_id=None, birth=None, sequence=None),
        _op(['span_partial_dequeue', 'span_head_remaining_update'], 'span_descriptor', 'rmw', 3, source='private', span_id=7),
        _op('source_head_update', 'frontier_control', 'rmw', 4, source='private', span_id=7),
    ]
    group = build_groups(ops)[0]
    assert group['transaction_type'] == 'dequeue_nonterminal'
    assert group['member_record_node_count'] == 5
    assert group['touched_record_count'] == 4


def test_a471_post_commit_replay_preserves_source_front_and_removes_terminal_span_atomically():
    create_ops = [
        _op('span_create', 'span_descriptor', 'write', 0),
        _op('ownership_link', 'ownership_link', 'write', 1),
    ]
    terminal_ops = [
        _op('source_head_metadata_read', 'frontier_control', 'read', 0),
        _op(['span_partial_dequeue', 'span_head_remaining_update'], 'span_descriptor', 'rmw', 1),
        _op('span_release', 'span_descriptor', 'release', 2),
        _op('ownership_unlink', 'ownership_link', 'release', 3),
        _op('source_head_update', 'frontier_control', 'rmw', 4),
    ]
    state = SemanticReplay()
    state.commit(build_groups(create_ops)[0], create_ops)
    state.commit(build_groups(terminal_ops)[0], terminal_ops)
    assert state.spans == state.owners == {}
