from types import SimpleNamespace
import json

import torch

from kvpress.admission_shadow import CalibratedAdmissionShadow, LayerBatchAdmissionShadow, PackedKVAdmissionShadow
from tools.run_kvzap_admission_shadow import validate_expected_a2
from tools.validate_kvzap_admission_shadow import validate_deferred_replay_positions, validate_hybrid_head_progress


def test_shadow_reads_kv_without_mutating_source_and_packs_mature_keep_positions():
    keys = torch.arange(12, dtype=torch.float32).reshape(1, 2, 3, 2)
    values = keys + 100
    source_keys, source_values = keys.clone(), values.clone()
    cache = SimpleNamespace(layers=[SimpleNamespace(keys=keys, values=values)])
    shadow = PackedKVAdmissionShadow(request_id="unit", layers=1, heads=2, window=2, page_tokens=2, expected_kv_bytes_per_token=16, record_tasks=True)
    rows = [
        {"layer": 0, "kv_head": 0, "cold_admitted_tokens": 1},
        {"layer": 0, "kv_head": 1, "cold_admitted_tokens": 0},
    ]
    scores = torch.tensor([[0.0, -1.0, 0.0], [-1.0, 0.0, 0.0]])
    shadow.observe(layer=0, score_start=0, scores=scores, threshold=-0.5, model_call=0, phase="context_prefill", kwargs={"past_key_values": cache}, lifecycle_rows=rows)
    shadow.finalize()
    assert torch.equal(keys, source_keys)
    assert torch.equal(values, source_values)
    tasks = shadow._tasks
    assert [task["admitted_tokens"] for task in tasks] == [1, 0]
    assert tasks[0]["packed_kv_bytes"] == 16
    final = shadow.final_rows()
    head0 = next(row for row in final if row["kv_head"] == 0)
    assert head0["cold_logical_tokens"] == 1
    assert head0["position_sum"] == 0


def test_layer_batch_shadow_emits_one_batch_for_all_heads():
    keys = torch.arange(12, dtype=torch.float32).reshape(1, 2, 3, 2)
    cache = SimpleNamespace(layers=[SimpleNamespace(keys=keys, values=keys + 100)])
    shadow = LayerBatchAdmissionShadow(request_id="unit", layers=1, heads=2, window=2, page_tokens=2, expected_kv_bytes_per_token=16, record_tasks=True)
    rows = [{"layer": 0, "kv_head": 0, "cold_admitted_tokens": 1}, {"layer": 0, "kv_head": 1, "cold_admitted_tokens": 0}]
    shadow.observe(layer=0, score_start=0, scores=torch.tensor([[0.0, -1.0, 0.0], [-1.0, 0.0, 0.0]]), threshold=-0.5, model_call=0, phase="context_prefill", kwargs={"past_key_values": cache}, lifecycle_rows=rows)
    shadow.finalize()
    assert len(shadow._tasks) == 1
    assert shadow._tasks[0]["active_head_count"] == 1
    assert shadow._tasks[0]["admitted_tokens"] == 1
    assert len(shadow._head_tasks) == 2


def test_v2_batch_uses_common_planning_scope_and_zero_delay_packs_immediately():
    keys = torch.arange(12, dtype=torch.float32).reshape(1, 2, 3, 2)
    cache = SimpleNamespace(layers=[SimpleNamespace(keys=keys, values=keys + 100)])
    shadow = CalibratedAdmissionShadow(request_id="unit", layers=1, heads=2, window=2, page_tokens=2, expected_kv_bytes_per_token=16, record_tasks=True, submission_mode="per_layer_batch_v2", deferred_decode_steps=0)
    rows = [{"layer": 0, "kv_head": 0, "cold_admitted_tokens": 1}, {"layer": 0, "kv_head": 1, "cold_admitted_tokens": 0}]
    shadow.observe(layer=0, score_start=0, scores=torch.tensor([[0.0, -1.0, 0.0], [-1.0, 0.0, 0.0]]), threshold=-0.5, model_call=0, phase="context_prefill", kwargs={"past_key_values": cache}, lifecycle_rows=rows)
    shadow.finalize()
    task = shadow._v2_tasks[0]
    assert task["planning_host_us"] >= 0
    assert task["packed_admitted_tokens"] == task["decided_admitted_tokens"] == 1
    assert task["member_head_count"] == 2


def test_v2_budget_caps_layer_flush_and_retains_pending_fifo():
    keys = torch.arange(12, dtype=torch.float32).reshape(1, 2, 3, 2)
    cache = SimpleNamespace(layers=[SimpleNamespace(keys=keys, values=keys + 100)])
    shadow = CalibratedAdmissionShadow(request_id="unit", layers=1, heads=2, window=2, page_tokens=2, expected_kv_bytes_per_token=16, record_tasks=True, submission_mode="per_layer_batch_v2", deferred_decode_steps=0, admission_flush_token_budget=1, record_hybrid_head_progress=True)
    rows = [{"layer": 0, "kv_head": 0, "cold_admitted_tokens": 1}, {"layer": 0, "kv_head": 1, "cold_admitted_tokens": 1}]
    shadow.observe(layer=0, score_start=0, scores=torch.zeros((2, 3)), threshold=-0.5, model_call=0, phase="context_prefill", kwargs={"past_key_values": cache}, lifecycle_rows=rows)
    shadow.finalize()
    task = shadow._v2_tasks[0]
    assert task["packed_admitted_tokens"] == 1
    assert task["pending_tokens_after"] == 1
    assert shadow.summary()["pending_tokens_at_end"] == 1
    assert len(shadow._hybrid_head_progress) == 2
    assert sum(row["packed_admitted_tokens"] for row in shadow._hybrid_head_progress) == 1
    assert sum(row["pending_tokens_after"] for row in shadow._hybrid_head_progress) == 1


