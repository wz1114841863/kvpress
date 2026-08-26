from tools.simulate_kvzap_route_a311_deferred_memory_system import branch_total


def test_initial_deferred_fallback_has_no_admission_service_charge():
    cost = {"full_bytes": 100, "full_cycles": 10, "hybrid_bytes": 30, "hybrid_cycles": 3, "fallback": False}
    assert branch_total(cost, initial_fallback=True, admission_bytes=40, admission_bandwidth=20) == ("initial_full_kv", 100.0, 10.0, 0)


def test_post_activation_staging_fallback_continues_admission_service():
    cost = {"full_bytes": 100, "full_cycles": 10, "hybrid_bytes": 100, "hybrid_cycles": 10, "fallback": True}
    assert branch_total(cost, initial_fallback=False, admission_bytes=40, admission_bandwidth=20) == ("staging_full_kv", 140.0, 12.0, 40)
