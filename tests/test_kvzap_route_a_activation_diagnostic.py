import torch

from kvpress.route_a_activation_diagnostic import summarize_activation_relation, summarize_layer_activation_relations
from tools.run_kvzap_route_a4127_allhead_activation_diagnostic import requirement


def test_activation_relation_reports_bounded_maximum_and_per_token_values_without_tensor_output():
    dense = torch.zeros(1, 2, 3)
    route = dense.clone()
    route[0, 1, 2] = 0.5
    summary = summarize_activation_relation(dense, route)
    assert summary["shape"] == [1, 2, 3]
    assert summary["both_all_finite"] is True
    assert summary["max_abs_difference"] == 0.5
    assert summary["maximum"] == {
        "batch": 0,
        "question_token_offset": 1,
        "hidden_index": 2,
        "dense_value": 0.0,
        "route_a_value": 0.5,
    }
    assert summary["per_question_token"][0]["max_abs_difference"] == 0.0
    assert summary["per_question_token"][1]["max_abs_difference"] == 0.5


def test_layer_activation_relation_finds_first_nonzero_layer_and_accepts_exact_layers():
    dense = {0: torch.zeros(1, 2, 2), 1: torch.ones(1, 2, 2)}
    route = {0: torch.zeros(1, 2, 2), 1: torch.ones(1, 2, 2)}
    assert summarize_layer_activation_relations(dense, route)["first_layer_with_nonzero_difference"] is None
    route[1][0, 0, 0] = 2.0
    relation = summarize_layer_activation_relations(dense, route)
    assert relation["first_layer_with_nonzero_difference"] == 1
    assert relation["layers"][0]["max_abs_difference"] == 0.0
    assert relation["layers"][1]["max_abs_difference"] == 1.0


def test_guard_requirement_distinguishes_unrequested_from_satisfied():
    assert requirement(requested=False, satisfied=False) == {"requested": False, "satisfied": None}
    assert requirement(requested=True, satisfied=True) == {"requested": True, "satisfied": True}
