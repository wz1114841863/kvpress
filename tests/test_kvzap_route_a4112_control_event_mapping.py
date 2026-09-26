import pytest

from tools.validate_kvzap_route_a4112_control_event_mapping import mapping_contract, validate_lifecycle_events


def event(*, sequence=0, layer=0, start=0, phase="prefill", matured=3, admitted=2, count=129):
    before_pending = 1
    after_maturity = before_pending + matured
    after_service = after_maturity - admitted
    return {
        "logical_transition_sequence": sequence,
        "timestamps_recorded": False,
        "layer": layer,
        "phase": phase,
        "start_position": start,
        "end_position": start + count - 1,
        "input_token_count": count,
        "heads": [{
            "kv_head": 0,
            "hot_tokens_before": 128,
            "pending_tokens_before_maturity": before_pending,
            "matured_kept_tokens": matured,
            "matured_dropped_tokens": 1,
            "pending_tokens_after_maturity": after_maturity,
            "admitted_tokens": admitted,
            "pending_tokens_after_service": after_service,
            "packed_tokens_before": 5,
            "packed_tokens_after_service": 5 + admitted,
            "packed_page_count_after_service": 1,
            "packed_full_page_count_after_service": 0,
            "packed_tail_tokens_after_service": 5 + admitted,
        }],
    }


def test_a4112_accepts_prefill_armed_conserved_lifecycle_and_reports_software_only_fields():
    result = validate_lifecycle_events([event()], selected_layers=[0], selected_heads={0: [0]}, window=128)
    assert result["prefill_trace_armed_before_pending_creation"] is True
    assert result["software_maturity_arrival_tokens"] == 3
    assert result["software_pending_after_maturity_max_per_head"] == 4
    contract = mapping_contract()
    assert contract["modeled_arrival"]["mapping"] == "direct_software_scalar"
    assert contract["modeled_micro_op_done"]["mapping"] == "no_direct_software_correspondent"


def test_a4112_rejects_trace_that_starts_after_prefill():
    with pytest.raises(ValueError, match="not armed before prefill"):
        validate_lifecycle_events([event(start=1, phase="decode")], selected_layers=[0], selected_heads={0: [0]}, window=128)


def test_a4112_rejects_missing_prefill_pending_creation():
    with pytest.raises(ValueError, match="prefill-created retained pending"):
        validate_lifecycle_events([event(matured=0, admitted=0)], selected_layers=[0], selected_heads={0: [0]}, window=128)
