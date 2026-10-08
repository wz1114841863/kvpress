import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl2_6_5c_event_replay import (
    AcceptedCarrierCapture,
    AcceptedCarrierObservation,
    RTL265cEventReplayError,
    RouteARTL265cOracleReplay,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl2_6_5c_event_capture_replay_manifest.json"
SCHEMA = ROOT / "analysis/rtl2_scoreboard_event_schema.json"
VALIDATOR = ROOT / "tools/validate_rtl2_6_5c_event_capture_replay.py"


def _records():
    return {item["event"]: item for item in json.loads(SCHEMA.read_text())["event_records"]}


def _observation(event: str, fields: dict[str, int], *, accepted: bool = True, owner: str | None = None, carrier: str | None = None):
    record = _records()[event]
    return AcceptedCarrierObservation(
        event, owner or record["emitter_owners"][0], carrier or record["carrier_ids"][0], accepted, fields,
    )


def _success_observations():
    request = {"request_id": 7, "incarnation": 1, "reset_epoch": 0, "delivery_context_ref": 2, "candidate_class": 3}
    rows = [_observation("request_accept", request)]
    for index in range(8):
        rows.append(_observation("fragment_deliver", {"request_id": 7, "incarnation": 1, "reset_epoch": 0, "delivery_context_ref": 2, "fragment_index": index, "last": int(index == 7), "status": 0}))
    rows += [
        _observation("write_commit", {"request_id": 7, "incarnation": 1, "reset_epoch": 0, "delivery_context_ref": 2, "operation_kind": 1, "status": 0, "r1_durable": 1}),
        _observation("descriptor_durable", {"page_ref": 0, "generation": 0, "layer": 0, "kv_head": 0, "transaction_group_tag": 1, "required_mask": 1, "durable_mask": 1}),
        _observation("metadata_publish_commit", {"transaction_group_tag": 1, "entry_id": 0, "record_ordinal": 0, "page_ref": 0, "generation": 0, "publication_status": 0}),
        _observation("authority_transition", {"entry_id": 0, "transaction_group_tag": 1, "from_authority": 1, "to_authority": 2}),
        _observation("source_deliverable", {"request_id": 7, "incarnation": 1, "source_kind": 2, "instance_coordinate": 0, "source_generation": 1, "source_valid": 1}),
    ]
    rows += [_observation("consumer_partial_commit", {"request_id": 7, "incarnation": 1, "source_kind": 2, "instance_coordinate": 0, "source_generation": 1, "consumer_id": consumer}) for consumer in range(4)]
    rows += [
        _observation("source_release", {"request_id": 7, "incarnation": 1, "source_kind": 2, "instance_coordinate": 0, "source_generation": 1, "all_four_consumers_committed": 1}),
        _observation("merge_request", {"request_id": 7, "incarnation": 1, "source_presence": 4}),
        _observation("attention_terminal", {"request_id": 7, "incarnation": 1, "terminal_status": 0}),
        _observation("descriptor_invalidate", {"page_ref": 0, "generation": 0, "descriptor_operation": 2, "delivery_context_ref": 0}),
        _observation("page_free", {"page_ref": 0, "generation": 0}),
        _observation("retire_ack", {"session_id": 0, "request_id": 7, "incarnation": 1}),
    ]
    return rows


def test_successful_accepted_carrier_trace_captures_all_fourteen_and_replays():
    capture = AcceptedCarrierCapture(ROOT)
    trace = capture.capture_many(_success_observations())
    assert set(event.event for event in trace) == set(_records())
    replay = RouteARTL265cOracleReplay(ROOT)
    replay.replay(trace)
    assert replay.summary() == {"authority": "packed", "faulted": False, "terminal_seen": True, "retire_ack": True, "full_kv_substitution_count": 0}


def test_fault_trace_is_explicit_and_cannot_publish_or_deposit_afterward():
    capture = AcceptedCarrierCapture(ROOT)
    trace = capture.capture_many([
        _observation("request_accept", {"request_id": 9, "incarnation": 2, "reset_epoch": 0, "delivery_context_ref": 2, "candidate_class": 3}),
        _observation("fragment_deliver", {"request_id": 9, "incarnation": 2, "reset_epoch": 0, "delivery_context_ref": 2, "fragment_index": 0, "last": 1, "status": 1}),
    ])
    replay = RouteARTL265cOracleReplay(ROOT); replay.replay(trace)
    assert replay.summary()["faulted"] is True
    with pytest.raises(RTL265cEventReplayError, match="fault/non-durable"):
        replay.dispatch(capture.capture(_observation("write_commit", {"request_id": 9, "incarnation": 2, "reset_epoch": 0, "delivery_context_ref": 2, "operation_kind": 1, "status": 0, "r1_durable": 1})))


def test_stale_identity_and_bounded_ready_low_emit_nothing_until_actual_acceptance():
    capture = AcceptedCarrierCapture(ROOT)
    ready_low = _observation("request_accept", {"request_id": 4, "incarnation": 1, "reset_epoch": 0, "delivery_context_ref": 2, "candidate_class": 3}, accepted=False)
    with pytest.raises(RTL265cEventReplayError, match="unaccepted"):
        capture.capture(ready_low)
    stale = _observation("fragment_deliver", {"request_id": 99, "incarnation": 1, "reset_epoch": 0, "delivery_context_ref": 2, "fragment_index": 0, "last": 1, "status": 0}, accepted=False)
    with pytest.raises(RTL265cEventReplayError, match="unaccepted"):
        capture.capture(stale)
    accepted = capture.capture(_observation("request_accept", dict(ready_low.fields)))
    replay = RouteARTL265cOracleReplay(ROOT); replay.dispatch(accepted)
    before = replay.summary()
    stale_after_accept = capture.capture(_observation("fragment_deliver", {"request_id": 99, "incarnation": 1, "reset_epoch": 0, "delivery_context_ref": 2, "fragment_index": 0, "last": 1, "status": 0}))
    with pytest.raises(RTL265cEventReplayError, match="stale or mismatched"):
        replay.dispatch(stale_after_accept)
    assert replay.summary() == before


def test_manifest_rejects_schema_order_drift_and_cli_supports_help():
    manifest = json.loads(MANIFEST.read_text())
    bad = copy.deepcopy(manifest); bad["captured_event_order"].reverse()
    with pytest.raises(RTL265cEventReplayError, match="schema order"):
        validate_manifest(bad, json.loads(SCHEMA.read_text()))
    help_result = subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "--manifest" in help_result.stdout
