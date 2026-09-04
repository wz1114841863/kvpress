import pytest

from tools.run_kvzap_route_a4124_multitoken_bridge_gate import assert_required_packed_page_coverage


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
