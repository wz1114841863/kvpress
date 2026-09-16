import pytest

from tools.analyze_kvzap_route_a431_policy_pending_staging_envelope import summarize_comparisons


def test_pending_snapshot_summary_tracks_per_layer_head_max_without_fifo_claim():
    result = summarize_comparisons([
        {"layer": 0, "kv_head": 1, "pending_tokens": 2},
        {"layer": 0, "kv_head": 1, "pending_tokens": 5},
        {"layer": 1, "kv_head": 0, "pending_tokens": 0},
    ])
    assert result["pending_tokens_snapshot_max"] == 5
    assert result["pending_nonempty_snapshot_fraction"] == 2 / 3
    assert result["per_layer_snapshot_max"] == {"0": 5, "1": 0}
    assert result["per_layer_kv_head_snapshot_max"][0] == {"layer": 0, "kv_head": 1, "pending_tokens_snapshot_max": 5}
    assert result["overflow_observation"].startswith("not_observable")


def test_pending_snapshot_summary_rejects_negative_or_missing_values():
    with pytest.raises(ValueError, match="invalid"):
        summarize_comparisons([{"layer": 0, "kv_head": 0, "pending_tokens": -1}])
