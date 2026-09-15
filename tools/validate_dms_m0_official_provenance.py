#!/usr/bin/env python3
"""Validate one cached official DMS checkpoint before any Route-A integration.

M0 is intentionally bounded to provenance and runtime compatibility.  It never
changes KVPress defaults, DMS code, pruning policy, cache layout, or attention
semantics.  The optional runtime probe is an explicit one-prefill smoke test,
not a generation, accuracy, lifecycle, performance, or hardware experiment.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from safetensors import safe_open

from tools.analyze_kvzap_trace import get_git_commit, stable_hash


M0_SCHEMA = "route-a-dms-m0-official-provenance-1.0"
OFFICIAL_DMS_REPO = "nvidia/Qwen3-8B-DMS-8x"
OFFICIAL_DMS_REVISION = "da1535fc3bfb52fa340eca692a7e4e650f98838d"
REQUIRED_CODE = (
    "configuration_qwen3_dms.py",
    "modeling_qwen3_dms.py",
    "dms_attention.py",
    "dms_cache.py",
)
EXPECTED_AUTO_MAP = {
    "AutoConfig": "configuration_qwen3_dms.Qwen3Config",
    "AutoModelForCausalLM": "modeling_qwen3_dms.Qwen3ForCausalLM",
}
EXPECTED_CONFIG = {
    "model_type": "qwen3",
    "dms_cr": 8,
    "dms_window_size": 512,
    "hidden_size": 4096,
    "num_hidden_layers": 36,
    "num_key_value_heads": 8,
    "torch_dtype": "bfloat16",
    "use_cache": True,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "DMS-M0 official checkpoint provenance and optional runtime-compatibility gate; "
            "not a Route-A, quality, performance, or hardware experiment."
        )
    )
    parser.add_argument("--snapshot-root", type=Path, required=True, help="Exact cached official DMS snapshot root.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    parser.add_argument(
        "--runtime-probe",
        choices=("none", "config-only", "model-prefill"),
        default="none",
        help="Explicit compatibility probe; default performs no custom-code execution.",
    )
    parser.add_argument(
        "--device",
        default="cuda:0",
        help="Torch device used only by --runtime-probe model-prefill (default: cuda:0).",
    )
    parser.add_argument(
        "--tokenizer-root",
        type=Path,
        default=None,
        help=(
            "Explicit local tokenizer snapshot used only by --runtime-probe model-prefill. "
            "The official DMS README names Qwen/Qwen3-8B rather than the DMS checkpoint itself. "
            "No network download is attempted."
        ),
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(value: Any, expected: Any, label: str) -> None:
    if value != expected:
        raise ValueError(f"M0 {label} differs from the official DMS contract: {value!r}")


def inspect_static_snapshot(snapshot_root: Path) -> dict[str, Any]:
    """Parse a snapshot without importing any checkpoint-provided Python code."""
    if snapshot_root.name != OFFICIAL_DMS_REVISION:
        raise ValueError("M0 snapshot directory name is not the pinned official revision")
    config_path = snapshot_root / "config.json"
    index_path = snapshot_root / "model.safetensors.index.json"
    if not config_path.is_file() or not index_path.is_file():
        raise FileNotFoundError("M0 snapshot lacks config.json or model.safetensors.index.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for key, expected in EXPECTED_CONFIG.items():
        _require(config.get(key), expected, f"config {key}")
    auto_map = config.get("auto_map")
    if not isinstance(auto_map, dict):
        raise ValueError("M0 config lacks custom-code auto_map")
    for key, expected in EXPECTED_AUTO_MAP.items():
        _require(auto_map.get(key), expected, f"auto_map {key}")
    weight_map = index.get("weight_map")
    if not isinstance(weight_map, dict) or not weight_map:
        raise ValueError("M0 weight index lacks a nonempty weight_map")
    shard_names = sorted(set(weight_map.values()))
    if len(shard_names) != 4 or any(not isinstance(name, str) for name in shard_names):
        raise ValueError("M0 expects exactly four named official Safetensors shards")
    code_sha256 = {}
    for name in REQUIRED_CODE:
        path = snapshot_root / name
        if not path.is_file():
            raise FileNotFoundError(f"M0 snapshot lacks required custom code: {name}")
        ast.parse(path.read_text(encoding="utf-8"), filename=name)
        code_sha256[name] = sha256_file(path)
    shard_rows = []
    for name in shard_names:
        path = snapshot_root / name
        if not path.is_file():
            raise FileNotFoundError(f"M0 indexed weight shard is missing: {name}")
        # ``safe_open`` reads only the safetensors header here; no tensor is materialized.
        with safe_open(path, framework="pt", device="cpu") as shard:
            tensor_count = len(list(shard.keys()))
            if tensor_count <= 0:
                raise ValueError(f"M0 Safetensors shard has no tensors: {name}")
            metadata = shard.metadata()
        shard_rows.append({"name": name, "bytes": path.stat().st_size, "tensor_count": tensor_count, "metadata": metadata})
    return {
        "repo_id": OFFICIAL_DMS_REPO,
        "revision": OFFICIAL_DMS_REVISION,
        "snapshot_root": str(snapshot_root),
        "config_sha256": sha256_file(config_path),
        "safetensors_index_sha256": sha256_file(index_path),
        "custom_code_sha256": code_sha256,
        "config_selected_fields": {key: config[key] for key in EXPECTED_CONFIG},
        "auto_map": auto_map,
        "weight_shards": shard_rows,
        "static_guards": {
            "pinned_official_revision_directory": True,
            "official_dms_config_fields_match": True,
            "required_custom_code_exists_and_parses": True,
            "indexed_safetensors_headers_are_readable": True,
            "no_checkpoint_custom_code_executed_during_static_inspection": True,
            "no_weight_tensor_materialized_during_static_inspection": True,
        },
    }


def _local_tokenizer_provenance(tokenizer_root: Path) -> dict[str, Any]:
    """Record the explicit local tokenizer input without asserting its file layout."""
    root = tokenizer_root.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f"M0 tokenizer root is not a directory: {root}")
    known_names = (
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "vocab.json",
        "merges.txt",
    )
    files = {
        name: sha256_file(root / name)
        for name in known_names
        if (root / name).is_file()
    }
    if not files:
        raise FileNotFoundError(f"M0 tokenizer root has none of the recognized tokenizer files: {root}")
    return {"root": str(root), "selected_file_sha256": files}


def runtime_probe(
    snapshot_root: Path,
    mode: str,
    device: str,
    tokenizer_root: Path | None = None,
) -> dict[str, Any]:
    """Run an explicit minimal local-only compatibility probe, never generation."""
    if mode == "none":
        return {
            "mode": mode,
            "status": "not_requested",
            "custom_code_executed": False,
            "model_weights_loaded": False,
            "generation_calls": 0,
        }
    import torch
    import transformers
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

    outcome: dict[str, Any] = {
        "mode": mode,
        "status": "blocked",
        "custom_code_executed": False,
        "model_weights_loaded": False,
        "generation_calls": 0,
        "runtime": {
            "torch_version": str(torch.__version__),
            "transformers_version": str(transformers.__version__),
            "device_requested": device,
            "cuda_available": bool(torch.cuda.is_available()),
        },
    }
    model = tokenizer = config = None
    try:
        # NVIDIA's DMS README explicitly loads the base Qwen/Qwen3-8B tokenizer.
        # Requiring a local path makes that second artifact visible and prevents an
        # accidental download or a silent assumption that DMS ships tokenizer files.
        tokenizer_provenance = None
        if mode == "model-prefill":
            if tokenizer_root is None:
                raise ValueError("M0 model-prefill requires an explicit --tokenizer-root")
            tokenizer_provenance = _local_tokenizer_provenance(tokenizer_root)
        config = AutoConfig.from_pretrained(snapshot_root, local_files_only=True, trust_remote_code=True)
        outcome["custom_code_executed"] = True
        outcome["config_class"] = f"{type(config).__module__}.{type(config).__name__}"
        if mode == "config-only":
            outcome["status"] = "passed"
            return outcome
        if not torch.cuda.is_available():
            raise RuntimeError("model-prefill requires CUDA; M0 does not fall back to CPU")
        tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_root,
            local_files_only=True,
            trust_remote_code=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            snapshot_root,
            config=config,
            local_files_only=True,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        outcome["model_weights_loaded"] = True
        inputs = tokenizer("DMS M0 compatibility probe.", return_tensors="pt")
        inputs = {key: value.to(model.device) for key, value in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs, use_cache=True)
        logits = outputs.logits.detach()
        if not bool(torch.isfinite(logits).all().item()):
            raise RuntimeError("model-prefill produced non-finite logits")
        sample = logits[0, -1, : min(16, logits.shape[-1])].to(dtype=torch.float32, device="cpu").numpy().tobytes()
        outcome.update(
            {
                "status": "passed",
                "model_class": f"{type(model).__module__}.{type(model).__name__}",
                "tokenizer_provenance": tokenizer_provenance,
                "prefill": {
                    "input_shape": list(inputs["input_ids"].shape),
                    "logits_shape": list(logits.shape),
                    "last_logit_prefix_sha256": hashlib.sha256(sample).hexdigest(),
                    "use_cache": True,
                    "generation_calls": 0,
                },
            }
        )
    except Exception as exc:  # A blocked manifest is the required compatibility evidence.
        outcome["exception"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        del model, tokenizer, config
        if "torch" in locals() and torch.cuda.is_available():
            torch.cuda.empty_cache()
    return outcome


def build_manifest(static: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    status = "complete" if probe["status"] in {"passed", "not_requested"} else "blocked"
    return {
        "schema_version": M0_SCHEMA,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "execution_classification": (
            "official DMS checkpoint provenance/static validation plus optional bounded functional runtime compatibility; "
            "not trace-derived workload, hardware modeled, or hardware measured evidence"
        ),
        "official_snapshot": static,
        "runtime_probe": probe,
        "source_sha256": {"m0_tool": sha256_file(Path(__file__))},
        "boundaries": [
            "M0 does not change KVPress defaults, instantiate DMSPress, create a Route-A event stream, or compare any attention result.",
            "Static validation parses custom-code syntax and Safetensors headers only. The explicit runtime probe may execute official checkpoint code from the pinned local snapshot, but it never downloads files, generates tokens, measures performance, or interprets a successful load as algorithmic correctness.",
            "For model-prefill, the DMS checkpoint and the explicitly supplied local base tokenizer are separate provenance inputs. A blocked runtime probe demonstrates only that those pinned inputs were not compatible with this exact runtime/probe. It is not evidence against trained DMS or Route-A.",
            "M0 selects no page size, FIFO/PTE/bank/burst, merge precision, PE count, scheduler, controller timing, capacity, traffic, latency, throughput, energy, area, architecture specification, or RTL implementation.",
        ],
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"M0 output directory already exists: {args.output_dir}")
    static = inspect_static_snapshot(args.snapshot_root)
    probe = runtime_probe(args.snapshot_root, args.runtime_probe, args.device, args.tokenizer_root)
    manifest = build_manifest(static, probe)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "dms_m0_official_provenance_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"DMS M0 status={manifest['status']}: {args.output_dir}")
    if manifest["status"] != "complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
