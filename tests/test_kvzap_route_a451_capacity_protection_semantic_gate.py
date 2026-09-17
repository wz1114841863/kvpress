import json
from pathlib import Path

from tools.run_kvzap_route_a451_capacity_protection_semantic_gate import read_a450_row, validate_protection


def test_a451_declares_offline_mode_before_hf_library_imports():
    source = Path("tools/run_kvzap_route_a451_capacity_protection_semantic_gate.py").read_text(encoding="utf-8")
    assert source.index('os.environ["HF_HUB_OFFLINE"] = "1"') < source.index("import transformers")
    assert source.index('os.environ["TRANSFORMERS_OFFLINE"] = "1"') < source.index("from huggingface_hub import snapshot_download")


def test_a451_requires_hash_bound_a450_c1024_witness(tmp_path):
    report = tmp_path / "a450.json"
    report.write_text(json.dumps({
        "schema_version": "kvzap-route-a450-capacity-protection-boundary-replay-1.0",
        "status": "complete",
        "input_artifacts": {"qwen3_8b": {"report_sha256": "anchor-sha"}},
        "replay_rows": [{
            "anchor": "qwen3_8b", "workload": "retrieval",
            "policy": {"pending_high_watermark": 1024},
            "transition": {"boundary": "activation_commit_before_current_decode_append"},
        }],
    }), encoding="utf-8")
    row = read_a450_row(report, anchor="qwen3_8b", workload="retrieval", anchor_sha256="anchor-sha", watermark=1024)
    assert row["transition"]["boundary"] == "activation_commit_before_current_decode_append"


def test_a451_accepts_frozen_protected_layer_and_active_peer():
    protected_event = {
        "aggregate_pending_tokens_at_transition": 1024,
        "reentry_permitted": False,
        "native_cache_mutated_or_freed_by_transition": False,
        "post_transition_route_a_logical_admission_or_drop": "disabled",
        "route_a_state_next_position_frozen": 133,
    }
    summary = {"layers": [
        {"layer": 0, "activation_committed": True, "activation_event": {}, "native_cache_mutated_or_freed": False,
         "mode_at_trace_end": "protected_full_kv", "capacity_protection_committed": True,
         "capacity_protection_event": protected_event, "protected_native_attention_calls": 2,
         "route_a_logical_state_next_position_at_end": 133},
        {"layer": 1, "activation_committed": True, "activation_event": {}, "native_cache_mutated_or_freed": False,
         "mode_at_trace_end": "route_a_active", "capacity_protection_committed": False,
         "capacity_protection_event": None, "protected_native_attention_calls": 0,
         "route_a_logical_state_next_position_at_end": 134},
    ]}
    guard = validate_protection(summary, layers=(0, 1), watermark=1024, workload="retrieval")
    assert guard["protected_layer_count"] == 1
    assert guard["still_route_a_active_layers"] == [1]
