from tools.analyze_kvzap_route_a462_activation_service_envelope import (
    INDEPENDENT_POLICY,
    SHARED_POLICY,
    minimum_quantum,
    simulate_layer_shared_round_robin,
)


def test_a462_multi_horizon_minimum_independent_quantum_changes_with_deadline():
    initial = {(0, 0): 4}
    arrivals = {(0, 0): [0, 0]}
    assert minimum_quantum(initial, arrivals, horizon=1, policy=INDEPENDENT_POLICY)[0] == 4
    assert minimum_quantum(initial, arrivals, horizon=2, policy=INDEPENDENT_POLICY)[0] == 2


def test_a462_layer_shared_round_robin_records_competing_head_backlog_fairly():
    initial = {(0, 0): 3, (0, 1): 1}
    arrivals = {(0, 0): [0], (0, 1): [0]}
    rows = simulate_layer_shared_round_robin(initial, arrivals, quantum=2, horizon=1)
    assert [(x["kv_head"], x["final_pending_after_service"], x["logical_service_tokens_granted"]) for x in rows] == [(0, 2, 1), (1, 0, 1)]
    assert minimum_quantum(initial, arrivals, horizon=1, policy=SHARED_POLICY)[0] == 4
