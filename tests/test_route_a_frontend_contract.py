import numpy as np
import pytest
import torch
from types import SimpleNamespace

from kvpress.presses.scorer_press import ScorerPress
from kvpress.route_a_frontend_contract import (
    FRONTEND_DECISION_STREAM_SCHEMA,
    SNAPKV_FRONTEND_NAME,
    SNAPKV_TERMINAL_EPOCH,
    FrontendDecision,
    SnapKVPrefillDecisionObserver,
    load_frontend_decision_stream,
    snapkv_terminal_decisions_from_scores,
    validate_snapkv_p0_contract,
    write_frontend_decision_stream,
)


def _scores():
    return torch.tensor([[[0.1, 0.5, 0.2, 2.0, 2.1], [0.7, 0.6, 0.4, 1.9, 2.2]]])


def test_snapkv_terminal_decisions_share_native_topk_set_and_use_original_position_order():
    scores = _scores()
    decisions = snapkv_terminal_decisions_from_scores(scores, compression_ratio=0.4, layer=3, request_id="unit")
    native = ScorerPress.select_topk_indices(scores, 3)
    observed = {
        (row.kv_head, row.original_position)
        for row in decisions
        if row.keep
    }
    expected = {(head, int(position)) for head in range(2) for position in native[0, head]}
    assert observed == expected
    assert [(row.kv_head, row.original_position) for row in decisions] == [
        (0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (1, 0), (1, 1), (1, 2), (1, 3), (1, 4)
    ]


def test_snapkv_p0_contract_verifies_terminal_coverage_and_protected_window():
    report = validate_snapkv_p0_contract(
        snapkv_terminal_decisions_from_scores(_scores(), compression_ratio=0.4, layer=0, request_id="unit"),
        window_size=2,
        compression_ratio=0.4,
    )
    assert report["schema_version"] == FRONTEND_DECISION_STREAM_SCHEMA
    assert report["frontend_name"] == SNAPKV_FRONTEND_NAME
    assert report["decision_epoch"] == SNAPKV_TERMINAL_EPOCH
    assert report["terminal_finality_verified"] is True
    assert report["drop_to_keep_transition_count"] == 0
    assert all(row["protected_window_keep_count"] == 2 for row in report["groups"])


def test_snapkv_p0_contract_rejects_missing_position_or_protected_drop():
    decisions = snapkv_terminal_decisions_from_scores(_scores(), compression_ratio=0.4, layer=0, request_id="unit")
    with pytest.raises(ValueError, match="contiguous"):
        validate_snapkv_p0_contract(decisions[:-1], window_size=2, compression_ratio=0.4)
    modified = list(decisions)
    terminal = modified[-1]
    modified[-1] = FrontendDecision(
        frontend_name=terminal.frontend_name,
        request_id=terminal.request_id,
        decision_epoch=terminal.decision_epoch,
        model_call_index=terminal.model_call_index,
        layer=terminal.layer,
        kv_head=terminal.kv_head,
        original_position=terminal.original_position,
        sequence_length=terminal.sequence_length,
        keep=False,
        score=terminal.score,
    )
    with pytest.raises(ValueError, match="keep count|protection"):
        validate_snapkv_p0_contract(modified, window_size=2, compression_ratio=0.4)


def test_frontend_decision_stream_round_trip_and_refuses_existing_output(tmp_path):
    decisions = snapkv_terminal_decisions_from_scores(_scores(), compression_ratio=0.4, layer=1, request_id="unit")
    path = tmp_path / "decision_stream.npz"
    digest = write_frontend_decision_stream(path, decisions)
    assert len(digest) == 64
    assert load_frontend_decision_stream(path) == decisions
    with pytest.raises(FileExistsError, match="already exists"):
        write_frontend_decision_stream(path, decisions)


def test_frontend_decision_stream_rejects_duplicate_or_wrong_schema(tmp_path):
    decisions = snapkv_terminal_decisions_from_scores(_scores(), compression_ratio=0.4, layer=1, request_id="unit")
    with pytest.raises(ValueError, match="duplicate"):
        write_frontend_decision_stream(tmp_path / "duplicate.npz", decisions + [decisions[0]])
    path = tmp_path / "wrong.npz"
    np.savez_compressed(path, schema_version=np.array("wrong"))
    with pytest.raises(ValueError, match="fields"):
        load_frontend_decision_stream(path)


def test_snapkv_observer_records_decisions_without_replacing_cache_tensors():
    module = torch.nn.Module()
    module.layer_idx = 0
    model = SimpleNamespace(model=SimpleNamespace(layers=[SimpleNamespace(self_attn=module)]))
    keys = torch.randn(1, 2, 5, 3)
    values = torch.randn(1, 2, 5, 3)
    cache = SimpleNamespace(layers=[SimpleNamespace(keys=keys, values=values)])
    press = SimpleNamespace(compression_ratio=0.4, score=lambda *_args: _scores())
    output = (torch.empty(0), None)
    observer = SnapKVPrefillDecisionObserver(model, press, request_id="unit", target_layers=(0,))
    result = observer._forward_hook(
        module,
        (),
        {"hidden_states": torch.empty(1, 5, 1), "cache_position": torch.arange(5), "past_key_values": cache},
        output,
    )
    assert result is output
    assert cache.layers[0].keys is keys
    assert cache.layers[0].values is values
    assert len(observer.decisions()) == 10
