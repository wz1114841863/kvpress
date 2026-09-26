from tools.validate_kvzap_route_a4112b_external_storage_binding import (
    mature_positions,
    per_layer_total_pending_after_maturity_max,
)


def test_a4112b_mature_positions_respect_hot_window_and_batch_append():
    assert list(mature_positions({"start_position": 0, "end_position": 127})) == []
    assert list(mature_positions({"start_position": 0, "end_position": 130})) == [0, 1, 2]
    assert list(mature_positions({"start_position": 131, "end_position": 133})) == [3, 4, 5]


def test_a4112b_per_layer_pending_watermark_sums_heads_within_one_append_epoch():
    events = [
        {"layer": 0, "heads": [{"pending_tokens_after_maturity": 7}, {"pending_tokens_after_maturity": 11}]},
        {"layer": 0, "heads": [{"pending_tokens_after_maturity": 13}, {"pending_tokens_after_maturity": 2}]},
        {"layer": 1, "heads": [{"pending_tokens_after_maturity": 3}, {"pending_tokens_after_maturity": 5}]},
    ]
    assert per_layer_total_pending_after_maturity_max(events) == {0: 18, 1: 8}
