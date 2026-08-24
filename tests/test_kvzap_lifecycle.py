import csv
import json

import numpy as np
import torch

from kvpress.lifecycle import FINAL_COLUMNS, LIFECYCLE_COLUMNS, LifecycleSimulator, PackedColdPageState
from kvpress.presses.kvzap_press import KVzapPress
from tools.replay_kvzap_decode_lifecycle_pages import replay
from tools.validate_kvzap_decode_lifecycle_trace import validate


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


def test_lifecycle_page_replay_preserves_admissions_and_changes_only_page_geometry():
    events = [
        {"request_id": "r", "model_call": "0", "phase": "context_prefill", "layer": "0", "kv_head": "0", "score_start": "0", "q_len": "5", "cache_tokens_after": "5", "matured_tokens": "3", "cold_admitted_tokens": "3", "cold_dropped_tokens": "0"},
        {"request_id": "r", "model_call": "1", "phase": "decode", "layer": "0", "kv_head": "0", "score_start": "5", "q_len": "1", "cache_tokens_after": "6", "matured_tokens": "1", "cold_admitted_tokens": "0", "cold_dropped_tokens": "1"},
    ]
    rows, final, summary = replay(events, page_tokens=2, metadata_bytes_per_page=4, kv_bytes_per_token=8, window=2)
    assert [row["cold_logical_tokens"] for row in rows] == [3, 3]
    assert final[0]["cold_allocated_slots"] == 4
    assert final[0]["tail_waste_slots"] == 1
    assert summary["declared_hot_to_cold_read_bytes"] == 32
    assert summary["declared_cold_write_bytes"] == 24
    assert summary["physical_capacity_compression"] == 1.0


def test_validator_counts_request_level_phase_once_not_once_per_head(tmp_path):
    simulator = LifecycleSimulator(layers=1, heads=2, window=2, page_tokens=2, kv_bytes_per_token=8, metadata_bytes_per_page=2)
    rows = simulator.observe(0, 0, np.asarray([[1.0, 1.0, 1.0], [-1.0, -1.0, -1.0]], dtype=np.float32), 0.0, 0, "context_prefill")
    for row in rows:
        row["request_id"] = "r"
    with (tmp_path / "lifecycle_events.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LIFECYCLE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    final = [{"request_id": "r", **row} for row in simulator.final_rows()]
    with (tmp_path / "lifecycle_final_state.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FINAL_COLUMNS)
        writer.writeheader()
        writer.writerows(final)
    manifest = {
        "schema_version": "kvzap-route-a2-readonly-lifecycle-1.0", "page_tokens": 2,
        "kv_bytes_per_layer_head_token": 8, "metadata_bytes_per_cold_page": 2, "sliding_window": 2,
        "trace_equivalence": {"answers_identical": True, "lifecycle_digests_identical": True, "lifecycle_summaries_identical": True},
        "observational_guards": {"dms_press_used": False, "masked_key_indices_created": False, "fake_key_attention_used": False, "model_cache_mutated_by_collector": False},
        "decode_lifecycle_observation": {"decode_model_call_count": 0, "pipeline_generated_token_ids_observed": 1, "answer_retokenized_token_count": 0, "phase_summary": {"context_prefill": {"model_call_count": 1, "query_tokens": 3, "matured_layer_head_slots": 2, "cold_admitted_tokens": 1, "cold_dropped_tokens": 1, "cold_page_allocations": 1, "cold_page_seals": 0, "hot_to_cold_read_bytes": 16, "cold_write_bytes": 8, "metadata_update_bytes": 2}}},
    }
    (tmp_path / "lifecycle_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert validate(tmp_path) == {"layers": 1, "layer_heads": 2, "events": 2}
