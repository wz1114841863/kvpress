from tools.validate_kvzap_route_a4112b_external_storage_binding import mature_positions


def test_a4112b_mature_positions_respect_hot_window_and_batch_append():
    assert list(mature_positions({"start_position": 0, "end_position": 127})) == []
    assert list(mature_positions({"start_position": 0, "end_position": 130})) == [0, 1, 2]
    assert list(mature_positions({"start_position": 131, "end_position": 133})) == [3, 4, 5]
