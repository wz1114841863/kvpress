from kvpress.route_a_measurement import A412_RAW_SCHEMA, A4147_RAW_SCHEMA, CudaMemorySnapshot, TimingSample, raw_record, validate_raw_repetition
from tools.run_kvzap_route_a412_whole_decode_gate import WHOLE_DECODE_COMPONENT, schedule_runs, token_ids_hash, whole_decode_summary
from tools.run_kvzap_route_a4147_qwen_external_storage_whole_decode_measurement import EXTERNAL_STORAGE_PATH, MEASUREMENT_PATHS, compact_route_state


def snapshot():
    return CudaMemorySnapshot(allocated_bytes=1, reserved_bytes=2, peak_allocated_bytes=3, peak_reserved_bytes=4)


def make_whole_record(*, path: str, repetition: int, order: int, warmup: bool, tokens: int) -> dict:
    record = raw_record(path=path, component=WHOLE_DECODE_COMPONENT, repetition=repetition, execution_order=order, warmup=warmup, timing=TimingSample(wall_ms=float(order + 1), cuda_event_ms=float(order + 2)), memory_before=snapshot(), memory_after=snapshot(), schema_version=A412_RAW_SCHEMA)
    record.update({"generated_token_count": tokens, "generated_token_ids_sha256": token_ids_hash(list(range(tokens))), "answer_sha256": token_ids_hash([tokens]), "timed_region": "question_forward_plus_greedy_decode"})
    return record


def test_whole_decode_schedule_has_all_three_paths_per_reset_run():
    schedule = schedule_runs(warmups=1, measured=2, seed=42)
    assert len(schedule) == 9
    assert sum(warmup for _path, _repetition, warmup in schedule) == 3
    for warmup, expected_repetitions in ((True, {0}), (False, {0, 1})):
        rows = [(path, repetition) for path, repetition, is_warmup in schedule if is_warmup == warmup]
        assert {repetition for _path, repetition in rows} == expected_repetitions
        for repetition in expected_repetitions:
            assert {path for path, current in rows if current == repetition} == {"full_kv_bypass", "same_mask_dense_replay", "same_mask_route_a_replay"}


def test_whole_decode_summary_keeps_one_timed_record_per_reset_run():
    records = [
        make_whole_record(path="full_kv_bypass", repetition=0, order=0, warmup=True, tokens=2),
        make_whole_record(path="full_kv_bypass", repetition=0, order=1, warmup=False, tokens=3),
        make_whole_record(path="full_kv_bypass", repetition=1, order=2, warmup=False, tokens=4),
        make_whole_record(path="same_mask_dense_replay", repetition=0, order=3, warmup=False, tokens=3),
        make_whole_record(path="same_mask_dense_replay", repetition=1, order=4, warmup=False, tokens=3),
    ]
    summary = whole_decode_summary(records, outcomes=[])
    assert summary["schema_version"] == "kvzap-route-a41-summary-1.1"
    full_group = next(group for group in summary["reset_run_aggregate_groups"] if group["path"] == "full_kv_bypass")
    assert full_group["reported_reset_runs"] == 2
    assert full_group["callback_count_per_reset_run"]["mean"] == 1.0
    full_tokens = next(group for group in summary["whole_decode_generated_tokens"] if group["path"] == "full_kv_bypass")
    assert full_tokens["generated_token_count"]["mean"] == 3.5


def test_external_storage_measurement_schedule_keeps_three_distinct_controls():
    schedule = schedule_runs(warmups=1, measured=1, seed=42, paths=MEASUREMENT_PATHS)
    assert len(schedule) == 6
    assert {path for path, _repetition, _warmup in schedule} == set(MEASUREMENT_PATHS)
    record = make_whole_record(path=EXTERNAL_STORAGE_PATH, repetition=0, order=0, warmup=False, tokens=8)
    record["schema_version"] = A4147_RAW_SCHEMA
    validate_raw_repetition(record)


def test_external_storage_measurement_outcome_is_bounded_scalar_summary():
    coverage = {"layers": [{"layer": 0, "heads": [{"kv_head": 0, "ever_pending": False, "max_packed_page_count": 2, "max_packed_full_page_count": 1, "max_packed_tail_tokens": 3}]}]}
    page = {"witnesses": [{"layer": 0, "kv_head": 0}]}
    ulp = {"layers": [{"layer": 0, "breach_count": 2, "max_observed_ulps": 17.0}]}
    assert compact_route_state(coverage=coverage, page_coverage=page, ulp=ulp) == {
        "selected_layer_count": 1, "selected_kv_head_count": 1, "pending_head_count": 0,
        "page_witness_count": 1, "max_packed_page_count": 2, "max_packed_full_page_count": 1,
        "max_packed_tail_tokens": 3, "execution_dtype_ulp_breach_count": 2,
        "execution_dtype_ulp_max": 17.0,
    }
