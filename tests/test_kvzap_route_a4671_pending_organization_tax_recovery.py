from tools.analyze_kvzap_route_a4671_pending_organization_tax_recovery import (
    capacity_recovery,
    management_inventory,
    unweighted_exposure_ratio,
)


def _variant(*, terminal_pending: int = 0) -> dict:
    return {
        "global_B_final": terminal_pending,
        "activation_logical_operation_and_concurrency_summary": [
            {"layer": 0, "private_enqueue_token_units": 3, "private_enqueue_segment_count": 1, "active_spans_after_activation": 1},
        ],
        "per_layer_append_opportunity_logical_operation_and_concurrency_summary": [
            {
                "layer": 0,
                "shared_enqueue_token_units": 2,
                "cross_source_dequeue_head_opportunity_count": 1,
                "max_oldest_source_comparison_count_one_opportunity": 2,
                "max_cross_source_switch_count_one_opportunity": 1,
                "max_active_spans_after_arrival": 2,
                "max_heads_with_shared_after_arrival": 1,
                "max_heads_with_two_sources_after_arrival": 1,
                "max_max_active_spans_one_head_after_arrival": 2,
            },
        ],
        "global_logical_queue_operations": {
            "private_enqueue_token_units": 3,
            "shared_enqueue_token_units": 2,
            "private_dequeue_token_units": 3,
            "shared_dequeue_token_units": 2 - terminal_pending,
            "private_enqueue_segment_count": 1,
            "shared_enqueue_segment_count": 1,
            "private_release_segment_count": 1,
            "shared_release_segment_count": 1 - int(bool(terminal_pending)),
            "oldest_source_comparison_count": 2,
            "cross_source_switch_count": 1,
        },
    }


def test_a4671_capacity_recovery_is_per_layer_and_never_selects_physical_capacity():
    result = capacity_recovery(head_local_cmin=100, organization_cmin=60, layer_count=4)
    assert result["recovered_logical_tokens_per_layer"] == 40
    assert result["recovered_fraction_of_head_local_Cmin"] == 0.4
    assert result["recovered_logical_token_layers"] == 160


def test_a4671_management_inventory_keeps_activation_and_append_distinct_with_conservation():
    inventory = management_inventory(_variant())
    assert inventory["logical_source_affiliation_creation"]["activation_enqueue_token_units"] == 3
    assert inventory["logical_source_affiliation_creation"]["append_enqueue_token_units"] == 2
    assert inventory["logical_unit_conservation"] == {
        "total_enqueue_token_units": 5,
        "total_dequeue_token_units": 5,
        "terminal_pending_token_units": 0,
    }
    assert inventory["logical_cross_source_selection"]["oldest_source_comparison_count"] == 2


def test_a4671_prefix_inventory_can_retain_pending_without_failing_conservation():
    inventory = management_inventory(_variant(terminal_pending=1))
    assert inventory["logical_unit_conservation"]["total_dequeue_token_units"] == 4
    assert inventory["logical_unit_conservation"]["terminal_pending_token_units"] == 1


def test_a4671_unweighted_exposure_ratio_has_no_zero_event_surrogate():
    assert unweighted_exposure_ratio(recovered_logical_token_layers=32, event_count=4) == 8.0
    assert unweighted_exposure_ratio(recovered_logical_token_layers=32, event_count=0) is None
