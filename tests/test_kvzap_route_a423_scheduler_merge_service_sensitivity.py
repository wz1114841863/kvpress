import pytest

from tools.analyze_kvzap_route_a423_scheduler_merge_service_sensitivity import A423_SCHEMA, capacity_exceeding_evaluations, fan_in_bounds, state_waves


def test_a423_schema_and_exact_fan_in_bounds():
    assert A423_SCHEMA.endswith("scheduler-merge-service-sensitivity-1.0")
    bounds = fan_in_bounds(merge_calls=10, packed_partials=8, pending_partials=3)
    assert bounds["minimum_three_source_overlap"] == {"one_active_source": 0, "two_active_sources": 9, "three_active_sources": 1}
    assert bounds["maximum_three_source_overlap"] == {"one_active_source": 2, "two_active_sources": 5, "three_active_sources": 3}


def test_a423_capacity_and_wave_accounting_is_explicit_not_a_queue_claim():
    counts = {"one_active_source": 2, "two_active_sources": 5, "three_active_sources": 3}
    assert capacity_exceeding_evaluations(counts, 1) == 8
    assert capacity_exceeding_evaluations(counts, 2) == 3
    assert capacity_exceeding_evaluations(counts, 3) == 0
    assert state_waves(counts, 1) == 21
    assert state_waves(counts, 2) == 13
    assert state_waves(counts, 3) == 10


def test_a423_rejects_invalid_marginal_counts():
    with pytest.raises(ValueError, match="exceeds"):
        fan_in_bounds(merge_calls=2, packed_partials=3, pending_partials=0)
