import pytest

from tools.analyze_kvzap_route_a_m6_cross_model_fixed_horizon_envelope import (
    FAN_IN_KEYS,
    M6_SCHEMA,
    coverage_envelope,
    normalize_workload,
    require_fraction_distribution,
    source_active_fractions,
)


def _row(*, model_anchor: str = "qwen", workload: str = "retrieval", three_way: float = 0.25):
    return normalize_workload(
        model_anchor=model_anchor,
        workload=workload,
        policy_decode_calls=7,
        combinations={"hot": 0.25, "hot+packed": 0.75 - three_way, "hot+pending+packed": three_way},
        fan_in={"1_active_sources": 0.25, "2_active_sources": 0.75 - three_way, "3_active_sources": three_way},
        record_counts={
            "hot": {"sample_count": 4, "p50": 128, "p95": 128, "max": 128},
            "pending": {"sample_count": 1, "p50": 3, "p95": 3, "max": 3},
            "packed": {"sample_count": 3, "p50": 7, "p95": 11, "max": 13},
        },
        packed_tail={"p50": 1, "p95": 11, "max": 13, "tail_p50": 7, "tail_p95": 55, "tail_max": 63},
    )


def test_m6_schema_and_fan_in_keys_are_versioned():
    assert M6_SCHEMA == "kvzap-route-a-m6-cross-model-fixed-horizon-envelope-1.0"
    assert FAN_IN_KEYS == ("1_active_sources", "2_active_sources", "3_active_sources")


def test_fraction_distribution_rejects_non_unit_sum():
    with pytest.raises(ValueError, match="does not sum"):
        require_fraction_distribution(
            {"1_active_sources": 0.4, "2_active_sources": 0.4, "3_active_sources": 0.1},
            FAN_IN_KEYS,
            label="test",
        )


def test_normalized_workload_rejects_mismatched_fan_in():
    with pytest.raises(ValueError, match="does not match"):
        normalize_workload(
            model_anchor="test",
            workload="retrieval",
            policy_decode_calls=7,
            combinations={"hot": 0.5, "hot+packed": 0.5},
            fan_in={"1_active_sources": 0.25, "2_active_sources": 0.75, "3_active_sources": 0.0},
            record_counts={
                "hot": {"sample_count": 2, "p50": 128, "p95": 128, "max": 128},
                "packed": {"sample_count": 1, "p50": 1, "p95": 1, "max": 1},
            },
            packed_tail={"p50": 1, "p95": 1, "max": 1, "tail_p50": 1, "tail_p95": 1, "tail_max": 1},
        )


def test_source_active_fractions_derive_from_combinations():
    assert source_active_fractions({"hot": 0.25, "hot+pending+packed": 0.75}) == {
        "hot": 1.0,
        "pending": 0.75,
        "packed": 0.75,
    }


def test_coverage_envelope_uses_zero_only_for_explicitly_unobserved_combination():
    first = _row(three_way=0.25)
    second = _row(model_anchor="llama", workload="reasoning", three_way=0.0)
    envelope = coverage_envelope([first, second])
    assert envelope["source_combination_fractions"]["hot+pending+packed"] == {
        "min": 0.0,
        "max": 0.25,
        "range": 0.25,
        "sample_count": 2,
    }
    assert envelope["source_record_count_conditioned_on_nonempty"]["packed"]["max"]["sample_count"] == 2
