from kvpress.route_a_continuation_diagnostic import first_token_mismatch, prefix_equal_before_step


def test_first_token_mismatch_is_bounded_and_none_for_equal_sequences():
    assert first_token_mismatch([1, 2, 3], [1, 2, 3]) is None
    assert first_token_mismatch([1, 2, 3], [1, 9, 3]) == {"generated_token_offset": 1, "dense_token_id": 2, "route_a_token_id": 9}


def test_prefix_equal_before_step_stops_after_the_first_divergent_input():
    assert prefix_equal_before_step([1, 2, 3], [1, 9, 3], 0) is True
    assert prefix_equal_before_step([1, 2, 3], [1, 9, 3], 1) is True
    assert prefix_equal_before_step([1, 2, 3], [1, 9, 3], 2) is False
