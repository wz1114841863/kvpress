import csv
import json

from tools.summarize_kvzap_route_a39_cross_workload import load_fixed_point


def test_load_fixed_point_requires_continue_admission_and_filters_threshold(tmp_path):
    directory = tmp_path / "gate"
    directory.mkdir()
    (directory / "consistent_gate_manifest.json").write_text(json.dumps({"schema_version": "kvzap-route-a39-consistent-gate-dse-1.0", "assumptions": {"admission_mode": "continue_admission"}}))
    fields = ["request_id", "pending_token_threshold", "max_bank_burst_threshold"]
    with (directory / "consistent_gate_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"request_id": "r", "pending_token_threshold": 0, "max_bank_burst_threshold": 0})
        writer.writerow({"request_id": "r", "pending_token_threshold": 512, "max_bank_burst_threshold": 8})
    _manifest, rows = load_fixed_point(directory, pending=512, bursts=8)
    assert len(rows) == 1
    assert rows[0]["request_id"] == "r"
