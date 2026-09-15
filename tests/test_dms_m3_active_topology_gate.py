import numpy as np
import pytest

from tools.run_dms_route_a_m3_active_topology_gate import ActiveSlotTopologyController, M3_SCHEMA, replay_topology


def test_m3_controller_tracks_logical_source_arrivals_across_slot_reuse():
    controller = ActiveSlotTopologyController(window_size=3)
    controller.consume(np.asarray([1, 1, 0], dtype=np.uint8))
    assert controller.active_sources() == [0, 1, 2]
    controller.consume(np.asarray([0], dtype=np.uint8))
    # The marked first source is retired at the ring turn and its native slot
    # receives the fourth arrival; no source is duplicated among active slots.
    assert controller.active_sources() == [3, 1, 2]
    assert controller.cache_length == 3
    assert controller.arrival_count == 4
    assert controller.native_recent_info().shape == (3, 2)


def test_m3_replay_requires_native_ring_metadata_and_length_agreement():
    events = []
    for layer in range(36):
        controllers = [ActiveSlotTopologyController(window_size=3) for _ in range(8)]
        for controller in controllers:
            controller.consume(np.asarray([0], dtype=np.uint8))
        events.append(
            {
                "layer": layer,
                "call_index": layer,
                "q_len": 1,
                "decision_bits": np.zeros((8, 1), dtype=np.uint8),
                "native_recent_info": np.stack([controller.native_recent_info() for controller in controllers]),
                "native_recent_info_position": np.asarray([controller.recent_position for controller in controllers], dtype=np.int32),
                "cache_lengths_before": [0] * 8,
                "cache_lengths_after": [1] * 8,
            }
        )
    summary, lengths, topology = replay_topology(events, window_size=3)
    assert summary["per_event_native_ring_metadata_agreement"] is True
    assert lengths.shape == (36, 8)
    assert topology.shape == (36, 8, 1)
    events[0]["native_recent_info"][0, 0, 0] = 99
    with pytest.raises(AssertionError, match="ring metadata"):
        replay_topology(events, window_size=3)


def test_m3_schema_is_explicitly_not_route_a_attention():
    assert M3_SCHEMA == "route-a-dms-m3-active-native-slot-topology-1.0"
