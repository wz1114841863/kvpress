"""Read-only frontend decision contracts for Route-A portability gates.

This module deliberately separates an algorithm's final selection from the
Route-A storage/attention backend.  It contains no allocator, timing, traffic,
or hardware model.  SnapKV's native press still gathers K/V in score-ranked
order; the adapter below instead records the same selected set as terminal
``(layer, KV head, original position)`` decisions for a later canonical replay.
"""

from __future__ import annotations

import hashlib
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from kvpress.presses.base_press import is_prefilling
from kvpress.presses.scorer_press import ScorerPress
from kvpress.utils import extract_keys_and_values


FRONTEND_DECISION_STREAM_SCHEMA = "route-a-frontend-decision-stream-1.0"
SNAPKV_FRONTEND_NAME = "snapkv_prefill_topk"
SNAPKV_TERMINAL_EPOCH = "prefill_terminal"


@dataclass(frozen=True)
class FrontendDecision:
    """One final per-position frontend decision, without token text or K/V."""

    frontend_name: str
    request_id: str
    decision_epoch: str
    model_call_index: int
    layer: int
    kv_head: int
    original_position: int
    sequence_length: int
    keep: bool
    score: float


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_scores(scores: torch.Tensor, compression_ratio: float) -> None:
    if scores.ndim != 3 or scores.shape[0] != 1 or scores.shape[1] <= 0 or scores.shape[2] <= 0:
        raise ValueError("SnapKV decision scores must have shape [1, positive KV-head count, positive length]")
    if not 0.0 <= compression_ratio < 1.0:
        raise ValueError("compression_ratio must be in [0, 1)")
    if not torch.isfinite(scores).all():
        raise ValueError("SnapKV decision scores must be finite")


def snapkv_terminal_decisions_from_scores(
    scores: torch.Tensor,
    *,
    compression_ratio: float,
    layer: int,
    request_id: str,
    model_call_index: int = 0,
) -> list[FrontendDecision]:
    """Materialize SnapKV's exact top-k set as canonical terminal decisions.

    ``torch.topk`` has the same tie behavior as the native ``ScorerPress``
    compressor.  Only after selection do we emit rows in original-position
    order; that ordering is the Route-A identity contract, not a change to the
    selected set or an assertion about native compressed-cache ordering.
    """
    _validate_scores(scores, compression_ratio)
    if layer < 0 or model_call_index < 0 or not request_id:
        raise ValueError("layer/model_call_index/request_id is invalid")
    sequence_length = int(scores.shape[-1])
    n_kept = int(sequence_length * (1.0 - compression_ratio))
    selected = ScorerPress.select_topk_indices(scores, n_kept)
    keep_mask = torch.zeros_like(scores, dtype=torch.bool)
    keep_mask.scatter_(-1, selected, True)
    score_cpu = scores.detach().to(device="cpu", dtype=torch.float32)
    keep_cpu = keep_mask.detach().to(device="cpu")
    decisions: list[FrontendDecision] = []
    for kv_head in range(int(scores.shape[1])):
        for position in range(sequence_length):
            decisions.append(
                FrontendDecision(
                    frontend_name=SNAPKV_FRONTEND_NAME,
                    request_id=request_id,
                    decision_epoch=SNAPKV_TERMINAL_EPOCH,
                    model_call_index=model_call_index,
                    layer=layer,
                    kv_head=kv_head,
                    original_position=position,
                    sequence_length=sequence_length,
                    keep=bool(keep_cpu[0, kv_head, position].item()),
                    score=float(score_cpu[0, kv_head, position].item()),
                )
            )
    return decisions


def _validate_terminal_rows(decisions: list[FrontendDecision]) -> None:
    if not decisions:
        raise ValueError("frontend decision stream cannot be empty")
    identities: set[tuple[int, int, int, int]] = set()
    for row in decisions:
        identity = (row.model_call_index, row.layer, row.kv_head, row.original_position)
        if identity in identities:
            raise ValueError("frontend decision stream contains a duplicate identity")
        identities.add(identity)
        if (
            not row.request_id
            or row.model_call_index < 0
            or row.layer < 0
            or row.kv_head < 0
            or row.original_position < 0
            or row.sequence_length <= 0
            or row.original_position >= row.sequence_length
            or not np.isfinite(row.score)
        ):
            raise ValueError("frontend decision stream contains an invalid terminal decision")


