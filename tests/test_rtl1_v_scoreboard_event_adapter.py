from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

from kvpress.route_a_lifecycle_adapter_reference import INIT_ACKS, RETIRE_DRAIN_ACKS

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "hardware/route_a/chisel/testbench/route_a_scoreboard_event_adapter.py"


def _load():
    spec = importlib.util.spec_from_file_location("route_a_scoreboard_event_adapter", ADAPTER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def _event(module, domain, event, **fields):
    return module.ScoreboardEvent(domain, event, fields)


def test_adapter_checks_authority_reclaim_and_finite_fair_progress_without_model_execution():
    module = _load(); adapter = module.RouteAScoreboardEventAdapter(ROOT)
    for event in [
        _event(module, "authority", "seed_hot", token="t0"),
        _event(module, "authority", "mature", token="t0", keep=True),
        _event(module, "authority", "open_packed_write", request_id=0, token="t0"),
        _event(module, "authority", "page_write_commit", request_id=0, token="t0"),
        _event(module, "authority", "begin_metadata_group", group_id="g0", members=("t0",)),
        _event(module, "authority", "stage_metadata_member", group_id="g0", member="t0"),
        _event(module, "authority", "metadata_atomic_publish", group_id="g0"),
    ]: adapter.dispatch(event)
    assert adapter.authority.authority("t0") == "packed"
    assert adapter.authority.authoritative_count("t0") == 1

    ref = adapter.dispatch(_event(module, "reclaim", "allocate", ref="p0", layer=0, kv_head=0))
    adapter.dispatch(_event(module, "reclaim", "payload_write_commit", ref="p0"))
    operations = adapter.dispatch(_event(module, "reclaim", "descriptor_prepare", ref="p0", layer=0, kv_head=0, valid_count=1))
    for operation_id in operations: adapter.dispatch(_event(module, "reclaim", "descriptor_terminal", operation_id=operation_id, success=True))
    adapter.dispatch(_event(module, "reclaim", "metadata_publish", ref="p0"))
    adapter.dispatch(_event(module, "reclaim", "retire", request_id=1, incarnation=0))
    adapter.dispatch(_event(module, "reclaim", "quiesce", ref="p0"))
    invalidate = adapter.dispatch(_event(module, "reclaim", "invalidate", ref="p0"))
    adapter.dispatch(_event(module, "reclaim", "invalidate_terminal", operation_id=invalidate, success=True))
    adapter.dispatch(_event(module, "reclaim", "finish_reclaim", ref="p0"))
    assert ref.page_id == 0

    for acknowledgement in INIT_ACKS: adapter.dispatch(_event(module, "lifecycle", "ack_init", acknowledgement=acknowledgement))
    adapter.dispatch(_event(module, "lifecycle", "session_start", session_id=0, context_tokens=32768))
    adapter.dispatch(_event(module, "lifecycle", "kv_arrival", entry_id=0, layer=0, kv_head=0, logical_position=0, payload_ref=7))
    adapter.dispatch(_event(module, "lifecycle", "attention_accept", request_id=2, incarnation=0, layer=0, kv_head=0, query_position=1))
    adapter.dispatch(_event(module, "lifecycle", "gqa_complete", request_id=2, incarnation=0))
    assert adapter.dispatch(_event(module, "lifecycle", "terminal", request_id=2, incarnation=0, success=True)) == "success"
    adapter.dispatch(_event(module, "lifecycle", "retire", request_id=3, incarnation=0, session_id=0))
    for acknowledgement in RETIRE_DRAIN_ACKS: adapter.dispatch(_event(module, "lifecycle", "drain_ack", acknowledgement=acknowledgement))
    assert adapter.dispatch(_event(module, "lifecycle", "retire_ack")) is not None


def test_adapter_rejects_unknown_or_malformed_events():
    module = _load(); adapter = module.RouteAScoreboardEventAdapter(ROOT)
    with pytest.raises(module.ScoreboardEventError): adapter.dispatch(_event(module, "authority", "unknown", token="t0"))
    with pytest.raises(module.ScoreboardEventError): adapter.dispatch(_event(module, "authority", "seed_hot", token="t0", extra=True))
