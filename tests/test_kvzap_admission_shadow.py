from types import SimpleNamespace

import torch

from kvpress.admission_shadow import PackedKVAdmissionShadow


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