def validate_snapkv_p0_contract(
    decisions: list[FrontendDecision], *, window_size: int, compression_ratio: float
) -> dict[str, Any]:
    """Validate P0 finality, coverage, and protected-window invariants.

    The one-shot SnapKV epoch has no online maturity/pending timeline.  Its P0
    claim is narrower: every prefill position is covered exactly once by a
    terminal keep/drop decision, and the score-padded observation window stays
    selected when the configured keep budget can contain it.
    """
    _validate_terminal_rows(decisions)
    if window_size <= 0 or not 0.0 <= compression_ratio < 1.0:
        raise ValueError("window_size/compression_ratio is invalid")
    groups: dict[tuple[int, int, int], list[FrontendDecision]] = {}
    for row in decisions:
        if row.frontend_name != SNAPKV_FRONTEND_NAME or row.decision_epoch != SNAPKV_TERMINAL_EPOCH:
            raise ValueError("SnapKV P0 accepts only terminal SnapKV prefill decisions")
        groups.setdefault((row.model_call_index, row.layer, row.kv_head), []).append(row)
    rows = []
    for (model_call_index, layer, kv_head), group in sorted(groups.items()):
        group.sort(key=lambda item: item.original_position)
        positions = [item.original_position for item in group]
        declared_lengths = {item.sequence_length for item in group}
        if len(declared_lengths) != 1:
            raise ValueError("SnapKV P0 has inconsistent declared sequence lengths per layer/KV head")
        length = declared_lengths.pop()
        if positions != list(range(length)):
            raise ValueError("SnapKV P0 requires contiguous original-position coverage per layer/KV head")
        expected_keep_count = int(length * (1.0 - compression_ratio))
        keep_count = sum(item.keep for item in group)
        if keep_count != expected_keep_count:
            raise ValueError("SnapKV P0 keep count differs from the configured top-k budget")
        protected_start = max(0, length - window_size)
        protected_missing = [item.original_position for item in group if item.original_position >= protected_start and not item.keep]
        if protected_missing:
            raise ValueError("SnapKV P0 observation-window protection was violated")
        rows.append(
            {
                "model_call_index": model_call_index,
                "layer": layer,
                "kv_head": kv_head,
                "sequence_length": length,
                "keep_count": keep_count,
                "drop_count": length - keep_count,
                "protected_window_start": protected_start,
                "protected_window_keep_count": length - protected_start,
            }
        )
    return {
        "schema_version": FRONTEND_DECISION_STREAM_SCHEMA,
        "frontend_name": SNAPKV_FRONTEND_NAME,
        "decision_epoch": SNAPKV_TERMINAL_EPOCH,
        "terminal_finality_verified": True,
        "drop_to_keep_transition_count": 0,
        "group_count": len(rows),
        "event_count": len(decisions),
        "groups": rows,
    }


