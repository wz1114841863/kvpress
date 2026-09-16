import gzip
import hashlib
import json

import pytest

from tools.analyze_kvzap_route_a436_llama31_microevent_quantum_sweep import (
    SOURCE_SCHEMA,
    load_source,
    summarize,
)


def test_a436_summary_is_logical_state_only():
    events = [
        {"phase": "prefill", "input_token_count": 64, "heads": [{"pending_tokens_after_service": 4, "admitted_tokens": 2, "packed_tokens_after_service": 2, "packed_full_page_count_after_service": 0}]},
        {"phase": "decode", "input_token_count": 1, "heads": [{"pending_tokens_after_service": 1, "admitted_tokens": 1, "packed_tokens_after_service": 3, "packed_full_page_count_after_service": 0}]},
    ]
    result = summarize(events)
    assert result["logical_event_count"] == 2
    assert result["max_prefill_event_tokens"] == 64
    assert result["admitted_tokens_total"] == 3


def test_a436_source_rejects_timed_event(tmp_path):
    trace_path = tmp_path / "trace.jsonl.gz"
    with gzip.open(trace_path, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps({"layer": 0, "start_position": 0, "end_position": 3, "timestamps_recorded": True, "phase": "prefill", "input_token_count": 4, "heads": []}) + "\n")
    trace_sha = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    source = {
        "schema_version": SOURCE_SCHEMA, "status": "complete",
        "config": {"preset": "retrieval", "admission_budget": 1, "prefill_maturity_chunk_tokens": 64, "fixed_new_tokens": 8},
        "provenance": {"m0_manifest_sha256": "m0", "m1_manifest_sha256": "m1", "m51_report_sha256": "m51", "m41_non_strict_summarization_context_retained": True},
        "observational_guards": {"m0_m1_m51_hash_bound": True, "m41_non_strict_summarization_context_retained": True, "all_32_layers_all_8_kv_heads_covered_dense_trace_off_and_microevent": True, "online_dense_mask_replayed_exactly_once_by_both_route_a_paths": True, "same_mask_numerical_guard_work_executed_by_all_paths": True, "record_only_ulp_context_not_a_strict_pass": True, "fixed_dense_token_trajectory_forced_in_route_a": True, "trace_off_route_a_tokens_equal_trace_on_microevent": True, "prefill_micro_event_trace_enabled": True, "logical_events_have_no_timestamps": True, "fake_key_attention_used": False, "model_cache_mutated_by_backend": False},
        "lifecycle_transition_trace": {"path": trace_path.name, "sha256": trace_sha, "prefill_maturity_chunk_tokens": 64},
    }
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="non-contiguous or timed"):
        load_source(source_path, m0_sha256="m0", m1_sha256="m1", m51_sha256="m51")
