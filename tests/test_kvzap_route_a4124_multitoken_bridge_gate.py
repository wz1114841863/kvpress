import pytest

from tools.run_kvzap_route_a4124_multitoken_bridge_gate import (
    assert_any_head_coverage,
    assert_complete_selected_head_bridge_coverage,
    assert_required_packed_page_coverage,
    parse_target_kv_head,
)


def test_target_kv_head_parser_accepts_all_or_a_nonnegative_index():
    assert parse_target_kv_head("all") is None
    assert parse_target_kv_head("6") == 6
    with pytest.raises(Exception, match="nonnegative"):
        parse_target_kv_head("-1")


def test_required_packed_page_coverage_accepts_observed_full_tail_and_multi_page_states():
    coverage = {
        "heads": [{
            "kv_head": 6,
            "ever_multi_page_packed": True,
            "ever_sealed_packed_page": True,
            "max_packed_tail_tokens": 3,
        }],
    }
    assert_required_packed_page_coverage(
        coverage,
        require_multi_page_packed=True,
        require_full_packed_page=True,
        require_tail_packed_page=True,
    )


@pytest.mark.parametrize(
    ("field", "requirement"),
    [
        ("ever_multi_page_packed", "multi-page packed coverage"),
        ("ever_sealed_packed_page", "sealed full packed-page coverage"),
        ("max_packed_tail_tokens", "nonempty packed-tail coverage"),
    ],
)
def test_required_packed_page_coverage_rejects_unobserved_requested_state(field, requirement):
    coverage = {
        "heads": [{
            "kv_head": 6,
            "ever_multi_page_packed": True,
            "ever_sealed_packed_page": True,
            "max_packed_tail_tokens": 3,
        }],
    }
    coverage["heads"][0][field] = False if field != "max_packed_tail_tokens" else 0
    with pytest.raises(AssertionError, match=requirement):
        assert_required_packed_page_coverage(
            coverage,
            require_multi_page_packed=True,
            require_full_packed_page=True,
            require_tail_packed_page=True,
        )


def test_all_head_bridge_coverage_requires_each_selected_head_and_each_question_token():
    coverage = {"heads": [{"kv_head": 0, "comparison_count": 22}, {"kv_head": 1, "comparison_count": 22}]}
    assert_complete_selected_head_bridge_coverage(
        coverage,
        expected_selected_kv_heads=(0, 1),
        question_token_count=22,
        label="Route-A",
    )
    coverage["heads"][1]["comparison_count"] = 21
    with pytest.raises(AssertionError, match="every question token"):
        assert_complete_selected_head_bridge_coverage(
            coverage,
            expected_selected_kv_heads=(0, 1),
            question_token_count=22,
            label="Route-A",
        )


def test_any_head_coverage_does_not_require_low_retention_heads_to_have_a_page():
    coverage = {"heads": [{"kv_head": 0, "ever_pending": False}, {"kv_head": 6, "ever_pending": True}]}
    assert_any_head_coverage(coverage, field="ever_pending", label="pending staging")
    coverage["heads"][1]["ever_pending"] = False
    with pytest.raises(AssertionError, match="any-head pending staging"):
        assert_any_head_coverage(coverage, field="ever_pending", label="pending staging")
