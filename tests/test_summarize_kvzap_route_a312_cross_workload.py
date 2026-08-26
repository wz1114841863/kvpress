import csv
import json

import pytest

from tools.summarize_kvzap_route_a312_cross_workload import parse_args, run


def make_input(directory, request_id, cycle):
    directory.mkdir()
    (directory / "deferred_memory_system_manifest.json").write_text(json.dumps({"schema_version": "kvzap-route-a311-deferred-memory-system-dse-1.0"}))
    fields = ["request_id", "deferred_decode_steps", "admission_flush_token_budget", "bank_count", "burst_bytes", "bank_bytes_per_cycle", "pending_layout", "staging_capacity_tokens_per_layer", "net_bytes_saved_fraction", "net_cycle_proxy_saved_fraction", "initial_full_kv_call_count", "staging_full_kv_call_count", "staging_full_kv_layer_count"]
    with (directory / "deferred_memory_system_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        writer.writerow({"request_id": request_id, "deferred_decode_steps": 5, "admission_flush_token_budget": 512, "bank_count": 16, "burst_bytes": 128, "bank_bytes_per_cycle": 64.0, "pending_layout": "round_robin_token", "staging_capacity_tokens_per_layer": 8192, "net_bytes_saved_fraction": 0.4, "net_cycle_proxy_saved_fraction": cycle, "initial_full_kv_call_count": 5, "staging_full_kv_call_count": 2, "staging_full_kv_layer_count": 7})


def test_cross_summary_uses_worst_workload(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"; make_input(one, "r1", 0.3); make_input(two, "r2", 0.1)
    args = parse_args(["--deferred-memory-dir", str(one), "--deferred-memory-dir", str(two), "--workload-label", "retrieval", "--workload-label", "summarization", "--output-dir", str(tmp_path / "out")])
    per, cross, _ = run(args)
    assert len(per) == 2 and cross[0]["all_workloads_positive_cycle"] is True
    assert cross[0]["min_net_cycle_proxy_saved_fraction"] == 0.1 and cross[0]["worst_cycle_workload"] == "summarization"


def test_cross_summary_rejects_unaligned_sweeps(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"; make_input(one, "r1", 0.3); make_input(two, "r2", 0.1)
    path = two / "deferred_memory_system_summary.csv"; path.write_text(path.read_text().replace(",16,128,64.0,", ",8,128,64.0,"))
    args = parse_args(["--deferred-memory-dir", str(one), "--deferred-memory-dir", str(two), "--workload-label", "retrieval", "--workload-label", "summarization", "--output-dir", str(tmp_path / "out")])
    with pytest.raises(ValueError, match="policy/hardware points disagree"):
        run(args)
