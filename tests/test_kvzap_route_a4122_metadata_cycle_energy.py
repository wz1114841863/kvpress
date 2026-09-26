from collections import Counter

from tools.simulate_kvzap_route_a4122_metadata_cycle_energy import access_plan, can_use, commit_ready_groups, duration, resource_capacities
from tools.simulate_kvzap_route_a492_record_granular_engine import MicroOp


def member(kind, operation="read"):
    return MicroOp(transaction_index=0, object_key=(kind, (0,)), bank=3, operation=operation)


def test_m1_unifies_both_metadata_classes_on_one_explicit_1rw_slot():
    resources, energy = access_plan("M1_banked_sram_pipelined_rmw", member("head_control", "rmw"), Counter())
    assert resources == ((3, "unified_1rw"),)
    assert energy["persistent_head_control_and_span_owner"] == Counter(read=1, write=1)
    assert duration("rmw") == 2


def test_m2_mirrors_head_writes_but_not_reads_or_span_owner_accesses():
    resources, energy = access_plan("M2_replicated_or_duplicated_control_storage", member("head_control", "write"), Counter())
    assert set(resources) == {(3, "head_replica_0"), (3, "head_replica_1")}
    assert energy["replicated_head_control"] == Counter(write=2)
    resources, energy = access_plan("M2_replicated_or_duplicated_control_storage", member("span_owner", "read"), Counter())
    assert resources == ((3, "span_owner_1rw"),)
    assert energy["span_owner_primary"] == Counter(read=1)


def test_m3_does_not_convert_hot_register_access_to_cacti_energy():
    resources, energy = access_plan("M3_register_hot_state_with_sram_backing", member("head_control", "read"), Counter())
    assert resources == ((3, "head_hot_register"),)
    assert "head_control_register_hot_state_unestimated" in energy
    capacities = resource_capacities("M3_register_hot_state_with_sram_backing")
    assert can_use(resources, Counter(), capacities)
    assert not can_use(resources, Counter({(3, "head_hot_register"): 2}), capacities)


def test_frozen_ha8_wide_commit_gate_does_not_add_a_global_serial_slot():
    tx = [type("Tx", (), {"predecessors": ()})(), type("Tx", (), {"predecessors": ()})()]
    completed = {0: {member("head_control")}, 1: {member("span_owner")}}
    members = {0: (member("head_control"),), 1: (member("span_owner"),)}
    assert commit_ready_groups({0, 1}, completed, members, tx, set()) == [0, 1]
