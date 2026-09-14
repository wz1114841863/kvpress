import pytest

from tools.run_kvzap_llama31_m51_fixed_horizon_workload_descriptor import (
    M51_SCHEMA,
    M51_PREVIOUS_SCHEMA,
    expected_policy_decode_calls,
    token_ids_digest,
    validate_forced_token_trajectory,
)


def test_m51_schema_and_fixed_decode_contract_are_versioned():
    assert M51_SCHEMA == "kvzap-llama31-m51-fixed-horizon-workload-descriptor-1.1"
    assert M51_PREVIOUS_SCHEMA == "kvzap-llama31-m51-fixed-horizon-workload-descriptor-1.0"
    assert expected_policy_decode_calls(8) == 7


def test_m51_fixed_decode_contract_rejects_one_token_horizon():
    with pytest.raises(ValueError, match="at least two"):
        expected_policy_decode_calls(1)


def test_m51_token_digest_is_deterministic_and_order_sensitive():
    assert token_ids_digest([1, 2, 3]) == token_ids_digest([1, 2, 3])
    assert token_ids_digest([1, 2, 3]) != token_ids_digest([3, 2, 1])


def test_m51_forced_token_check_does_not_make_whole_logit_equality_a_gate():
    validate_forced_token_trajectory(
        dense={"generated_token_ids": [1, 2], "logits": [object()]},
        route={"generated_token_ids": [1, 2], "logits": [object()]},
        workload="retrieval",
    )
    with pytest.raises(AssertionError, match="token IDs"):
        validate_forced_token_trajectory(
            dense={"generated_token_ids": [1, 2]},
            route={"generated_token_ids": [2, 1]},
            workload="retrieval",
        )
