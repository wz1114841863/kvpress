import numpy as np
import torch

from kvpress.lifecycle import LifecycleSimulator, PackedColdPageState
from kvpress.presses.kvzap_press import KVzapPress


def test_packed_cold_page_state_allocates_and_seals():
    state = PackedColdPageState(page_tokens=2)
    assert state.append(1) == (1, 0)
    assert (state.logical_tokens, state.page_count, state.tail_valid_count) == (1, 1, 1)
    assert state.append(3) == (1, 2)
    assert (state.logical_tokens, state.page_count, state.tail_valid_count, state.allocated_slots) == (4, 2, 2, 4)


def test_lifecycle_hot_window_matures_drop_and_admit_without_mask_mutation():
    simulator = LifecycleSimulator(layers=1, heads=2, window=2, page_tokens=2, kv_bytes_per_token=8, metadata_bytes_per_page=2)
    scores = np.asarray([[1.0, -1.0, 1.0, 1.0], [-1.0, -1.0, 1.0, -1.0]], dtype=np.float32)
    rows = simulator.observe(0, 0, scores, threshold=0.0, model_call=0, phase="context_prefill")
    # The first two tokens leave a two-token hot window. H0 admits one and drops one; H1 drops both.
    assert [(row["cold_admitted_tokens"], row["cold_dropped_tokens"]) for row in rows] == [(1, 1), (0, 2)]
    assert rows[0]["hot_tokens_before"] == 0
    assert rows[0]["matured_tokens"] == 2
    assert rows[0]["hot_to_cold_read_bytes"] == 16
    assert rows[0]["cold_write_bytes"] == 8
    assert rows[0]["cold_page_allocations"] == 1
    assert rows[0]["cold_logical_tokens"] == 1
    assert rows[1]["cold_page_count"] == 0


def test_lifecycle_requires_contiguous_positions_and_tracks_decode_page_seal():
    simulator = LifecycleSimulator(layers=1, heads=1, window=1, page_tokens=2, kv_bytes_per_token=8, metadata_bytes_per_page=2)
    simulator.observe(0, 0, np.asarray([[1.0, 1.0]], dtype=np.float32), 0.0, 0, "context_prefill")
    row = simulator.observe(0, 2, np.asarray([[1.0]], dtype=np.float32), 0.0, 1, "decode")[0]
    assert row["cold_admitted_tokens"] == 1
    assert row["cold_page_seals"] == 1
    assert row["cold_page_count"] == 1
    try:
        simulator.observe(0, 4, np.asarray([[1.0]], dtype=np.float32), 0.0, 2, "decode")
    except AssertionError as error:
        assert "not contiguous" in str(error)
    else:
        raise AssertionError("non-contiguous lifecycle position should fail")


def test_kvzap_press_passes_explicit_predictor_revision(monkeypatch):
    loaded = {}

    class Loaded:
        layers = torch.nn.ModuleList([])

    def fake_load(name, revision=None):
        loaded.update(name=name, revision=revision)
        return Loaded()

    monkeypatch.setattr("kvpress.presses.kvzap_press.KVzapModel.from_pretrained", fake_load)
    model = type("Model", (), {"config": type("Config", (), {"name_or_path": "Qwen/Qwen3-8B"})()})()
    KVzapPress(model_type="mlp", predictor_revision="frozen-revision").post_init_from_model(model)
    assert loaded == {"name": "nvidia/KVzap-mlp-Qwen3-8B", "revision": "frozen-revision"}
