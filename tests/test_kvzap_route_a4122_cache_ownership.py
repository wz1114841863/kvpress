import pytest

from tools.run_kvzap_route_a4122_cache_ownership_gate import generated_output_relation, selected_head_coverage


def test_selected_head_coverage_requires_exactly_one_matching_head():
    coverage = {"heads": [{"kv_head": 6, "ever_pending": True}]}
    assert selected_head_coverage(coverage, 6) == {"kv_head": 6, "ever_pending": True}


@pytest.mark.parametrize("coverage", [{"heads": []}, {"heads": [{"kv_head": 6}, {"kv_head": 6}]}])
def test_selected_head_coverage_rejects_missing_or_duplicate_head(coverage):
    with pytest.raises(AssertionError, match="exactly one"):
        selected_head_coverage(coverage, 6)


def test_generated_output_relation_records_first_token_difference_without_token_text():
    relation = generated_output_relation("dense", [1, 2, 3], "route", [1, 9])
    assert relation == {
        "answer_sha256_equal": False,
        "generated_token_ids_equal": False,
        "dense_generated_token_count": 3,
        "route_a_generated_token_count": 2,
        "first_generated_token_difference": {"index": 1, "dense_token_id": 2, "route_a_token_id": 9},
    }
