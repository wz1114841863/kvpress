from tools.analyze_kvzap_route_a4131_payload_organization import (
    KV_BYTES,
    attention_envelope,
    candidates,
    lifecycle_envelope,
    packing_envelope,
)


def test_payload_access_and_three_candidates_keep_mapping_boundaries():
    heads = []
    for head in range(8):
        admitted = 1 if head == 0 else 0
        heads.append({"kv_head": head, "pending_tokens_after_maturity": admitted, "matured_kept_tokens": admitted, "admitted_tokens": admitted})
    lifecycle = [{"layer": layer, "admitted_tokens_total": 1, "heads": heads} for layer in range(36)]
    final = {"layers": [{"layer": layer, "heads": [{"kv_head": head, "packed_tokens": 1 if head == 0 else 0, "packed_page_count": 1 if head == 0 else 0, "packed_full_page_count": 0, "packed_tail_tokens": 1 if head == 0 else 0} for head in range(8)]} for layer in range(36)]}
    manifest = {"outcomes": {"external_storage_trace_on": {"final_state": final}}}
    life = lifecycle_envelope(lifecycle, manifest)
    assert life["admitted_retained_tokens"] == 36
    assert life["isolated_per_layer_kv_head_pending_provision_tokens"] == 36
    assert packing_envelope(life)["final_packed_page_payload_capacity_bytes"] == 36 * 64 * KV_BYTES

    payload = [{"layer": layer, "kv_head": 0, "query_head": 0, "cache_position": 1, "phase": "decode", "source_decisions": [{"source": "hot", "record_count": 128}, {"source": "pending", "record_count": 1}, {"source": "packed", "record_count": 9}]} for layer in range(36)]
    attention = attention_envelope(payload)
    assert attention["direct_logical_cold_kv_token_visits"] == 360
    assert attention["deterministic_merge_interface"]["additional_nonempty_source_partials_beyond_first"] == 72
    rows = candidates(life, attention, lifecycle)
    assert [row["candidate"][:2] for row in rows] == ["P1", "P2", "P3"]
    assert rows[0]["declared_admission_movement"]["total_declared_hbm_bytes"] == 3 * 36 * KV_BYTES
    assert rows[1]["declared_attention_mapping"]["total_declared_hbm_read_bytes"] == 36 * 9 * KV_BYTES
