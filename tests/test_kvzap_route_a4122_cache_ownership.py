import pytest

from tools.run_kvzap_route_a4122_cache_ownership_gate import selected_head_coverage


def test_selected_head_coverage_requires_exactly_one_matching_head():
    coverage = {"heads": [{"kv_head": 6, "ever_pending": True}]}
    assert selected_head_coverage(coverage, 6) == {"kv_head": 6, "ever_pending": True}


@pytest.mark.parametrize("coverage", [{"heads": []}, {"heads": [{"kv_head": 6}, {"kv_head": 6}]}])
def test_selected_head_coverage_rejects_missing_or_duplicate_head(coverage):
    with pytest.raises(AssertionError, match="exactly one"):
        selected_head_coverage(coverage, 6)