def test_v2_hybrid_head_progress_writes_separate_untimed_csv(tmp_path):
    keys = torch.arange(12, dtype=torch.float32).reshape(1, 2, 3, 2)
    cache = SimpleNamespace(layers=[SimpleNamespace(keys=keys, values=keys + 100)])
    shadow = CalibratedAdmissionShadow(request_id="unit", layers=1, heads=2, window=2, page_tokens=2, expected_kv_bytes_per_token=16, record_tasks=True, submission_mode="per_layer_batch_v2", deferred_decode_steps=0, admission_flush_token_budget=1, record_hybrid_head_progress=True)
    rows = [{"layer": 0, "kv_head": 0, "cold_admitted_tokens": 1}, {"layer": 0, "kv_head": 1, "cold_admitted_tokens": 1}]
    shadow.observe(layer=0, score_start=0, scores=torch.zeros((2, 3)), threshold=-0.5, model_call=0, phase="context_prefill", kwargs={"past_key_values": cache}, lifecycle_rows=rows)
    output = tmp_path / "out"
    output.mkdir()
    paths = shadow.write(output)
    assert paths["hybrid_head_progress"].is_file()
    assert len(paths["hybrid_head_progress"].read_text(encoding="utf-8").splitlines()) == 3


def test_v3_deferred_replay_positions_write_retained_token_positions(tmp_path):
    keys = torch.arange(12, dtype=torch.float32).reshape(1, 2, 3, 2)
    cache = SimpleNamespace(layers=[SimpleNamespace(keys=keys, values=keys + 100)])
    shadow = CalibratedAdmissionShadow(request_id="unit", layers=1, heads=2, window=2, page_tokens=2, expected_kv_bytes_per_token=16, record_tasks=True, submission_mode="per_layer_batch_v2", deferred_decode_steps=0, admission_flush_token_budget=1, record_hybrid_head_progress=True, record_deferred_replay_positions=True)
    rows = [{"layer": 0, "kv_head": 0, "cold_admitted_tokens": 1}, {"layer": 0, "kv_head": 1, "cold_admitted_tokens": 0}]
    shadow.observe(layer=0, score_start=0, scores=torch.tensor([[0.0, -1.0, 0.0], [-1.0, 0.0, 0.0]]), threshold=-0.5, model_call=0, phase="context_prefill", kwargs={"past_key_values": cache}, lifecycle_rows=rows)
    output = tmp_path / "out"
    output.mkdir()
    paths = shadow.write(output)
    assert paths["deferred_replay_positions"].is_file()
    assert "unit,0,context_prefill,0,0,0" in paths["deferred_replay_positions"].read_text(encoding="utf-8")


def test_hybrid_progress_accepts_a_deferred_backlog_flush():
    lifecycle = [
        {"model_call": "0", "layer": "0", "kv_head": "0", "cold_admitted_tokens": "2"},
        {"model_call": "1", "layer": "0", "kv_head": "0", "cold_admitted_tokens": "0"},
    ]
    progress = [
        {"model_call": "0", "layer": "0", "kv_head": "0", "decided_admitted_tokens": "2", "packed_admitted_tokens": "0", "pending_tokens_before": "0", "pending_tokens_after": "2", "cold_logical_tokens_after": "0", "cold_allocated_slots_after": "0", "cold_page_count_after": "0"},
        {"model_call": "1", "layer": "0", "kv_head": "0", "decided_admitted_tokens": "0", "packed_admitted_tokens": "2", "pending_tokens_before": "2", "pending_tokens_after": "0", "cold_logical_tokens_after": "2", "cold_allocated_slots_after": "2", "cold_page_count_after": "1"},
    ]
    tasks = [
        {"model_call": "0", "layer": "0", "member_head_count": "1", "packed_admitted_tokens": "0", "pending_tokens_after": "2"},
        {"model_call": "1", "layer": "0", "member_head_count": "1", "packed_admitted_tokens": "2", "pending_tokens_after": "0"},
    ]
    validate_hybrid_head_progress(progress, lifecycle, tasks)


def test_deferred_replay_positions_match_retained_decision_count_and_order():
    progress = [
        {"model_call": "0", "layer": "0", "kv_head": "0", "decided_admitted_tokens": "2"},
        {"model_call": "0", "layer": "0", "kv_head": "1", "decided_admitted_tokens": "0"},
    ]
    positions = [
        {"model_call": "0", "layer": "0", "kv_head": "0", "position": "3"},
        {"model_call": "0", "layer": "0", "kv_head": "0", "position": "7"},
    ]
    validate_deferred_replay_positions(positions, progress)


def test_expected_a2_binding_rejects_different_request_content(tmp_path):
    request = {"request_id": "r", "context": "c", "question": "q"}
    args = SimpleNamespace(model_name="m", model_revision="mr", predictor_name="p", predictor_revision="pr", threshold=-4.0, window_size=128, page_tokens=64, kv_bytes_per_token=512, max_new_tokens=8)
    from tools.export_kvzap_predictor_trace import stable_hash
    manifest = {"schema_version": "kvzap-route-a2-readonly-lifecycle-1.0", "request_id": "r", "model": "m", "model_revision": "mr", "predictor_checkpoint": "p", "predictor_revision": "pr", "threshold": -4.0, "sliding_window": 128, "page_tokens": 64, "kv_bytes_per_layer_head_token": 512, "max_new_tokens": 8, "config": {"request_content_hash": stable_hash({"context": "c", "question": "q"})}, "trace_equivalence": {"normal_observer_record_answer_sha256": "a" * 64}}
    (tmp_path / "lifecycle_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_expected_a2(tmp_path, args, request) == "a" * 64
