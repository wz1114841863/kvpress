from argparse import Namespace

import pytest

from tools.run_kvzap_route_a4129_multilayer_continuation_diagnostic import any_route_a_state, require_state_coverage


def coverage(*, pending: bool, multi_page: bool, full_page: bool, tail: int):
    return {
        "layers": [
            {"layer": 0, "heads": [{"kv_head": 0, "ever_pending": pending, "ever_multi_page_packed": multi_page, "ever_sealed_packed_page": full_page, "max_packed_tail_tokens": tail}]},
            {"layer": 18, "heads": [{"kv_head": 0, "ever_pending": False, "ever_multi_page_packed": False, "ever_sealed_packed_page": False, "max_packed_tail_tokens": 0}]},
        ]
    }


def test_aggregate_state_coverage_is_allowed_in_any_selected_layer_head():
    observed = coverage(pending=False, multi_page=True, full_page=True, tail=63)
    assert any_route_a_state(observed, "ever_multi_page_packed")
    assert any_route_a_state(observed, "ever_sealed_packed_page")
    assert any_route_a_state(observed, "max_packed_tail_tokens")
    assert not any_route_a_state(observed, "ever_pending")


def test_requested_multilayer_state_guard_rejects_missing_pending_only():
    args = Namespace(require_any_pending=True, require_any_multi_page_packed=False, require_any_full_packed_page=False, require_any_tail_packed_page=False)
    with pytest.raises(AssertionError, match="pending staging"):
        require_state_coverage(coverage=coverage(pending=False, multi_page=False, full_page=False, tail=0), args=args)
    require_state_coverage(coverage=coverage(pending=True, multi_page=False, full_page=False, tail=0), args=args)
