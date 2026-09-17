import pytest

from tools.analyze_kvzap_route_a452_global_protection_controller_reconciliation import reconcile_workload


def source_row(pending):
    return {"activation_contract": {"deferred_activation_summary": {"layers": [
        {"layer": layer, "activation_event": {"heads": [{"pending_tokens_after_commit": value}]}}
        for layer, value in enumerate(pending)
    ]}}}


def a451_row(pending, protected):
    layers = []
    for layer, value in enumerate(pending):
        if layer in protected:
            layers.append({
                "layer": layer, "capacity_protection_committed": True,
                "mode_at_trace_end": "protected_full_kv", "protected_native_attention_calls": 2,
                "route_a_logical_state_next_position_at_end": 99 + layer,
                "capacity_protection_event": {
                    "boundary": "activation_commit_before_current_route_a_logical_append",
                    "aggregate_pending_tokens_at_transition": value, "pending_high_watermark": 1024,
                    "route_a_state_next_position_frozen": 99 + layer,
                },
            })
        else:
            layers.append({"layer": layer, "capacity_protection_committed": False, "mode_at_trace_end": "route_a_active", "capacity_protection_event": None})
    return {"protection_contract": {"forced_token_inputs_equal_full_kv": True, "execution_scope": "layer-local attention-hook primitive; not a request-global controller", "deferred_activation_summary": {"layers": layers}}}


def a450_row():
    return {"transition": {"boundary": "activation_commit_before_current_decode_append", "trigger_pending_max_across_layers": 1600, "trigger_layer_count_at_or_above_high_watermark": 2}}


def test_a452_reconciles_local_trigger_set_and_next_epoch_global_boundary():
    row = reconcile_workload(
        anchor="qwen3_8b", workload="retrieval", layer_count=3,
        source_row=source_row([500, 1200, 1600]), a450_row=a450_row(),
        a451_row=a451_row([500, 1200, 1600], {1, 2}),
    )
    contract = row["reconciled_request_global_controller_contract"]
    assert row["a451_actual_layer_local_primitive"]["protected_layer_indices"] == [1, 2]
    assert contract["first_trigger_observation_layer"] == 1
    assert contract["layers_completed_before_trigger_observation"] == 1
    assert contract["all_layer_global_protection_effective_boundary"] == "next_decode_epoch_after_completion_of_current_activation_epoch"
    assert contract["current_epoch_retroactive_reroute_permitted"] is False


def test_a452_rejects_actual_set_that_does_not_match_activation_threshold_set():
    with pytest.raises(ValueError, match="unexpected unprotected"):
        reconcile_workload(
            anchor="qwen3_8b", workload="retrieval", layer_count=3,
            source_row=source_row([500, 1200, 1600]), a450_row=a450_row(),
            a451_row=a451_row([500, 1200, 1600], {2}),
        )
