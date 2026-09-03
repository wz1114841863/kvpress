import json
from argparse import Namespace
from pathlib import Path

import pytest

from kvpress.route_a_measurement import (
    A41_RAW_SCHEMA,
    CudaMemorySnapshot,
    TimingSample,
    cuda_memory_snapshot,
    initialize_output_directory,
    raw_record,
    reset_cuda_peak_memory,
    summarize_reported_repetitions,
    time_cuda_region,
    validate_raw_repetition,
    write_completed_manifest,
    write_raw_repetitions,
)
from kvpress.route_a_replay import load_replay_events, sha256_file, write_replay_events
from tools.run_kvzap_route_a41_component_gate import assert_pending_coverage, manifest_config


def snapshots():
    return CudaMemorySnapshot(allocated_bytes=10, reserved_bytes=20, peak_allocated_bytes=30, peak_reserved_bytes=40)


def make_record(*, warmup=False, repetition=0, order=0, wall_ms=2.0, cuda_event_ms=1.0):
    return raw_record(
        path="harness_self_check",
        component="cuda_tensor_add",
        repetition=repetition,
        execution_order=order,
        warmup=warmup,
        timing=TimingSample(wall_ms=wall_ms, cuda_event_ms=cuda_event_ms),
        memory_before=snapshots(),
        memory_after=snapshots(),
    )


def test_cuda_instrumentation_rejects_cpu_before_executing_operation():
    for function in (cuda_memory_snapshot, reset_cuda_peak_memory):
        with pytest.raises(ValueError, match="CUDA device"):
            function("cpu")
    called = False

    def operation():
        nonlocal called
        called = True

    with pytest.raises(ValueError, match="CUDA device"):
        time_cuda_region(operation, device="cpu")
    assert not called


def test_raw_repetition_validation_rejects_missing_or_nonbyte_allocator_fields():
    record = make_record()
    validate_raw_repetition(record)
    missing = dict(record)
    del missing["memory_after"]
    with pytest.raises(ValueError, match="missing fields"):
        validate_raw_repetition(missing)
    bad_memory = json.loads(json.dumps(record))
    bad_memory["memory_after"]["allocated_bytes"] = 1.5
    with pytest.raises(ValueError, match="byte count"):
        validate_raw_repetition(bad_memory)
    assert record["schema_version"] == A41_RAW_SCHEMA


def test_summary_excludes_warmup_and_reports_distribution():
    records = [
        make_record(warmup=True, repetition=0, order=0, wall_ms=99.0, cuda_event_ms=99.0),
        make_record(repetition=0, order=1, wall_ms=1.0, cuda_event_ms=2.0),
        make_record(repetition=1, order=2, wall_ms=3.0, cuda_event_ms=4.0),
    ]
    summary = summarize_reported_repetitions(records)
    group = summary["groups"][0]
    assert group["reported_repetitions"] == 2
    assert group["wall_ms"] == {"count": 2, "min": 1.0, "median": 2.0, "mean": 2.0, "stddev": pytest.approx(2**0.5), "p90": 2.8, "p95": 2.9, "max": 3.0}
    assert group["cuda_event_ms"]["mean"] == 3.0


def test_output_records_are_new_directory_only_and_raw_file_is_not_overwritten(tmp_path):
    output_dir = tmp_path / "a41_gate"
    started = initialize_output_directory(output_dir, config={"mode": "dry_run"}, git_commit="abc")
    assert json.loads(started.read_text())["status"] == "started"
    record = make_record()
    raw_path = write_raw_repetitions(output_dir, [record])
    assert raw_path.read_text().count("\n") == 1
    with pytest.raises(FileExistsError, match="raw repetitions"):
        write_raw_repetitions(output_dir, [record])
    summary = summarize_reported_repetitions([record])
    completed = write_completed_manifest(output_dir, config={"mode": "dry_run"}, git_commit="abc", summary=summary)
    assert json.loads(completed.read_text())["status"] == "complete"
    with pytest.raises(FileExistsError, match="output directory"):
        initialize_output_directory(output_dir, config={}, git_commit="def")


def test_replay_event_npz_round_trip_is_sorted_hashed_and_rejects_overwrite(tmp_path):
    events = {1: {(1, 4): (False, -4.25), (0, 4): (True, -3.75)}, 0: {(0, 3): (True, -3.5)}}
    path = tmp_path / "events.npz"
    digest = write_replay_events(path, events)
    assert digest == sha256_file(path)
    assert load_replay_events(path) == {0: {(0, 3): (True, -3.5)}, 1: {(0, 4): (True, -3.75), (1, 4): (False, -4.25)}}
    with pytest.raises(FileExistsError, match="already exists"):
        write_replay_events(path, events)


def test_component_manifest_config_serializes_path_arguments(tmp_path):
    config = manifest_config(Namespace(replay_source_dir=tmp_path / "source", output_dir=tmp_path / "result", admission_budget=1))
    assert config == {"replay_source_dir": str(tmp_path / "source"), "admission_budget": 1}
    assert json.loads(json.dumps(config)) == config


def test_pending_coverage_is_opt_in_for_component_candidate_points():
    comparisons = [{"pending_tokens": 0}]
    assert_pending_coverage(comparisons=comparisons, required=False)
    with pytest.raises(AssertionError, match="required pending"):
        assert_pending_coverage(comparisons=comparisons, required=True)
    assert_pending_coverage(comparisons=[{"pending_tokens": 1}], required=True)
