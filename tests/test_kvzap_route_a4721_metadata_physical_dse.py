from tools.analyze_kvzap_route_a4721_metadata_physical_dse import bank_index, fnv1a_64, longest_consecutive_integer_run, lower_transaction, saturation_streaks


def test_a4721_bank_mapping_is_deterministic_and_bounded():
    key = ("span_owner", (99,))
    assert fnv1a_64("fixed") == fnv1a_64("fixed")
    for mapping in ("head_affine_v1", "object_identity_striped_v1"):
        for count in (1, 4, 8):
            assert 0 <= bank_index(mapping, count, key, layer=3, head=7) < count


def test_a4721_colocated_read_write_lowers_to_one_modeled_rmw():
    row = {"layer": 1, "kv_head": 2, "read_set": [{"record_type": "span_descriptor", "record_identity": [1, 2, 7]}], "write_set": [{"record_type": "ownership_link", "record_identity": [1, 2, "private", 7]}], "rmw_set": [], "release_set": []}
    assert lower_transaction(row, "span_owner_colocated_direct_v1") == {("span_owner", (7,)): "rmw"}


def test_a4721_release_is_modeled_write_not_payload_movement():
    row = {"layer": 1, "kv_head": 2, "read_set": [], "write_set": [], "rmw_set": [], "release_set": [{"record_type": "span_descriptor", "record_identity": [1, 2, 7]}]}
    assert lower_transaction(row, "separated_direct_v1") == {("span_descriptor", (1, 2, 7)): "write"}


def test_a4721_saturation_run_requires_numerically_consecutive_checkpoints():
    assert longest_consecutive_integer_run([]) == 0
    assert longest_consecutive_integer_run([2, 3, 4, 8, 9]) == 3
    streaks = saturation_streaks([2, 3, 4, 8, 9], 2, {0: {2, 3, 4}, 1: {8, 9}})
    assert streaks["peak_any_bank_consecutive_saturated_logical_checkpoint_run"] == 3
    assert streaks["banks_saturated_at_every_observed_phase_checkpoint"] == []
