from types import SimpleNamespace

from tools.simulate_kvzap_route_a492_record_granular_engine import MicroOp, record_granular_replay


def tx(index, arrival, predecessors, banks):
    return SimpleNamespace(index=index, arrival_ordinal=arrival, predecessors=frozenset(predecessors), banks=frozenset(banks))


def candidate(**changes):
    base = {"banks": 2, "read_ports": 1, "write_ports": 1, "rmw_lanes": 1,
            "queue_groups_per_bank": 8, "commit_slots": 1}
    base.update(changes)
    return base


def test_member_completion_does_not_release_dependency_before_commit():
    first = tx(0, 0, (), {0, 1})
    second = tx(1, 0, {0}, {0})
    members = {
        0: (MicroOp(0, ("a", (0,)), 0, "read"), MicroOp(0, ("b", (0,)), 1, "rmw")),
        1: (MicroOp(1, ("c", (0,)), 0, "write"),),
    }
    result = record_granular_replay([first, second], [("x", 0)], members, candidate(), 16)
    assert result["completed"] == 2 and result["drained_within_declared_bound"]
    assert result["blocking_observation_counts"]["intrinsic_dependency"] > 0
    assert result["transaction_commit_delay_abstract_cycles"]["max"] >= 2


def test_same_record_lock_is_distinct_from_intrinsic_dependency():
    left = tx(0, 0, (), {0})
    right = tx(1, 0, (), {0})
    members = {
        0: (MicroOp(0, ("shared", (0,)), 0, "rmw"),),
        1: (MicroOp(1, ("shared", (0,)), 0, "rmw"),),
    }
    result = record_granular_replay([left, right], [("x", 0)], members, candidate(commit_slots=0), 16)
    assert result["blocking_observation_counts"]["same_record_lock"] > 0
    assert result["blocking_observation_counts"]["intrinsic_dependency"] == 0


def test_inflight_transaction_lock_remains_legal_after_another_transaction_commits():
    completed_first = tx(0, 0, (), {0})
    still_inflight = tx(1, 0, (), {1})
    members = {
        0: (MicroOp(0, ("first", (0,)), 0, "write"),),
        1: (MicroOp(1, ("second", (0,)), 1, "rmw"),),
    }
    result = record_granular_replay([completed_first, still_inflight], [("x", 0)], members, candidate(commit_slots=0), 16)
    assert result["completed"] == 2 and result["drained_within_declared_bound"]


def test_bank_resource_reasons_are_separate():
    group = tx(0, 0, (), {0})
    members = {0: (
        MicroOp(0, ("r", (0,)), 0, "read"),
        MicroOp(0, ("w", (0,)), 0, "write"),
        MicroOp(0, ("m", (0,)), 0, "rmw"),
        MicroOp(0, ("m2", (0,)), 0, "rmw"),
    )}
    result = record_granular_replay([group], [("x", 0)], members, candidate(commit_slots=0), 16)
    assert result["blocking_observation_counts"]["rmw_lane"] > 0
    assert result["active_micro_op_concurrency"]["max"] >= 2


def test_cross_bank_commit_coordination_is_reported():
    left = tx(0, 0, (), {0, 1})
    right = tx(1, 0, (), {0, 1})
    members = {
        0: (MicroOp(0, ("a", (0,)), 0, "write"), MicroOp(0, ("b", (0,)), 1, "write")),
        1: (MicroOp(1, ("c", (0,)), 0, "write"), MicroOp(1, ("d", (0,)), 1, "write")),
    }
    result = record_granular_replay([left, right], [("x", 0)], members, candidate(write_ports=2), 16)
    assert result["completed"] == 2
    assert result["blocking_observation_counts"]["cross_bank_commit_coordination"] > 0
