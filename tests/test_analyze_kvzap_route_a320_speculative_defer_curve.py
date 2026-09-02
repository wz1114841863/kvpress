import csv
import json

from tools.analyze_kvzap_route_a320_speculative_defer_curve import parse_args, run


HARDWARE = {
    "bank_count": 16,
    "burst_bytes": 64,
    "bank_bytes_per_cycle": 64.0,
    "pending_layout": "round_robin_token",
    "staging_capacity_tokens_per_layer": 8192,
}


def write_memory(directory):
    directory.mkdir()
    (directory / "deferred_memory_system_manifest.json").write_text(
        json.dumps({"schema_version": "kvzap-route-a311-deferred-memory-system-dse-1.0"})
    )
    summary_fields = ["request_id", "deferred_decode_steps", "admission_flush_token_budget", *HARDWARE, "decode_steps", "initial_full_kv_call_count", "staging_full_kv_call_count", "net_bytes_saved_fraction", "net_cycle_proxy_saved_fraction"]
    step_fields = ["request_id", "deferred_decode_steps", "admission_flush_token_budget", *HARDWARE, "decode_step", "full_total_bytes", "candidate_total_bytes", "full_total_cycle_proxy", "candidate_total_cycle_proxy"]
    # D=0 pays admission then recovers; D=2 never activates in two calls.
    values = {0: [(100.0, 120.0), (100.0, 60.0)], 1: [(100.0, 100.0), (100.0, 70.0)], 2: [(100.0, 100.0), (100.0, 100.0)]}
    with (directory / "deferred_memory_system_step_results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=step_fields); writer.writeheader()
        for defer, points in values.items():
            for step, (full, candidate) in enumerate(points, start=1):
                writer.writerow({"request_id": "unit", "deferred_decode_steps": defer, "admission_flush_token_budget": 512, **HARDWARE, "decode_step": step, "full_total_bytes": full, "candidate_total_bytes": candidate, "full_total_cycle_proxy": full, "candidate_total_cycle_proxy": candidate})
    with (directory / "deferred_memory_system_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=summary_fields); writer.writeheader()
        for defer, points in values.items():
            full, candidate = sum(x for x, _ in points), sum(x for _, x in points)
            writer.writerow({"request_id": "unit", "deferred_decode_steps": defer, "admission_flush_token_budget": 512, **HARDWARE, "decode_steps": 2, "initial_full_kv_call_count": defer, "staging_full_kv_call_count": 0, "net_bytes_saved_fraction": (full-candidate)/full, "net_cycle_proxy_saved_fraction": (full-candidate)/full})


def args_for(memory, output):
    return parse_args(["--deferred-memory-dir", str(memory), "--workload-label", "unit", "--deferred-decode-steps-points", "0", "1", "2", "--admission-flush-token-budget", "512", "--output-dir", str(output)])


def test_a320_reports_prefix_drop_recovery_and_unactivated_full_kv(tmp_path):
    memory = tmp_path / "memory"; write_memory(memory)
    final, prefix, summary, provenance = run(args_for(memory, tmp_path / "out"))
    assert provenance["unit"]["request_id"] == "unit"
    assert [row["net_cycle_proxy_saved_fraction"] for row in prefix if row["deferred_decode_steps"] == 0] == [-0.2, 0.1]
    d2 = next(row for row in final if row["deferred_decode_steps"] == 2)
    assert d2["final_policy_class"] == "strict_full_kv_no_admission"
    assert d2["net_cycle_proxy_saved_fraction"] == 0.0
    assert summary[0]["best_final_deferred_decode_steps"] == 1


def test_a320_rejects_missing_dense_defer_point(tmp_path):
    memory = tmp_path / "memory"; write_memory(memory)
    for name in ("deferred_memory_system_step_results.csv", "deferred_memory_system_summary.csv"):
        path = memory / name
        rows = list(csv.DictReader(path.open()))
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys()); writer.writeheader()
            writer.writerows(row for row in rows if row["deferred_decode_steps"] != "1")
    try:
        run(args_for(memory, tmp_path / "out"))
    except ValueError as error:
        assert "missing requested dense defer points" in str(error)
    else:
        raise AssertionError("missing D=1 was accepted")
