import gzip
import json

from tools.analyze_kvzap_route_a450_capacity_protection_replay import replay_request


def test_a450_activation_boundary_protects_without_consuming_route_a_epochs(tmp_path):
    experiments = tmp_path / "analysis" / "experiments"
    run = experiments / "source"
    run.mkdir(parents=True)
    trace_path = run / "unused.jsonl.gz"
    with gzip.open(trace_path, "wt", encoding="utf-8") as handle:
        for layer in range(2):
            handle.write(json.dumps({
                "layer": layer,
                "start_position": 9,
                "heads": [{"pending_tokens_before_maturity": 1, "pending_tokens_after_service": 1}],
            }) + "\n")
    source = {
        "activation_contract": {
            "deferred_activation_summary": {"layers": [
                {"layer": 0, "activation_event": {"heads": [{"pending_tokens_after_commit": 8}]}},
                {"layer": 1, "activation_event": {"heads": [{"pending_tokens_after_commit": 2}]}},
            ]},
        },
        "post_commit_logical_trace": {"path": "source/unused.jsonl.gz"},
    }
    result = replay_request(
        anchor="test", workload="retrieval", report_path=run / "report.json", source_row=source,
        layer_count=2, high_watermark=8,
    )
    assert result["mode_at_trace_end"] == "protected_full_kv"
    assert result["transition"]["boundary"] == "activation_commit_before_current_decode_append"
    assert result["route_a_logical_epochs_consumed_before_protection"] == 0
    assert result["route_a_logical_epochs_bypassed_after_protection"] == 1
    assert result["contract_predicates"]["no_post_protection_route_a_logical_admission_or_drop"] is True
