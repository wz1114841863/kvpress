import json

import pytest
import torch

from kvpress.route_a_frontend_contract import snapkv_terminal_decisions_from_scores, write_frontend_decision_stream
from tools.analyze_snapkv_route_a_p1_packed_opportunity import (
    P0_MANIFEST_NAME,
    P0_SCHEMA,
    P0_STREAM_NAME,
    decisions_to_final_drop,
    load_p0_input,
    replay_p1,
)


def _write_p0(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    decisions = snapkv_terminal_decisions_from_scores(
        torch.tensor([[[0.1, 0.2, 0.3, 0.4, 10.0, 11.0]]]),
        compression_ratio=1 / 3,
        layer=0,
        request_id="unit",
    )
    stream = tmp_path / P0_STREAM_NAME
    digest = write_frontend_decision_stream(stream, decisions)
    manifest = {
        "schema_version": P0_SCHEMA,
        "status": "complete",
        "request_id": "unit",
        "config_hash": "unit-config",
        "git_commit": "unit-commit",
        "config": {"window_size": 2, "compression_ratio": 1 / 3},
        "decision_stream_schema": "route-a-frontend-decision-stream-1.0",
        "decision_stream_file": P0_STREAM_NAME,
        "decision_stream_sha256": digest,
        "decision_stream_event_count": len(decisions),
        "trace_off_on_answer_match": True,
    }
    (tmp_path / P0_MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    return decisions


def test_p1_reconstructs_complete_final_mask_without_changing_terminal_stream(tmp_path):
    decisions = _write_p0(tmp_path)
    manifest, loaded, window, ratio = load_p0_input(tmp_path)
    assert manifest["request_id"] == "unit"
    assert loaded == decisions
    assert (window, ratio) == (2, pytest.approx(1 / 3))
    final_drop, valid, layers, heads, length = decisions_to_final_drop(loaded)
    assert (layers, heads, length) == (1, 1, 6)
    assert valid.all()
    assert final_drop.tolist() == [[[True, True, False, False, False, False]]]


def test_p1_maps_protected_window_to_hot_and_rounds_cold_pages(tmp_path):
    _write_p0(tmp_path)
    _manifest, decisions, _window, _ratio = load_p0_input(tmp_path)
    request, heads = replay_p1(
        decisions=decisions,
        request_id="unit",
        resident_window=2,
        page_tokens=4,
        kv_bytes_per_token=8,
        metadata_bytes_per_page=2,
    )
    assert request["hot_slots"] == 2
    assert request["cold_logical_kept_slots"] == 2
    assert request["cold_allocated_slots"] == 4
    assert request["tail_waste_slots"] == 2
    assert request["cold_page_count"] == 1
    assert request["ideal_packed_slots"] == 4
    assert request["physical_allocated_slots"] == 6
    assert heads[0]["tail_page_valid_slots"] == 2


def test_p1_rejects_tampered_p0_stream_hash_and_nonmatching_trace_guard(tmp_path):
    _write_p0(tmp_path)
    stream = tmp_path / P0_STREAM_NAME
    stream.write_bytes(stream.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="SHA-256"):
        load_p0_input(tmp_path)

    _write_p0(tmp_path / "guard")
    manifest_path = tmp_path / "guard" / P0_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    manifest["trace_off_on_answer_match"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="trace-off/on"):
        load_p0_input(tmp_path / "guard")