def snapkv_terminal_decisions_to_route_a_replay_masks(
    decisions: list[FrontendDecision],
) -> dict[int, dict[tuple[int, int], tuple[bool, float]]]:
    """Convert one complete SnapKV terminal epoch into Route-A replay masks.

    The resulting keys are the existing Route-A identity contract
    ``(KV head, original position)`` inside a layer.  This is deliberately a
    lossless identity conversion: it does not reuse SnapKV's native
    score-ranked gather order, generate decisions for later decode positions,
    or turn a one-shot prefill frontend into an online predictor.
    """
    _validate_terminal_rows(decisions)
    if {row.frontend_name for row in decisions} != {SNAPKV_FRONTEND_NAME}:
        raise ValueError("Route-A replay accepts only the SnapKV frontend")
    if {row.decision_epoch for row in decisions} != {SNAPKV_TERMINAL_EPOCH}:
        raise ValueError("Route-A replay accepts only SnapKV terminal prefill decisions")
    if {row.model_call_index for row in decisions} != {0}:
        raise ValueError("SnapKV P3 accepts exactly one terminal prefill model call")
    request_ids = {row.request_id for row in decisions}
    if len(request_ids) != 1:
        raise ValueError("SnapKV terminal replay requires one request identity")

    by_layer_head: dict[tuple[int, int], list[FrontendDecision]] = {}
    for row in decisions:
        by_layer_head.setdefault((row.layer, row.kv_head), []).append(row)
    layers = sorted({layer for layer, _head in by_layer_head})
    if layers != list(range(len(layers))):
        raise ValueError("SnapKV terminal replay requires contiguous layer IDs")
    replay: dict[int, dict[tuple[int, int], tuple[bool, float]]] = {}
    for layer in layers:
        heads = sorted(head for candidate_layer, head in by_layer_head if candidate_layer == layer)
        if heads != list(range(len(heads))):
            raise ValueError("SnapKV terminal replay requires contiguous KV-head IDs per layer")
        events: dict[tuple[int, int], tuple[bool, float]] = {}
        for head in heads:
            rows = sorted(by_layer_head[(layer, head)], key=lambda row: row.original_position)
            lengths = {row.sequence_length for row in rows}
            if len(lengths) != 1:
                raise ValueError("SnapKV terminal replay has inconsistent sequence lengths")
            sequence_length = lengths.pop()
            if [row.original_position for row in rows] != list(range(sequence_length)):
                raise ValueError("SnapKV terminal replay lacks contiguous original-position coverage")
            for row in rows:
                key = (head, row.original_position)
                if key in events:
                    raise ValueError("SnapKV terminal replay contains a duplicate Route-A event")
                events[key] = (row.keep, row.score)
        replay[layer] = events
    return replay


def write_frontend_decision_stream(path: Path, decisions: list[FrontendDecision]) -> str:
    """Write a compact, sorted, final-decision-only NPZ once."""
    if path.exists():
        raise FileExistsError(f"frontend decision stream already exists: {path}")
    _validate_terminal_rows(decisions)
    rows = sorted(
        decisions,
        key=lambda item: (item.model_call_index, item.layer, item.kv_head, item.original_position),
    )
    np.savez_compressed(
        path,
        schema_version=np.array(FRONTEND_DECISION_STREAM_SCHEMA),
        frontend_name=np.asarray([item.frontend_name for item in rows]),
        request_id=np.asarray([item.request_id for item in rows]),
        decision_epoch=np.asarray([item.decision_epoch for item in rows]),
        model_call_index=np.asarray([item.model_call_index for item in rows], dtype=np.int32),
        layer=np.asarray([item.layer for item in rows], dtype=np.int16),
        kv_head=np.asarray([item.kv_head for item in rows], dtype=np.int16),
        original_position=np.asarray([item.original_position for item in rows], dtype=np.int32),
        sequence_length=np.asarray([item.sequence_length for item in rows], dtype=np.int32),
        keep=np.asarray([item.keep for item in rows], dtype=np.bool_),
        score=np.asarray([item.score for item in rows], dtype=np.float32),
    )
    return sha256_file(path)


