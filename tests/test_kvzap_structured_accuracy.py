from tools.run_kvzap_structured_accuracy import f1, rouge_l


def test_screening_f1_normalizes_articles_and_punctuation():
    assert f1("The answer!", "answer") == 1.0
    assert f1("wrong", "answer") == 0.0


def test_screening_rouge_l_uses_lcs_f1():
    assert rouge_l("a b c", "a x c") == 2 / 3
    assert rouge_l("", "") == 1.0
