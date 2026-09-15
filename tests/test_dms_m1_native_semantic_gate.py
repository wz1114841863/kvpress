import json
from pathlib import Path

import pytest

from tools.run_dms_route_a_m1_native_semantic_gate import (
    DMSUpdateRecorder,
    EXPECTED_KV_HEADS,
    M0_SCHEMA,
    OFFICIAL_DMS_REPO,
    OFFICIAL_DMS_REVISION,
    read_completed_m0,
    summarize_events,
)


class _ParentCache:
    def update(self):
        return "parent"


class _ChildDMSCache(_ParentCache):
    pass


def _m0(tmp_path: Path, *, status: str = "complete") -> Path:
    path = tmp_path / "m0.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": M0_SCHEMA,
                "status": status,
                "official_snapshot": {
                    "repo_id": OFFICIAL_DMS_REPO,
                    "revision": OFFICIAL_DMS_REVISION,
                    "snapshot_root": "/fixed/dms",
                },
                "runtime_probe": {
                    "status": "passed",
                    "model_weights_loaded": True,
                    "generation_calls": 0,
                    "tokenizer_provenance": {"root": "/fixed/tokenizer", "selected_file_sha256": {"tokenizer.json": "a"}},
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_m1_requires_completed_m0_with_successful_prefill_and_tokenizer(tmp_path):
    report = read_completed_m0(_m0(tmp_path))
    assert report["official_snapshot"]["revision"] == OFFICIAL_DMS_REVISION
    with pytest.raises(ValueError, match="completed"):
        read_completed_m0(_m0(tmp_path / "blocked", status="blocked"))


def test_m1_event_summary_requires_full_layer_coverage_and_reports_native_eviction():
    events = []
    for layer in range(36):
        for step in range(3):
            history = 600 + step
            events.append(
                {
                    "layer": layer,
                    "kind": "prefill" if step == 0 else "decode",
                    "q_len": 600 if step == 0 else 1,
                    "decision_ones_by_kv_head": [1] * EXPECTED_KV_HEADS,
                    "cache_lengths_after": [512] * EXPECTED_KV_HEADS,
                }
            )
    summary = summarize_events(events, decode_steps=2)
    assert summary["all_36_layers_all_8_kv_heads_covered"] is True
    assert summary["native_eviction_observed"] is True
    assert summary["decision_ones_total"] == 36 * 3 * EXPECTED_KV_HEADS


def test_m1_recorder_binds_the_inherited_update_method_before_installing_wrapper():
    assert DMSUpdateRecorder.inherited_update_method(_ChildDMSCache) is _ParentCache.update
