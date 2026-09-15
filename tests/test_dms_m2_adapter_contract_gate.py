import json
from pathlib import Path

import numpy as np
import pytest

from tools.run_dms_route_a_m1_native_semantic_gate import M0_SCHEMA, M1_SCHEMA
from tools.run_dms_route_a_m2_adapter_contract_gate import (
    DelayedEvictionSlotReuseController,
    M2_SCHEMA,
    read_completed_m1,
    replay_native_contract,
)


def _m0(tmp_path: Path) -> Path:
    path = tmp_path / "m0.json"
    path.write_text(json.dumps({"schema_version": M0_SCHEMA, "status": "complete"}), encoding="utf-8")
    return path


def _m1(tmp_path: Path, m0: Path, *, equivalent: bool = True) -> Path:
    path = tmp_path / "m1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": M1_SCHEMA,
                "status": "complete",
                "m0_provenance": {"m0_manifest_sha256": __import__("hashlib").sha256(m0.read_bytes()).hexdigest()},
                "trace_off_on_equivalence": {"token_logit_cache_digests_identical": equivalent},
                "observational_guards": {"official_binary_dms_decisions_observed": True},
                "native_dms_trace_summary": {
                    "all_36_layers_all_8_kv_heads_covered": True,
                    "event_summary_sha256": "test-summary",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_m2_requires_completed_equivalent_m1_bound_to_exact_m0(tmp_path):
    m0 = _m0(tmp_path)
    report = read_completed_m1(_m1(tmp_path, m0), m0_manifest=m0)
    assert report["schema_version"] == M1_SCHEMA
    with pytest.raises(ValueError, match="equivalence"):
        read_completed_m1(_m1(tmp_path / "bad", m0, equivalent=False), m0_manifest=m0)


def test_delayed_eviction_controller_marks_previous_arrival_and_reuses_slot_only_at_ring_turn():
    controller = DelayedEvictionSlotReuseController(window_size=3)
    # The first decision labels no prior entry.  The second marks token 0;
    # after three later arrivals, token 0 becomes candidate and its slot is
    # reused rather than growing the abstract native cache length.
    assert controller.consume(np.asarray([1, 1, 0], dtype=np.uint8)) == [0, 1, 2]
    assert controller.cache_length == 3
    assert controller.consume(np.asarray([0], dtype=np.uint8)) == [0]
    assert controller.cache_length == 3


def test_m2_replay_rejects_native_length_mismatch():
    events = []
    for layer in range(36):
        events.append(
            {
                "layer": layer,
                "call_index": layer,
                "kind": "prefill",
                "q_len": 1,
                "decision_bits": np.zeros((8, 1), dtype=np.uint8),
                "cache_lengths_before": [0] * 8,
                "cache_lengths_after": [1] * 8,
            }
        )
    replay = replay_native_contract(events, window_size=3)
    assert replay["per_event_native_cache_length_agreement"] is True
    events[0]["cache_lengths_after"][0] = 7
    with pytest.raises(AssertionError, match="post-update"):
        replay_native_contract(events, window_size=3)


def test_m2_schema_is_explicit_and_not_route_a_schema():
    assert M2_SCHEMA == "route-a-dms-m2-delayed-eviction-adapter-contract-1.0"
