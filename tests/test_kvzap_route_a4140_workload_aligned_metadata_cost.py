import hashlib

from tools.analyze_kvzap_route_a4140_workload_aligned_metadata_cost import (
    PAGE_TOKENS,
    reconstruct_transactions,
    sha256_file,
)


def event(sequence, start, end, kept):
    return {
        "layer": 0,
        "logical_transition_sequence": sequence,
        "start_position": start,
        "end_position": end,
        "heads": [{"kv_head": 0, "matured_kept_tokens": kept, "matured_dropped_tokens": 0}],
    }


def test_reconstruction_preserves_span_group_members_and_per_head_fifo():
    # The hot-window helper makes positions [0, 1] mature at end=129 and then
    # position 2 at the next append.  All remain in logical span zero.
    events = [event(0, 0, 129, 2), event(1, 130, 130, 1)]
    replay = {layer: {} for layer in range(36)}
    for position in range(3): replay[0][(0, position)] = (True, 0.0)
    candidate = {"mapping": "head_affine_v1", "banks": 8}
    transactions, members = reconstruct_transactions(events, replay, candidate)
    assert len(transactions) == 2
    assert transactions[0].predecessors == frozenset()
    assert transactions[1].predecessors == frozenset({0})
    assert all(len(value) == 2 for value in members.values())
    assert {(item.object_key[0], item.operation) for item in members[0]} == {("head_control", "rmw"), ("span_owner", "rmw")}
    assert PAGE_TOKENS == 64


def test_reconstruction_rejects_a_mask_that_disagrees_with_lifecycle_counts():
    events = [event(0, 0, 129, 2)]
    replay = {layer: {} for layer in range(36)}
    replay[0][(0, 0)] = (True, 0.0)
    replay[0][(0, 1)] = (False, 0.0)
    candidate = {"mapping": "head_affine_v1", "banks": 8}
    try:
        reconstruct_transactions(events, replay, candidate)
    except ValueError as error:
        assert "reconstructed frozen-mask maturity" in str(error)
    else:
        raise AssertionError("mismatched frozen-mask reconstruction was accepted")


def test_imported_hash_function_is_available_to_exact_input_validation(tmp_path):
    path = tmp_path / "artifact.json"
    path.write_text("{}", encoding="utf-8")
    assert sha256_file(path) == hashlib.sha256(b"{}").hexdigest()
