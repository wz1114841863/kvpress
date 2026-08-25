import json

from tools.simulate_kvzap_route_a3_edge import admission_task, load_architecture_config, schedule_admission


def test_admission_task_rounds_to_declared_memory_bursts():
    row = {"hot_to_cold_read_bytes": "50", "cold_write_bytes": "34"}
    page = {"metadata_update_bytes": "16"}
    task = admission_task(row, page, bandwidth=64, burst_bytes=64, pack_bytes_per_cycle=100, page_setup_cycles=2, metadata_bytes_per_page=16)
    assert task == {"bytes": 100.0, "transfer": 2.0, "pack": 1.0, "setup": 2.0, "service": 4.0}


def test_shared_admission_engines_use_lpt_makespan():
    tasks = [{"bytes": 0.0, "transfer": 0.0, "pack": 0.0, "setup": 0.0, "service": value} for value in (8.0, 7.0, 1.0)]
    result = schedule_admission(tasks, engine_count=2)
    assert result["service"] == 8.0
    assert result["task_count"] == 3.0


def test_qwen_edge_descriptor_is_internally_consistent(tmp_path):
    descriptor = {
        "schema_version": "kvzap-route-a3-edge-target-1.0",
        "model": {"hf_id": "model", "num_hidden_layers": 1, "num_attention_heads": 4, "num_key_value_heads": 2, "head_dim": 8, "gqa_group_size": 2, "kv_bytes_per_layer_head_token": 32},
        "edge_execution": {"attention_engine_candidates": [4]},
    }
    path = tmp_path / "target.json"
    path.write_text(json.dumps(descriptor), encoding="utf-8")
    assert load_architecture_config(path)["model"]["gqa_group_size"] == 2
