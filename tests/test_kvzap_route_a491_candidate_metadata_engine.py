from types import SimpleNamespace
from tools.simulate_kvzap_route_a491_candidate_metadata_engine import duration, replay, entry_sufficiency

def test_rmw_duration_uses_declared_lanes():
    tx=SimpleNamespace(demands={(0,"rmw"):2}, banks=frozenset({0}))
    assert duration(tx, {"read_ports":1,"write_ports":1,"rmw_lanes":1}) == 4
    assert duration(tx, {"read_ports":2,"write_ports":2,"rmw_lanes":2}) == 2

def test_replay_preserves_predecessor_before_commit():
    a=SimpleNamespace(index=0, arrival_ordinal=0, predecessors=frozenset(), demands={(0,"write"):1}, banks=frozenset({0}))
    b=SimpleNamespace(index=1, arrival_ordinal=0, predecessors=frozenset({0}), demands={(0,"rmw"):1}, banks=frozenset({0}))
    result=replay([a,b], [("x",0)], {"banks":1,"read_ports":1,"write_ports":1,"rmw_lanes":1,"queue_groups_per_bank":8,"commit_slots":0}, 16)
    assert result["completed"] == 2 and result["drained_within_declared_bound"]

def test_joint_safe_fields_are_word_padded_without_loss():
    report={"static_candidate_rows":[{"layout":"both_colocated_direct_v1","storage_scope":"per_head","namespace_policy":"reuse_after_terminal_commit","generation_bits":0,"context_count":1,"cross_context_joint_safe_field_widths_bits":{"valid_bit":1,"source_bit":1,"span_slot_bits":2,"span_generation_bits":0,"birth_bits":2,"sequence_bits":2,"scope_layer_tag_bits":1,"scope_head_tag_bits":1,"remaining_count_bits":2,"selection_epoch_bits":2},"cross_context_joint_safe_modeled_storage_object_counts":{"head_control":1,"span_owner":1},"cross_context_joint_safe_modeled_metadata_bits":46}]}
    result=entry_sufficiency(report)
    assert result["candidate_entry_width_bits"]["head_control"] % 64 == 0
