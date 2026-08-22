import pytest

from tools.run_kvzap_structured_accuracy import f1, rouge_l, select_rows


def test_screening_f1_normalizes_articles_and_punctuation():
    assert f1("The answer!", "answer") == 1.0
    assert f1("wrong", "answer") == 0.0


def test_screening_rouge_l_uses_lcs_f1():
    assert rouge_l("a b c", "a x c") == 2 / 3
    assert rouge_l("", "") == 1.0


def test_explicit_request_ids_preserve_cli_order():
    rows = [{"request_id": "first"}, {"request_id": "second"}, {"request_id": "third"}]
    assert [row["request_id"] for row in select_rows(rows, ["third", "first"], 1)] == ["third", "first"]


def test_explicit_request_ids_reject_unknown_or_duplicate_ids():
    rows = [{"request_id": "known"}]
    with pytest.raises(ValueError, match="Unknown"):
        select_rows(rows, ["missing"], 1)
    with pytest.raises(ValueError, match="duplicates"):
        select_rows(rows, ["known", "known"], 1)
