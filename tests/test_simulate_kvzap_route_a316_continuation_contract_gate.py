import csv
import json

from tools.simulate_kvzap_route_a316_continuation_contract_gate import parse_args, run


def make_pair(root, name, declared_steps, observed_steps, cycle):
    life, memory = root / f"life_{name}", root / f"memory_{name}"
    life.mkdir(); memory.mkdir()
    (life / "lifecycle_manifest.json").write_text(json.dumps({"schema_version": "kvzap-route-a2-readonly-lifecycle-1.0", "request_id": name, "decode_lifecycle_observation": {"decode_model_call_count": observed_steps}}))
    (memory / "deferred_memory_system_manifest.json").write_text(json.dumps({"schema_version": "kvzap-route-a311-deferred-memory-system-dse-1.0", "lifecycle_dir": str(life)}))
    fields = ["deferred_decode_steps", "admission_flush_token_budget", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "net_bytes_saved_fraction", "net_cycle_proxy_saved_fraction"]
    with (memory / "deferred_memory_system_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        writer.writerow({"deferred_decode_steps": 5, "admission_flush_token_budget": 512, "bank_count": 16, "burst_bytes": 64, "bank_bytes_per_cycle": 64, "pending_layout": "round_robin_token", "staging_capacity_tokens_per_layer": 8192, "net_bytes_saved_fraction": 0.4, "net_cycle_proxy_saved_fraction": cycle})
    return life, memory, declared_steps


def test_lower_bound_contract_protects_short_no_contract_request_and_audits_it(tmp_path):
    short_life, short_memory, short_contract = make_pair(tmp_path, "short", 0, 17, -0.2)
    long_life, long_memory, long_contract = make_pair(tmp_path, "long", 64, 127, 0.3)
    args = parse_args(["--lifecycle-dir", str(short_life), "--lifecycle-dir", str(long_life), "--deferred-memory-dir", str(short_memory), "--deferred-memory-dir", str(long_memory), "--workload-label", "short", "--workload-label", "long", "--declared-minimum-continuation-calls", str(short_contract), "--declared-minimum-continuation-calls", str(long_contract), "--required-minimum-continuation-calls", "32", "--output-dir", str(tmp_path / "out")])
    per, cross, audit, _ = run(args)
    assert {row["gate_path"] for row in per} == {"full_kv_no_admission", "active_deferred_admission"}
    assert cross[0]["all_declared_contracts_held_by_observed_trace"] is True
    assert cross[0]["all_workloads_nonnegative_cycle"] is True
    assert all(row["contract_held_by_observed_trace"] is True for row in audit)


def test_broken_contract_is_reported_not_used_as_trace_selection(tmp_path):
    left_life, left_memory, left_contract = make_pair(tmp_path, "left", 64, 17, 0.3)
    right_life, right_memory, right_contract = make_pair(tmp_path, "right", 64, 127, 0.3)
    args = parse_args(["--lifecycle-dir", str(left_life), "--lifecycle-dir", str(right_life), "--deferred-memory-dir", str(left_memory), "--deferred-memory-dir", str(right_memory), "--workload-label", "left", "--workload-label", "right", "--declared-minimum-continuation-calls", str(left_contract), "--declared-minimum-continuation-calls", str(right_contract), "--required-minimum-continuation-calls", "32", "--output-dir", str(tmp_path / "out")])
    per, cross, audit, _ = run(args)
    assert {row["gate_path"] for row in per} == {"active_deferred_admission"}
    assert cross[0]["all_declared_contracts_held_by_observed_trace"] is False
    assert audit[0]["contract_held_by_observed_trace"] is False
