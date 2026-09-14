import json
from dataclasses import replace

import pytest
import torch

from kvpress.route_a_frontend_contract import (
    snapkv_terminal_decisions_from_scores,
    snapkv_terminal_decisions_to_route_a_replay_masks,
    write_frontend_decision_stream,
)
from tools.analyze_snapkv_route_a_p1_packed_opportunity import P0_MANIFEST_NAME, P0_STREAM_NAME
from tools.run_snapkv_route_a_p3_semantic_gate import P1_REPORT_NAME, load_p3_inputs, resolve_language_model


def _write_completed_inputs(tmp_path):
    p0_dir = tmp_path / "p0"
    p0_dir.mkdir()
    decisions = snapkv_terminal_decisions_from_scores(
        torch.arange(128, dtype=torch.float32).reshape(1, 1, 128),
        compression_ratio=0.5,
        layer=0,
        request_id="builtin_summarization_trace",
    )
    stream = p0_dir / P0_STREAM_NAME
    stream_sha = write_frontend_decision_stream(stream, decisions)
    config = {
        "model_name": "Qwen/Qwen3-8B",
        "model_revision": "b968826d9c46dd6066d109eabc6255188de91218",
        "preset": "summarization",
        "context_repetitions": 12,
        "compression_ratio": 0.5,
        "window_size": 64,
        "kernel_size": 5,
        "seed": 42,
        "max_new_tokens": 1,
        "input_jsonl": None,
        "request_id": None,
        "target_layers": ["all"],
    }
    p0 = {
        "schema_version": "route-a-snapkv-p0-contract-gate-1.0",
        "status": "complete",
        "request_id": "builtin_summarization_trace",
        "request_content_hash": "unit-request",
        "config": config,
        "decision_stream_schema": "route-a-frontend-decision-stream-1.0",
        "decision_stream_file": P0_STREAM_NAME,
        "decision_stream_sha256": stream_sha,
        "decision_stream_event_count": len(decisions),
        "trace_off_on_answer_match": True,
    }
    manifest = p0_dir / P0_MANIFEST_NAME
    manifest.write_text(json.dumps(p0), encoding="utf-8")
    p1 = {
        "schema_version": "route-a-snapkv-p1-static-packed-opportunity-1.0",
        "status": "complete",
        "input": {
            "p0_manifest_sha256": __import__("hashlib").sha256(manifest.read_bytes()).hexdigest(),
            "p0_terminal_stream_sha256": stream_sha,
        },
        "mapping": {
            "terminal_drop": "absent from Route-A stores",
            "terminal_keep_at_or_after_resident_window_start": "resident hot window",
            "terminal_keep_before_resident_window_start": "append-only per-(layer,kv_head) cold pages in original-position order",
            "native_score_ranked_gather_order_used": False,
            "resident_window_is_p0_snapkv_observation_window": True,
        },
        "config": {"resident_window": 64, "page_tokens": [16, 32, 64, 128]},
        "request_rows": [
            {
                "page_tokens": 64,
                "request_id": "builtin_summarization_trace",
                "resident_window": 64,
                "hot_slots": 64,
                "cold_logical_kept_slots": 0,
                "cold_page_count": 0,
            }
        ],
    }
    p1_path = tmp_path / P1_REPORT_NAME
    p1_path.write_text(json.dumps(p1), encoding="utf-8")
    return p0_dir, p1_path


def test_p3_input_loader_binds_p0_p1_and_converts_canonical_positions(tmp_path):
    p0_dir, p1_path = _write_completed_inputs(tmp_path)
    p0, decisions, _p1, masks = load_p3_inputs(p0_dir, p1_path)
    assert p0["request_id"] == "builtin_summarization_trace"
    assert len(decisions) == 128
    assert masks[0][(0, 0)] == (False, 0.0)
    assert masks[0][(0, 63)] == (False, 63.0)
    assert masks[0][(0, 64)] == (True, 64.0)
    assert masks[0][(0, 127)] == (True, 127.0)


def test_p3_rejects_tampered_p1_p0_provenance(tmp_path):
    p0_dir, p1_path = _write_completed_inputs(tmp_path)
    report = json.loads(p1_path.read_text())
    report["input"]["p0_terminal_stream_sha256"] = "not-the-source"
    p1_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="terminal stream SHA-256"):
        load_p3_inputs(p0_dir, p1_path)


def test_terminal_converter_rejects_a_second_model_call(tmp_path):
    p0_dir, _p1_path = _write_completed_inputs(tmp_path)
    from kvpress.route_a_frontend_contract import load_frontend_decision_stream

    decisions = load_frontend_decision_stream(p0_dir / P0_STREAM_NAME)
    changed = [replace(decision, model_call_index=1) if index == 0 else decision for index, decision in enumerate(decisions)]
    with pytest.raises(ValueError, match="one terminal prefill model call"):
        snapkv_terminal_decisions_to_route_a_replay_masks(changed)


def test_p3_resolves_qwen_inner_language_model_not_top_level_wrapper():
    class LanguageModel:
        pass

    class Core:
        language_model = LanguageModel()

    class Wrapper:
        model = Core()

    assert isinstance(resolve_language_model(Wrapper()), LanguageModel)
