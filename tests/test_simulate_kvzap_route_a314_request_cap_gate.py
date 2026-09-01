import csv
import json

from tools.simulate_kvzap_route_a314_request_cap_gate import parse_args, run


def make_pair(root, name, request_id, cap, cycle):
    life, memory = root / f"life_{name}", root / f"memory_{name}"
    life.mkdir(); memory.mkdir()
    (life / "lifecycle_manifest.json").write_text(json.dumps({"schema_version": "kvzap-route-a2-readonly-lifecycle-1.0", "request_id": request_id, "config": {"max_new_tokens": cap}}))
    (memory / "deferred_memory_system_manifest.json").write_text(json.dumps({"schema_version": "kvzap-route-a311-deferred-memory-system-dse-1.0", "lifecycle_dir": str(life)}))
    fields = ["request_id", "deferred_decode_steps", "admission_flush_token_budget", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "net_bytes_saved_fraction", "net_cycle_proxy_saved_fraction"]
    with (memory / "deferred_memory_system_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        writer.writerow({"request_id": request_id, "deferred_decode_steps": 5, "admission_flush_token_budget": 512, "bank_count": 16, "burst_bytes": 128, "bank_bytes_per_cycle": 64, "pending_layout": "round_robin_token", "staging_capacity_tokens_per_layer": 8192, "net_bytes_saved_fraction": 0.4, "net_cycle_proxy_saved_fraction": cycle})
    return life, memory


def test_cap_gate_protects_only_calls_below_visible_cap_threshold(tmp_path):
    short_life, short_memory = make_pair(tmp_path, "short", "short", 32, -0.2)
    long_life, long_memory = make_pair(tmp_path, "long", "long", 128, 0.3)
    args = parse_args(["--lifecycle-dir", str(short_life), "--lifecycle-dir", str(long_life), "--deferred-memory-dir", str(short_memory), "--deferred-memory-dir", str(long_memory), "--workload-label", "short", "--workload-label", "long", "--request-max-new-tokens-thresholds", "33", "--output-dir", str(tmp_path / "out")])
    per, cross, _ = run(args)
    assert {row["gate_path"] for row in per} == {"full_kv_no_admission", "active_deferred_admission"}
    assert cross[0]["all_workloads_nonnegative_cycle"] is True
    assert cross[0]["min_net_cycle_proxy_saved_fraction"] == 0.0
