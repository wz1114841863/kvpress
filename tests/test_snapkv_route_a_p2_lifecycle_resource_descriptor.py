import hashlib
import json

import pytest
import torch

from kvpress.route_a_frontend_contract import snapkv_terminal_decisions_from_scores, write_frontend_decision_stream
from tools.analyze_snapkv_route_a_p1_packed_opportunity import P0_MANIFEST_NAME, P0_STREAM_NAME
from tools.analyze_snapkv_route_a_p2_lifecycle_resource_descriptor import (
    P3_MANIFEST_NAME,
    build_descriptor,
    load_p2_inputs,
)


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
            "p0_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
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
    p1_path = tmp_path / "snapkv_p1_packed_opportunity_report.json"
    p1_path.write_text(json.dumps(p1), encoding="utf-8")
    p3_dir = tmp_path / "p3"
    p3_dir.mkdir()
    p3 = {
        "schema_version": "route-a-snapkv-p3-same-mask-semantic-gate-1.0",
        "status": "complete",
        "config": {"source_epoch": "prefill_terminal", "generated_token_forward_count": 0},
        "input_provenance": {
            "p0_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "p0_terminal_stream_sha256": stream_sha,
            "p1_report_sha256": hashlib.sha256(p1_path.read_bytes()).hexdigest(),
            "p0_event_count": len(decisions),
        },
        "observational_guards": {
            "p0_and_p1_sha256_bound_and_revalidated": True,
            "p1_native_score_ranked_gather_order_not_used": True,
            "all_qwen_layers_and_kv_heads_covered": True,
            "terminal_replay_consumed_exactly_once": True,
            "same_mask_dense_and_route_a_mask_digests_match": True,
            "fp32_same_mask_guard_enforced": True,
            "executed_dtype_ulp_breaches_recorded_not_selected": True,
            "p1_p64_hot_packed_state_matches_functional_route_a": True,
            "p3_prefill_tail_probes_do_not_replace_model_prefill_attention": True,
            "generated_token_forward_count_is_zero": True,
            "snapkv_native_cache_replacement_used": False,
            "route_a_predictor_scored_online": False,
        },
        "outcomes": {
            "same_mask_dense_vs_route_a_prefill_tail_probe": {
                "p1_p64_state_cross_check": {"page_tokens": 64}
            }
        },
    }
    (p3_dir / P3_MANIFEST_NAME).write_text(json.dumps(p3), encoding="utf-8")
    return p0_dir, p1_path, p3_dir


def test_p2_binds_all_prerequisite_hashes_and_keeps_missing_fields_nonzero(tmp_path):
    p0_dir, p1_path, p3_dir = _write_completed_inputs(tmp_path)
    p0, decisions, p1, p3 = load_p2_inputs(p0_dir, p1_path, p3_dir)
    descriptor = build_descriptor(p0, decisions, p1, p3)
    statuses = {field["name"]: field for field in descriptor["field_statuses"]}
    assert descriptor["summary"]["unavailable_values_are_not_zero"] is True
    assert statuses["terminal_per_identity_action"]["status"] == "available"
    assert statuses["pending_arrival_service_and_occupancy"] == {
        "name": "pending_arrival_service_and_occupancy",
        "status": "unavailable",
        "evidence_classification": "not provided by the one-shot prefill source",
        "value": None,
        "evidence": "P3's terminal materialization has zero pending state; that is not evidence that a decode lifecycle has zero pending arrivals or occupancy.",
    }
    assert descriptor["eligibility"]["scheduler_or_backpressure_contract"] is False


def test_p2_rejects_tampered_p3_p1_hash(tmp_path):
    p0_dir, p1_path, p3_dir = _write_completed_inputs(tmp_path)
    p3_path = p3_dir / P3_MANIFEST_NAME
    p3 = json.loads(p3_path.read_text())
    p3["input_provenance"]["p1_report_sha256"] = "tampered"
    p3_path.write_text(json.dumps(p3), encoding="utf-8")
    with pytest.raises(ValueError, match="P3 P1 report SHA-256"):
        load_p2_inputs(p0_dir, p1_path, p3_dir)


def test_p2_rejects_p3_that_claims_native_cache_replacement(tmp_path):
    p0_dir, p1_path, p3_dir = _write_completed_inputs(tmp_path)
    p3_path = p3_dir / P3_MANIFEST_NAME
    p3 = json.loads(p3_path.read_text())
    p3["observational_guards"]["snapkv_native_cache_replacement_used"] = True
    p3_path.write_text(json.dumps(p3), encoding="utf-8")
    with pytest.raises(ValueError, match="native cache replacement"):
        load_p2_inputs(p0_dir, p1_path, p3_dir)
