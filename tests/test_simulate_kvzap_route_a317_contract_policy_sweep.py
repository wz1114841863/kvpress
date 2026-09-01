import csv
import json

from tools.simulate_kvzap_route_a317_contract_policy_sweep import main, parse_args, run


def pair(root, name, declared, observed, values):
    life, memory = root / f"life_{name}", root / f"memory_{name}"; life.mkdir(); memory.mkdir()
    (life / "lifecycle_manifest.json").write_text(json.dumps({"schema_version": "kvzap-route-a2-readonly-lifecycle-1.0", "request_id": name, "decode_lifecycle_observation": {"decode_model_call_count": observed}}))
    (memory / "deferred_memory_system_manifest.json").write_text(json.dumps({"schema_version": "kvzap-route-a311-deferred-memory-system-dse-1.0", "lifecycle_dir": str(life)}))
    fields = ["deferred_decode_steps", "admission_flush_token_budget", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "net_bytes_saved_fraction", "net_cycle_proxy_saved_fraction"]
    with (memory / "deferred_memory_system_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for defer, cycle in values.items(): writer.writerow({"deferred_decode_steps": defer, "admission_flush_token_budget": 512, "bank_count": 16, "burst_bytes": 64, "bank_bytes_per_cycle": 64, "pending_layout": "round_robin_token", "staging_capacity_tokens_per_layer": 8192, "net_bytes_saved_fraction": 0.4, "net_cycle_proxy_saved_fraction": cycle})
    return life, memory, declared


def test_sweep_reports_policy_specific_contract_gate_and_active_only_positive_status(tmp_path):
    a_life, a_mem, a_contract = pair(tmp_path, "short", 0, 17, {0: -0.2, 5: -0.1})
    b_life, b_mem, b_contract = pair(tmp_path, "long", 64, 127, {0: 0.4, 5: 0.3})
    args = parse_args(["--lifecycle-dir", str(a_life), "--lifecycle-dir", str(b_life), "--deferred-memory-dir", str(a_mem), "--deferred-memory-dir", str(b_mem), "--workload-label", "short", "--workload-label", "long", "--declared-minimum-continuation-calls", str(a_contract), "--declared-minimum-continuation-calls", str(b_contract), "--required-minimum-continuation-calls", "0", "32", "--deferred-decode-steps-points", "0", "5", "--admission-flush-token-budget-points", "512", "--output-dir", str(tmp_path / "out")])
    per, cross, audit, _ = run(args)
    assert len(cross) == 4
    protected = [row for row in cross if row["required_minimum_continuation_calls"] == 32 and row["deferred_decode_steps"] == 5][0]
    assert protected["all_workloads_nonnegative_cycle"] is True
    assert protected["all_active_workloads_positive_cycle"] is True
    assert protected["active_workload_count"] == 1
    assert all(row["contract_held_by_observed_trace"] is True for row in audit)
    assert any(row["gate_path"] == "full_kv_no_admission" for row in per)


def test_main_writes_a_new_directory_without_post_write_name_error(tmp_path, monkeypatch):
    left_life, left_memory, left_contract = pair(tmp_path, "left", 0, 17, {5: -0.2})
    right_life, right_memory, right_contract = pair(tmp_path, "right", 64, 127, {5: 0.3})
    output = tmp_path / "out"
    argv = ["tool", "--lifecycle-dir", str(left_life), "--lifecycle-dir", str(right_life), "--deferred-memory-dir", str(left_memory), "--deferred-memory-dir", str(right_memory), "--workload-label", "left", "--workload-label", "right", "--declared-minimum-continuation-calls", str(left_contract), "--declared-minimum-continuation-calls", str(right_contract), "--required-minimum-continuation-calls", "32", "--deferred-decode-steps-points", "5", "--admission-flush-token-budget-points", "512", "--output-dir", str(output)]
    monkeypatch.setattr("sys.argv", argv)
    main()
    assert (output / "contract_policy_sweep_manifest.json").is_file()
