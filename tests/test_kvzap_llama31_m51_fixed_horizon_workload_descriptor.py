import pytest

from tools.run_kvzap_llama31_m51_fixed_horizon_workload_descriptor import (
    M51_SCHEMA,
    expected_policy_decode_calls,
    token_ids_digest,
)


def test_m51_schema_and_fixed_decode_contract_are_versioned():
    assert M51_SCHEMA == "kvzap-llama31-m51-fixed-horizon-workload-descriptor-1.0"
    assert expected_policy_decode_calls(8) == 7


def test_m51_fixed_decode_contract_rejects_one_token_horizon():
    with pytest.raises(ValueError, match="at least two"):
        expected_policy_decode_calls(1)


def test_m51_token_digest_is_deterministic_and_order_sensitive():
    assert token_ids_digest([1, 2, 3]) == token_ids_digest([1, 2, 3])
    assert token_ids_digest([1, 2, 3]) != token_ids_digest([3, 2, 1])
