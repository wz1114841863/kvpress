from argparse import Namespace

import pytest

from tools.run_kvzap_route_a4129_multilayer_continuation_diagnostic import any_route_a_state, assert_entrypoint_contract, assert_scope, assert_scope_selector, require_state_coverage, resolve_diagnostic_layers


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


def test_layer_scope_resolves_all_and_rejects_non_all_a4130_scope():
    assert resolve_diagnostic_layers(["all"], 4) == (0, 1, 2, 3)
    assert resolve_diagnostic_layers(["0", "2"], 4) == (0, 2)
    with pytest.raises(ValueError, match="cannot be combined"):
        resolve_diagnostic_layers(["all", "0"], 4)
    assert_scope((0, 1, 2, 3), layer_count=4, scope="all_layers")
    with pytest.raises(ValueError, match="requires --target-layers all"):
        assert_scope((0, 2), layer_count=4, scope="all_layers")
    assert_scope_selector(["all"], scope="all_layers")
    with pytest.raises(ValueError, match="literal"):
        assert_scope_selector(["0", "1", "2", "3"], scope="all_layers")


def test_entrypoint_contract_pins_budget_and_required_page_state_flags():
    args = Namespace(admission_budget=512, require_any_multi_page_packed=True, require_any_full_packed_page=True, require_any_tail_packed_page=True)
    assert_entrypoint_contract(args=args, phase="A4.1.2.14", required_admission_budget=512, required_state_flags=("require_any_multi_page_packed", "require_any_full_packed_page", "require_any_tail_packed_page"))
    with pytest.raises(ValueError, match="admission-budget 512"):
        assert_entrypoint_contract(args=Namespace(**{**vars(args), "admission_budget": 1}), phase="A4.1.2.14", required_admission_budget=512, required_state_flags=())
    with pytest.raises(ValueError, match="require-any-tail-packed-page"):
        assert_entrypoint_contract(args=Namespace(**{**vars(args), "require_any_tail_packed_page": False}), phase="A4.1.2.14", required_admission_budget=512, required_state_flags=("require_any_tail_packed_page",))
