from tools.analyze_kvzap_route_a4212_dispatch_epoch_evidence import reconstruct, write_epochs


def event(sequence, layer, kv_head, query_head, position):
    return {"logical_event_sequence": sequence, "layer": layer, "kv_head": kv_head, "query_head": query_head,
            "phase": "decode", "cache_position": position,
            "source_decisions": [{"source": "hot", "outcome": "partial", "record_count": 2, "first_position": 1, "last_position": 2},
                                 {"source": "pending", "outcome": "skip", "record_count": 0, "first_position": None, "last_position": None},
                                 {"source": "packed", "outcome": "partial", "record_count": 3, "first_position": 3, "last_position": 5}]}


def test_reconstruction_groups_same_layer_and_keeps_cross_layer_ordered():
    rows, summary = reconstruct([event(0, 0, 0, 0, 9), event(1, 0, 0, 1, 9), event(2, 1, 0, 0, 9), event(3, 1, 0, 1, 9), event(4, 0, 0, 0, 10)])
    assert [row["forward_epoch"] for row in rows] == [0, 0, 0, 0, 1]
    assert [row["source_ready_epoch"] for row in rows] == [0, 0, 1, 1, 2]
    assert summary["same_layer_same_kv_head_group_semantic_pair_count"] == 2
    assert summary["cross_layer_semantic_overlap_allowed"] is False


def test_epoch_gzip_hash_is_host_and_time_independent(tmp_path):
    rows = [{"logical_event_sequence": 0, "source_ready_epoch": 0}]
    assert write_epochs(tmp_path / "left.jsonl.gz", rows) == write_epochs(tmp_path / "right.jsonl.gz", rows)