def load_frontend_decision_stream(path: Path) -> list[FrontendDecision]:
    """Load and validate a compact final-decision stream."""
    expected = {
        "schema_version",
        "frontend_name",
        "request_id",
        "decision_epoch",
        "model_call_index",
        "layer",
        "kv_head",
        "original_position",
        "sequence_length",
        "keep",
        "score",
    }
    with np.load(path, allow_pickle=False) as source:
        if set(source.files) != expected:
            raise ValueError("frontend decision stream fields do not match the schema")
        if str(source["schema_version"].item()) != FRONTEND_DECISION_STREAM_SCHEMA:
            raise ValueError("unexpected frontend decision stream schema")
        arrays = [source[name] for name in sorted(expected - {"schema_version"})]
    if not arrays[0].size or len({array.shape for array in arrays}) != 1:
        raise ValueError("frontend decision stream arrays must be non-empty and shape-aligned")
    fields = {name: value for name, value in zip(sorted(expected - {"schema_version"}), arrays, strict=True)}
    decisions = [
        FrontendDecision(
            frontend_name=str(frontend_name),
            request_id=str(request_id),
            decision_epoch=str(decision_epoch),
            model_call_index=int(model_call_index),
            layer=int(layer),
            kv_head=int(kv_head),
            original_position=int(original_position),
            sequence_length=int(sequence_length),
            keep=bool(keep),
            score=float(score),
        )
        for frontend_name, request_id, decision_epoch, model_call_index, layer, kv_head, original_position, sequence_length, keep, score in zip(
            fields["frontend_name"],
            fields["request_id"],
            fields["decision_epoch"],
            fields["model_call_index"],
            fields["layer"],
            fields["kv_head"],
            fields["original_position"],
            fields["sequence_length"],
            fields["keep"],
            fields["score"],
            strict=True,
        )
    ]
    _validate_terminal_rows(decisions)
    return decisions


class SnapKVPrefillDecisionObserver(AbstractContextManager):
    """Collect terminal SnapKV decisions after dense prefill without cache mutation."""

    def __init__(
        self,
        model,
        press,
        *,
        request_id: str,
        target_layers: tuple[int, ...] | None = None,
        model_call_index: int = 0,
    ) -> None:
        if not request_id or model_call_index < 0:
            raise ValueError("request_id/model_call_index is invalid")
        language_model = model.model.language_model if hasattr(model.model, "language_model") else model.model
        all_layers = tuple(range(len(language_model.layers)))
        self.layers = all_layers if target_layers is None else target_layers
        if not self.layers or len(set(self.layers)) != len(self.layers) or any(layer not in all_layers for layer in self.layers):
            raise ValueError("target_layers must be unique valid layer indices")
        self.model = model
        self.press = press
        self.request_id = request_id
        self.model_call_index = model_call_index
        self._modules = {int(layer): language_model.layers[layer].self_attn for layer in self.layers}
        self._hooks = []
        self._decisions: dict[int, list[FrontendDecision]] = {}

    def __enter__(self):
        if self._hooks:
            raise RuntimeError("SnapKV decision observer is already attached")
        for layer, module in self._modules.items():
            self._hooks.append(module.register_forward_hook(self._forward_hook, with_kwargs=True))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        for hook in self._hooks:
            hook.remove()
        self._hooks = []
        return None

    def _forward_hook(self, module, _inputs, kwargs, output):
        hidden_states = kwargs.get("hidden_states")
        cache_position = kwargs.get("cache_position")
        cache = kwargs.get("past_key_values")
        if hidden_states is None or cache_position is None or cache is None:
            raise AssertionError("SnapKV P0 observer requires hidden_states, cache_position, and past_key_values")
        if not is_prefilling(cache_position, hidden_states.shape[1]):
            return output
        layer = int(module.layer_idx)
        if layer not in self._modules:
            return output
        if layer in self._decisions:
            raise AssertionError("SnapKV P0 observed more than one prefill terminal epoch in one layer")
        keys, values = extract_keys_and_values(cache, layer)
        scores = self.press.score(module, hidden_states, keys, values, output[1], kwargs)
        self._decisions[layer] = snapkv_terminal_decisions_from_scores(
            scores,
            compression_ratio=float(self.press.compression_ratio),
            layer=layer,
            request_id=self.request_id,
            model_call_index=self.model_call_index,
        )
        return output

    def decisions(self) -> list[FrontendDecision]:
        missing = sorted(set(self.layers) - set(self._decisions))
        if missing:
            raise AssertionError(f"SnapKV P0 observer did not record selected layers: {missing}")
        return [row for layer in sorted(self._decisions) for row in self._decisions[layer]]
