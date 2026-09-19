from tools.analyze_kvzap_route_a465_causal_capacity_envelope import observer_summary, run_causal_observer


def test_a465_capacity_observer_reports_breach_without_mutating_samples():
    samples = {(0, 0): [(1, 8), (2, 20), (3, 24)]}
    before = {key: list(value) for key, value in samples.items()}
    result = observer_summary(samples, (16,), scope="head_local")
    assert samples == before
    assert result[0]["breached_stream_count"] == 1
    assert result[0]["first_breach_opportunity"] == 2
    assert result[0]["peak_excess"] == 8
    assert result[0]["max_consecutive_breach_duration"] == 2


def test_a465_causal_replay_has_no_capacity_input_or_drop_action():
    inventory = {(0, 0): {"pending": 20, "packed": 1, "hot": 2}}
    arrivals = {(0, 0): [0, 0]}
    result = run_causal_observer(inventory=inventory, arrivals=arrivals, horizon=2)
    assert result["B_final"] == 0
    assert result["deadline_miss_head_count"] == 0
    assert all("capacity" not in key.lower() for key in result)
