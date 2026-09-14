#!/usr/bin/env python3
"""No-model M0 provenance/compatibility gate for cached Nous Llama 3.1 8B."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, hf_hub_download

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-llama31-m0-provenance-1.0"
DEFAULT_MODEL_REPO = "NousResearch/Meta-Llama-3.1-8B-Instruct"
DEFAULT_MODEL_REVISION = "d10aef7999a2b5ba950ab3974312feeedbfe0b77"
OFFICIAL_PREDICTOR_REPO = "nvidia/KVzap-linear-Llama-3.1-8B-Instruct"
EXPECTED = {"model_type": "llama", "architecture": "LlamaForCausalLM", "hidden_size": 4096, "num_hidden_layers": 32, "num_attention_heads": 32, "num_key_value_heads": 8}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_directory(hf_home: Path, repo_id: str, revision: str) -> Path:
    return hf_home / "hub" / f"models--{repo_id.replace('/', '--')}" / "snapshots" / revision


def derived_predictor_repo_id(model_repo_id: str) -> str:
    return f"nvidia/KVzap-linear-{model_repo_id.rstrip('/').split('/')[-1]}"


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required file is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def json_record(path: Path, root: Path) -> dict[str, Any]:
    load_json(path)
    return {"relative_path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def inspect_base_snapshot(hf_home: Path, repo_id: str, revision: str) -> tuple[dict[str, Any], dict[str, Any]]:
    root = snapshot_directory(hf_home, repo_id, revision)
    if not root.is_dir():
        raise FileNotFoundError(f"fixed-revision base snapshot is absent: {root}")
    config_path, tokenizer_path, index_path = root / "config.json", root / "tokenizer_config.json", root / "model.safetensors.index.json"
    config, index = load_json(config_path), load_json(index_path)
    weight_map = index.get("weight_map")
    if not isinstance(weight_map, dict) or not weight_map:
        raise ValueError("model.safetensors.index.json has no nonempty weight_map")
    shards = sorted(set(weight_map.values()))
    if any(not isinstance(name, str) or not name.endswith(".safetensors") for name in shards):
        raise ValueError("weight_map contains a non-safetensors shard")
    shard_records = []
    for name in shards:
        path = root / name
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(f"declared safetensors shard absent or empty: {path}")
        shard_records.append({"relative_path": name, "bytes": path.stat().st_size})
    return config, {"repo_id": repo_id, "revision": revision, "snapshot_path": str(root), "config_files": [json_record(config_path, root), json_record(tokenizer_path, root), json_record(index_path, root)], "declared_safetensors_shards": shard_records, "base_weights_loaded": False}


def validate_llama_config(config: dict[str, Any]) -> dict[str, int]:
    for key, expected in EXPECTED.items():
        actual = config.get("architectures", []) if key == "architecture" else config.get(key)
        valid = expected in actual if key == "architecture" else actual == expected
        if not valid:
            raise ValueError(f"unexpected Llama config {key}: {actual!r}; expected {expected!r}")
    q_heads, kv_heads = int(config["num_attention_heads"]), int(config["num_key_value_heads"])
    if q_heads % kv_heads:
        raise ValueError("num_attention_heads is not divisible by num_key_value_heads")
    return {"hidden_size": int(config["hidden_size"]), "layer_count": int(config["num_hidden_layers"]), "query_head_count": q_heads, "kv_head_count": kv_heads, "query_heads_per_kv_head_group": q_heads // kv_heads}


def resolve_predictor_revision(repo_id: str, requested: str | None, offline: bool, hf_home: Path) -> str:
    if requested:
        return requested
    if offline:
        ref = hf_home / "hub" / f"models--{repo_id.replace('/', '--')}" / "refs" / "main"
        if not ref.is_file():
            raise FileNotFoundError("offline predictor revision unavailable; pass --predictor-revision or disable --offline")
        return ref.read_text(encoding="utf-8").strip()
    revision = HfApi(endpoint="https://huggingface.co").model_info(repo_id=repo_id).sha
    if not revision:
        raise ValueError(f"predictor metadata has no revision: {repo_id}")
    return revision


def inspect_predictor_config(repo_id: str, revision: str, offline: bool, hf_home: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = Path(hf_hub_download(repo_id=repo_id, filename="config.json", revision=revision, cache_dir=str(hf_home / "hub"), local_files_only=offline))
    return load_json(path), {"repo_id": repo_id, "resolved_revision": revision, "config_path": str(path), "config_bytes": path.stat().st_size, "config_sha256": sha256_file(path), "predictor_weights_loaded": False}


def validate_linear_predictor(config: dict[str, Any], dimensions: dict[str, int]) -> None:
    expected = {"model_type": "kvzap", "input_dim": dimensions["hidden_size"], "output_dim": dimensions["kv_head_count"], "n_modules": dimensions["layer_count"]}
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"unexpected predictor config {key}: {config.get(key)!r}; expected {value!r}")
    if config.get("hidden_dim") is not None:
        raise ValueError("M0 requires a Linear predictor (hidden_dim must be null)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M0 no-model provenance gate for Nous Llama 3.1 8B and the derived KVzap Linear predictor.")
    parser.add_argument("--hf-home", type=Path, default=Path(os.environ.get("HF_HOME", "")))
    parser.add_argument("--model-repo-id", default=DEFAULT_MODEL_REPO)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--predictor-repo-id", default=OFFICIAL_PREDICTOR_REPO, help="Official candidate predictor to inspect; M0 records whether it matches KVzapPress's direct derivation.")
    parser.add_argument("--predictor-repo-id-override", default=None, help="Explicit default-off KVzapPress override to bind to the inspected official predictor.")
    parser.add_argument("--predictor-revision", default=None)
    parser.add_argument("--offline", action="store_true", help="Require cached predictor metadata/config; make no network request.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if not str(args.hf_home):
        raise ValueError("--hf-home is required when HF_HOME is unset")
    predictor_repo = args.predictor_repo_id
    if predictor_repo != OFFICIAL_PREDICTOR_REPO:
        raise ValueError(f"unexpected official Linear predictor repository: {predictor_repo}")
    base_config, base = inspect_base_snapshot(args.hf_home, args.model_repo_id, args.model_revision)
    dimensions = validate_llama_config(base_config)
    predictor_revision = resolve_predictor_revision(predictor_repo, args.predictor_revision, args.offline, args.hf_home)
    predictor_config, predictor = inspect_predictor_config(predictor_repo, predictor_revision, args.offline, args.hf_home)
    validate_linear_predictor(predictor_config, dimensions)
    config = {"hf_home": str(args.hf_home), "model_repo_id": args.model_repo_id, "model_revision": args.model_revision, "predictor_repo_id": predictor_repo, "predictor_repo_id_override": args.predictor_repo_id_override, "predictor_revision_requested": args.predictor_revision, "predictor_revision_resolved": predictor_revision, "offline": args.offline}
    if args.predictor_repo_id_override not in (None, predictor_repo):
        raise ValueError("--predictor-repo-id-override must exactly match --predictor-repo-id")
    derived_repo = derived_predictor_repo_id(args.model_repo_id)
    direct_derivation_matches = derived_repo == predictor_repo
    override_bound = args.predictor_repo_id_override == predictor_repo
    status = "complete" if direct_derivation_matches or override_bound else "blocked"
    report = {"schema_version": SCHEMA, "status": status, "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "no-model provenance validation; base and predictor weights were not loaded", "base_model_snapshot": base, "base_model_structure": dimensions, "kvzap_predictor": predictor, "adapter_contract": {"kvzap_press_model_type": "linear", "kvzappress_direct_predictor_repo_id": derived_repo, "official_candidate_predictor_repo_id": predictor_repo, "direct_kvzappress_derivation_matches_official_candidate": direct_derivation_matches, "predictor_repo_id_override": args.predictor_repo_id_override, "explicit_nondefault_override_bound": override_bound, "threshold_for_later_M1": -7.0, "hot_window_tokens_for_later_M1": 128}, "observational_guards": {"fixed_base_snapshot_present": True, "declared_safetensors_shards_present": True, "llama_structure_matches_expected": True, "official_predictor_linear_dimensions_match_base_structure": True, "no_base_or_predictor_weights_loaded": True, "direct_derivation_or_explicit_override_bound": direct_derivation_matches or override_bound}, "blockers": [] if status == "complete" else ["KVzapPress derives its predictor ID from the Nous base-model basename, which differs from the official Llama predictor repository name. M1 requires an explicit nondefault predictor override and a fresh M0/M1 provenance binding."], "boundaries": ["This M0 report is observed cache/Hub provenance plus code-derived JSON compatibility only.", "NousResearch provenance is not an official Meta model reproduction claim.", "The override is default-off; M0 does not change or validate any default pruning path.", "M0 establishes no generated output, mask, attention, Route-A lifecycle, accuracy, traffic, latency, throughput, energy, area, hardware parameter, architecture-specification, or RTL claim."]}
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "llama31_m0_provenance_manifest.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"M0 provenance gate {status}: {path}")


if __name__ == "__main__":
    main()
