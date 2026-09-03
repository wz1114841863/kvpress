"""Compact, validated replay-mask sources for A4.1 paired controls."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from kvpress.route_a_policy_backend import MaskEvent, MaskEventLayers


REPLAY_SOURCE_SCHEMA = "kvzap-route-a41-replay-mask-source-1.0"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_replay_events(path: Path, events: MaskEventLayers) -> str:
    """Write sorted events once in a compact NPZ without token text or K/V."""
    if path.exists():
        raise FileExistsError(f"replay event file already exists: {path}")
    rows = [(layer, head, position, keep, score) for layer, layer_events in events.items() for (head, position), (keep, score) in layer_events.items()]
    if not rows:
        raise ValueError("cannot write an empty replay mask source")
    rows.sort()
    layers, heads, positions, keeps, scores = zip(*rows, strict=True)
    if len(set((layer, head, position) for layer, head, position, _keep, _score in rows)) != len(rows):
        raise ValueError("replay source contains duplicate layer/KV-head/position events")
    np.savez_compressed(
        path,
        schema_version=np.array(REPLAY_SOURCE_SCHEMA),
        layer=np.asarray(layers, dtype=np.int16),
        kv_head=np.asarray(heads, dtype=np.int16),
        cache_position=np.asarray(positions, dtype=np.int32),
        keep=np.asarray(keeps, dtype=np.bool_),
        score=np.asarray(scores, dtype=np.float32),
    )
    return sha256_file(path)


def load_replay_events(path: Path) -> MaskEventLayers:
    """Load and validate a replay source into backend event dictionaries."""
    with np.load(path, allow_pickle=False) as source:
        required = {"schema_version", "layer", "kv_head", "cache_position", "keep", "score"}
        if set(source.files) != required:
            raise ValueError("replay source fields do not match the A4.1 schema")
        schema = str(source["schema_version"].item())
        if schema != REPLAY_SOURCE_SCHEMA:
            raise ValueError("unexpected replay source schema")
        arrays = [source[name] for name in ("layer", "kv_head", "cache_position", "keep", "score")]
    if not arrays[0].size or len({array.shape for array in arrays}) != 1:
        raise ValueError("replay source arrays must be non-empty and shape-aligned")
    events: MaskEventLayers = {}
    for layer, head, position, keep, score in zip(*arrays, strict=True):
        key = (int(head), int(position))
        if int(layer) < 0 or key[0] < 0 or key[1] < 0 or not np.isfinite(score):
            raise ValueError("replay source contains invalid layer/head/position/score")
        layer_events = events.setdefault(int(layer), {})
        if key in layer_events:
            raise ValueError("replay source contains duplicate layer/KV-head/position events")
        layer_events[key] = (bool(keep), float(score))
    return events
