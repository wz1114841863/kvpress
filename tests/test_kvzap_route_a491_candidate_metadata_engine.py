from types import SimpleNamespace
from tools.simulate_kvzap_route_a491_candidate_metadata_engine import duration, replay

def test_rmw_duration_uses_declared_lanes():
    tx=SimpleNamespace(demands={(0,"rmw"):2}, banks=frozenset({0}))
    assert duration(tx, {"read_ports":1,"write_ports":1,"rmw_lanes":1}) == 4
    assert duration(tx, {"read_ports":2,"write_ports":2,"rmw_lanes":2}) == 2

def test_replay_preserves_predecessor_before_commit():
    a=SimpleNamespace(index=0, arrival_ordinal=0, predecessors=frozenset(), demands={(0,"write"):1}, banks=frozenset({0}))
    b=SimpleNamespace(index=1, arrival_ordinal=0, predecessors=frozenset({0}), demands={(0,"rmw"):1}, banks=frozenset({0}))
    result=replay([a,b], [("x",0)], {"banks":1,"read_ports":1,"write_ports":1,"rmw_lanes":1,"queue_groups_per_bank":8,"commit_slots":0}, 16)
    assert result["completed"] == 2 and result["drained_within_declared_bound"]
