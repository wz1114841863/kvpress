import json

from tools.freeze_kvzap_route_a315_lifecycle import ARTIFACTS, build


def test_build_freeze_uses_lifecycle_directory_name_and_all_artifact_hashes(tmp_path, monkeypatch):
    lifecycle = tmp_path / "life"; lifecycle.mkdir()
    for name in ARTIFACTS:
        (lifecycle / name).write_text(name)
    monkeypatch.setattr("tools.freeze_kvzap_route_a315_lifecycle.validate", lambda directory: {"events": 1})
    (lifecycle / "lifecycle_manifest.json").write_text(json.dumps({
        "request_id": "r", "model": "m", "model_revision": "mr", "predictor_checkpoint": "p", "predictor_revision": "pr", "threshold": -4.0, "sliding_window": 128, "page_tokens": 64, "kv_bytes_per_layer_head_token": 512, "metadata_bytes_per_cold_page": 16,
        "decode_lifecycle_observation": {"decode_model_call_count": 17}, "config": {"max_new_tokens": 128},
    }))
    freeze = build(lifecycle)
    assert freeze["schema_version"] == "kvzap-route-a2-lifecycle-freeze-1.0"
    assert set(freeze["artifact_sha256"]["life"]) == set(ARTIFACTS)
    assert freeze["validated_samples"][0]["decode_model_call_count"] == 17
