import torch

from tools.run_kvzap_route_a4123_first_decode_logits_diagnostic import logit_summary, paired_logit_relation


def test_finite_logit_summary_is_bounded_and_reports_margin():
    summary = logit_summary(torch.tensor([1.0, 3.0, 2.0]), top_k=2)
    assert summary["all_finite"] is True
    assert summary["argmax_token_id"] == 1
    assert summary["top_tokens"] == [{"token_id": 1, "logit": 3.0}, {"token_id": 2, "logit": 2.0}]
    assert summary["top1_top2_margin"] == 1.0


def test_nonfinite_logit_summary_preserves_argmax_but_refuses_topk_interpretation():
    summary = logit_summary(torch.tensor([float("nan"), 2.0]), top_k=2)
    assert summary["all_finite"] is False
    assert summary["nan_count"] == 1
    assert summary["top_tokens"] is None


def test_paired_logit_relation_requires_finite_values_for_difference():
    assert paired_logit_relation(torch.tensor([1.0, 2.0]), torch.tensor([1.0, 3.0])) == {"same_shape": True, "both_all_finite": True, "argmax_token_id_equal": True, "max_abs_difference": 1.0}
    relation = paired_logit_relation(torch.tensor([1.0, 2.0]), torch.tensor([float("nan"), 3.0]))
    assert relation["both_all_finite"] is False
    assert relation["max_abs_difference"] is None
