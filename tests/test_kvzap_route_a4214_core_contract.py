from tools.close_kvzap_route_a4214_core_contract import qwen_descriptor


def test_descriptor_keeps_qwen_group_width_separate_from_core_contract():
    a4200 = {"contract": {"contract_scope": {"model": "Qwen", "model_revision": "m", "predictor": "p", "predictor_revision": "r", "threshold": -4, "hot_window_tokens": 128, "page_tokens": 64, "admission_budget_retained_tokens_per_layer_call": 512, "observed_layer_count": 1, "observed_kv_head_count": 1}}}
    a428 = {"per_workload": {"w": {"actual_policy_decode_calls": 2, "summary": {"event_count": 4, "source_combination_fractions": {}, "fan_in_fractions": {}, "packed_page_witness_distribution": {}}}}}
    a4212 = {"per_workload": {"w": {"summary": {"forward_epoch_count": 1, "layer_dispatch_epoch_count": 1}}}}
    a4213 = {"per_workload": {"w": {"summary": {"query_heads_per_kv_head_group_histogram": {"4": 1}, "independent_source_dispatch_control_units_total": 8, "shared_kv_head_group_source_dispatch_control_units_total": 2, "dispatch_control_units_elided_total": 6, "partial_softmax_state_instances_unchanged": 4, "online_merge_instances_unchanged": 4}}}}
    descriptor = qwen_descriptor(a4200, a428, a4212, a4213)
    assert descriptor["qwen_specific_group_width_values"] == [4]
    assert descriptor["workload_descriptor"]["w"]["per_query_state_and_merge_instances"]["online_merge"] == 4
