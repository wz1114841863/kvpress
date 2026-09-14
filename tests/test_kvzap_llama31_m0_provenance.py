import json
from pathlib import Path

import pytest

from tools.validate_kvzap_llama31_m0_provenance import DEFAULT_MODEL_REPO, DEFAULT_MODEL_REVISION, EXPECTED_PREDICTOR_REPO, derived_predictor_repo_id, inspect_base_snapshot, validate_linear_predictor, validate_llama_config


def base_config(**updates):
    value = {"architectures": ["LlamaForCausalLM"], "model_type": "llama", "hidden_size": 4096, "num_hidden_layers": 32, "num_attention_heads": 32, "num_key_value_heads": 8}
    value.update(updates)
    return value


def make_snapshot(tmp_path: Path, *, config=None, shards=True):
    root = tmp_path / "hub" / "models--NousResearch--Meta-Llama-3.1-8B-Instruct" / "snapshots" / DEFAULT_MODEL_REVISION
    root.mkdir(parents=True)
    (root / "config.json").write_text(json.dumps(config or base_config()))
    (root / "tokenizer_config.json").write_text("{}")
    names = ["model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors"]
    (root / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {"a": names[0], "b": names[1]}}))
    if shards:
        for name in names:
            (root / name).write_bytes(b"weight")


def test_derives_supported_linear_predictor_id():
    assert derived_predictor_repo_id(DEFAULT_MODEL_REPO) == EXPECTED_PREDICTOR_REPO


def test_snapshot_and_llama_dimensions_are_checked(tmp_path):
    make_snapshot(tmp_path)
    config, provenance = inspect_base_snapshot(tmp_path, DEFAULT_MODEL_REPO, DEFAULT_MODEL_REVISION)
    assert provenance["base_weights_loaded"] is False
    assert len(provenance["declared_safetensors_shards"]) == 2
    assert validate_llama_config(config) == {"hidden_size": 4096, "layer_count": 32, "query_head_count": 32, "kv_head_count": 8, "query_heads_per_kv_head_group": 4}


def test_missing_declared_shard_is_rejected(tmp_path):
    make_snapshot(tmp_path, shards=False)
    with pytest.raises(FileNotFoundError, match="declared safetensors"):
        inspect_base_snapshot(tmp_path, DEFAULT_MODEL_REPO, DEFAULT_MODEL_REVISION)


def test_unexpected_llama_query_head_count_is_rejected():
    with pytest.raises(ValueError, match="num_attention_heads"):
        validate_llama_config(base_config(num_attention_heads=31))


def test_predictor_must_be_linear_and_dimension_matched():
    dimensions = {"hidden_size": 4096, "layer_count": 32, "query_head_count": 32, "kv_head_count": 8, "query_heads_per_kv_head_group": 4}
    validate_linear_predictor({"model_type": "kvzap", "input_dim": 4096, "output_dim": 8, "n_modules": 32, "hidden_dim": None}, dimensions)
    with pytest.raises(ValueError, match="hidden_dim"):
        validate_linear_predictor({"model_type": "kvzap", "input_dim": 4096, "output_dim": 8, "n_modules": 32, "hidden_dim": 512}, dimensions)
