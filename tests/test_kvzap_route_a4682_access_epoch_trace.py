import hashlib

from tools.analyze_kvzap_route_a4682_access_epoch_trace import (
    AccessEpochTraceWriter,
    LifetimeTracker,
    OccupancyTracker,
    checkpoint_index,
    distribution,
)


def test_a4682_checkpoint_order_is_logical_and_phase_explicit():
    assert checkpoint_index(phase="activation", opportunity=0) == 0
    assert checkpoint_index(phase="steady_state_append", opportunity=3) == 5
    assert checkpoint_index(phase="steady_state_dequeue", opportunity=3) == 6


def test_a4682_lifetime_tracker_separates_completed_from_right_censored():
    tracker = LifetimeTracker()
    tracker.create(span_id=1, source="private", birth_opportunity=0, phase="activation", opportunity=0)
    tracker.by_span[1].active_checkpoint_count = 3
    tracker.release(span_id=1, phase="steady_state_dequeue", opportunity=2)
    tracker.create(span_id=2, source="shared", birth_opportunity=2, phase="steady_state_append", opportunity=2)
    tracker.by_span[2].active_checkpoint_count = 2
    tracker.by_span[2].end_phase = "steady_state_dequeue"
    tracker.by_span[2].end_opportunity = 2
    tracker.by_span[2].end_checkpoint = 4
    tracker.by_span[2].right_censored = True
    tracker.censored.append(tracker.by_span[2])
    summary = tracker.summary()
    assert summary["completed"]["span_count"] == 1
    assert summary["right_censored"]["span_count"] == 1
    assert summary["completed"]["lifetime_checkpoint_distance"]["max"] == 4
    assert summary["right_censored"]["lifetime_opportunity_distance"]["max"] == 0
    assert summary["all_observed_spans"]["active_span_residence_checkpoints"]["sum"] == 5


def test_a4682_distribution_reports_empty_and_nonempty_without_time_units():
    assert distribution([])["count"] == 0
    assert distribution([])["p95"] is None
    assert distribution([1, 2, 10])["max"] == 10


def test_a4682_peak_plateau_counts_logical_checkpoints_not_cycles():
    rows = [
        {"active_spans": 1},
        {"active_spans": 3},
        {"active_spans": 3},
        {"active_spans": 2},
        {"active_spans": 3},
    ]
    plateau = OccupancyTracker._plateau(rows)
    assert plateau["peak_active_spans"] == 3
    assert plateau["peak_active_span_plateau_max_contiguous_checkpoints"] == 2
    assert plateau["peak_active_span_plateau_total_checkpoints"] == 3


def test_a4682_closed_trace_is_final_before_manifest_hash(tmp_path):
    path = tmp_path / "events.jsonl.gz"
    writer = AccessEpochTraceWriter(path)
    writer.record(phase="activation", opportunity=0, primitive="span_create")
    writer.close()
    first = hashlib.sha256(path.read_bytes()).hexdigest()
    assert path.read_bytes()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == first
