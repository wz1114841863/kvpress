import json
from pathlib import Path

import pytest
import torch
from safetensors.torch import save_file

from tools.validate_dms_m0_official_provenance import (
    OFFICIAL_DMS_REVISION,
    REQUIRED_CODE,
    build_manifest,
    inspect_static_snapshot,
    runtime_probe,
)


def _snapshot(tmp_path: Path) -> Path:
    root = tmp_path / OFFICIAL_DMS_REVISION
    root.mkdir(parents=True)
    config = {
        "model_type": "qwen3",
        "dms_cr": 8,
        "dms_window_size": 512,
        "hidden_size": 4096,
        "num_hidden_layers": 36,
        "num_key_value_heads": 8,
        "torch_dtype": "bfloat16",
        "use_cache": True,
        "auto_map": {
            "AutoConfig": "configuration_qwen3_dms.Qwen3Config",
            "AutoModelForCausalLM": "modeling_qwen3_dms.Qwen3ForCausalLM",
        },
    }
    (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
    weight_map = {}
    for index in range(4):
        name = f"model-{index:05d}-of-00004.safetensors"
        save_file({f"tensor_{index}": torch.ones(1)}, root / name)
        weight_map[f"tensor_{index}"] = name
    (root / "model.safetensors.index.json").write_text(json.dumps({"weight_map": weight_map}), encoding="utf-8")
    for name in REQUIRED_CODE:
        (root / name).write_text("class Placeholder:\n    pass\n", encoding="utf-8")
    return root


def test_m0_static_snapshot_accepts_pinned_complete_official_shape(tmp_path):
    static = inspect_static_snapshot(_snapshot(tmp_path))
    assert static["revision"] == OFFICIAL_DMS_REVISION
    assert len(static["weight_shards"]) == 4
    assert all(row["tensor_count"] == 1 for row in static["weight_shards"])
    assert static["static_guards"]["no_checkpoint_custom_code_executed_during_static_inspection"] is True


def test_m0_rejects_drifted_window_or_missing_custom_code(tmp_path):
    root = _snapshot(tmp_path)
    config = json.loads((root / "config.json").read_text())
    config["dms_window_size"] = 128
    (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="dms_window_size"):
        inspect_static_snapshot(root)

    root = _snapshot(tmp_path / "missing")
    (root / REQUIRED_CODE[0]).unlink()
    with pytest.raises(FileNotFoundError, match="required custom code"):
        inspect_static_snapshot(root)


def test_m0_default_runtime_probe_executes_nothing_and_manifest_stays_complete(tmp_path):
    static = inspect_static_snapshot(_snapshot(tmp_path))
    probe = runtime_probe(Path("/not/used"), "none", "cuda:0")
    manifest = build_manifest(static, probe)
    assert probe == {
        "mode": "none",
        "status": "not_requested",
        "custom_code_executed": False,
        "model_weights_loaded": False,
        "generation_calls": 0,
    }
    assert manifest["status"] == "complete"
