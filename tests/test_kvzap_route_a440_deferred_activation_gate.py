import pytest

from tools.run_kvzap_llama31_a440_deferred_activation_gate import assert_journal_coverage


def test_a440_journal_guard_accepts_full_kv_decisions_without_route_a_state():
    events = {
        layer: {(head, position): (True, 0.0) for head in range(2) for position in range(4)}
        for layer in range(3)
    }
    assert_journal_coverage(events, layers=3, heads=2, label="test")


def test_a440_journal_guard_rejects_missing_or_noncontiguous_decisions():
    missing = {0: {(0, 0): (True, 0.0), (1, 0): (True, 0.0)}}
    with pytest.raises(AssertionError, match="every selected layer"):
        assert_journal_coverage(missing, layers=2, heads=2, label="test")
    noncontiguous = {0: {(head, position): (True, 0.0) for head in range(2) for position in (0, 2)} }
    with pytest.raises(AssertionError, match="non-contiguous"):
        assert_journal_coverage(noncontiguous, layers=1, heads=2, label="test")
