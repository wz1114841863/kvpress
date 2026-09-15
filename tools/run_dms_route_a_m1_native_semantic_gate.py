#!/usr/bin/env python3
"""Bounded native-DMS semantic gate after official DMS-M0.

This gate observes the official trained DMS cache only.  It deliberately does
not instantiate KVPress DMSPress, change an official DMS decision, replace
attention, introduce a Route-A backend, or claim a hardware result.  Its role
is to establish what the official DMS frontend actually does before considering
whether any separately designed adapter can consume its state.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

from tools.run_kvzap_trace import PRESETS, build_builtin_request, load_jsonl_request, seed_everything
from tools.validate_dms_m0_official_provenance import OFFICIAL_DMS_REPO, OFFICIAL_DMS_REVISION, sha256_file


M0_SCHEMA = "route-a-dms-m0-official-provenance-1.0"
M1_SCHEMA = "route-a-dms-m1-native-semantic-gate-1.0"
EXPECTED_LAYERS = 36
EXPECTED_KV_HEADS = 8


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def git_commit() -> str:
    import subprocess

    result = subprocess.run(["git", "rev-parse", "HEAD"], check=False, capture_output=True, text=True)
    return result.stdout.strip() or "unknown"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "DMS-M1 native decision/cache observer with trace-off/on equivalence; "
            "not Route-A substitution, a benchmark, or hardware measurement."
        )
    )
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--context-repetitions", type=int, default=8)
    parser.add_argument("--m0-manifest", type=Path, required=True, help="Completed exact-source DMS-M0 manifest.")
    parser.add_argument("--snapshot-root", type=Path, required=True, help="Pinned local official DMS snapshot root.")
    parser.add_argument("--tokenizer-root", type=Path, required=True, help="Pinned local base Qwen3 tokenizer snapshot.")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--decode-steps", type=int, default=4, help="Fixed greedy decode forwards after prefill.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--require-native-eviction", action="store_true", help="Fail unless the observed native cache is shorter than its logical history in at least one layer/head.")
    parser.add_argument("--validate-inputs-only", action="store_true", help="Write only a fresh no-model prerequisite manifest.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def read_completed_m0(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"DMS-M0 manifest is absent: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != M0_SCHEMA or report.get("status") != "complete":
        raise ValueError("DMS-M1 requires a completed route-a-dms-m0-official-provenance-1.0 manifest")
    snapshot = report.get("official_snapshot")
    probe = report.get("runtime_probe")
    if not isinstance(snapshot, dict) or not isinstance(probe, dict):
        raise ValueError("DMS-M0 manifest lacks official_snapshot or runtime_probe")
    if snapshot.get("repo_id") != OFFICIAL_DMS_REPO or snapshot.get("revision") != OFFICIAL_DMS_REVISION:
        raise ValueError("DMS-M0 does not bind the required official trained-DMS snapshot")
    if probe.get("status") != "passed" or probe.get("model_weights_loaded") is not True:
        raise ValueError("DMS-M0 lacks a successful model-prefill compatibility probe")
    if probe.get("generation_calls") != 0:
        raise ValueError("DMS-M0 compatibility probe unexpectedly generated tokens")
    tokenizer = probe.get("tokenizer_provenance")
    if not isinstance(tokenizer, dict) or not isinstance(tokenizer.get("root"), str):
        raise ValueError("DMS-M0 lacks explicit base-tokenizer provenance")
    return report


def validate_input_contract(args: argparse.Namespace, m0: dict[str, Any]) -> dict[str, Any]:
    snapshot = args.snapshot_root.resolve(strict=True)
    tokenizer = args.tokenizer_root.resolve(strict=True)
    if snapshot.name != OFFICIAL_DMS_REVISION:
        raise ValueError("DMS-M1 snapshot root differs from the M0-pinned official revision")
    if not tokenizer.is_dir():
        raise NotADirectoryError(f"DMS-M1 tokenizer root is not a directory: {tokenizer}")
    if str(snapshot) != m0["official_snapshot"]["snapshot_root"]:
        raise ValueError("DMS-M1 snapshot root differs from the completed M0 source input")
    if str(tokenizer) != m0["runtime_probe"]["tokenizer_provenance"]["root"]:
        raise ValueError("DMS-M1 tokenizer root differs from the completed M0 runtime input")
    selected = ("config.json", "model.safetensors.index.json", "modeling_qwen3_dms.py", "dms_attention.py", "dms_cache.py")
    return {
        "m0_manifest_path": str(args.m0_manifest),
        "m0_manifest_sha256": sha256_file(args.m0_manifest),
        "official_snapshot": {
            "repo_id": OFFICIAL_DMS_REPO,
            "revision": OFFICIAL_DMS_REVISION,
            "root": str(snapshot),
            "selected_file_sha256": {name: sha256_file(snapshot / name) for name in selected},
        },
        "tokenizer": m0["runtime_probe"]["tokenizer_provenance"],
    }


def model_input(tokenizer, request: dict[str, Any], device: torch.device) -> torch.Tensor:
    text = f"Context:\n{request['context']}\n\nQuestion:\n{request['question']}\n\nAnswer:\n"
    encoded = tokenizer(text, return_tensors="pt", add_special_tokens=True)
    return encoded["input_ids"].to(device)


def tensor_digest(tensor: torch.Tensor) -> str:
    return hashlib.sha256(tensor.detach().to(dtype=torch.float32, device="cpu").contiguous().numpy().tobytes()).hexdigest()


def cache_state(cache, layer_count: int) -> list[list[int]]:
    rows = []
    if len(cache) != layer_count:
        raise AssertionError(f"native DMS cache has {len(cache)} layers, expected {layer_count}")
    for layer in range(layer_count):
        lengths = cache[layer].get_seq_lengths().detach().to(device="cpu", dtype=torch.int64).tolist()
        if len(lengths) != EXPECTED_KV_HEADS:
            raise AssertionError(f"layer {layer}: native cache has {len(lengths)} KV-head lengths")
        rows.append([int(value) for value in lengths])
    return rows


class DMSUpdateRecorder(AbstractContextManager):
    """Observe one official cache class without changing values or return paths."""

    def __init__(self, cache_class, *, capture_decision_bits: bool = False):
        self.cache_class = cache_class
        # M1 deliberately records summaries only.  A later, separately named
        # contract gate can opt in to an in-memory copy so it can serialize a
        # bounded decision stream outside the M1 manifest without changing the
        # official update inputs or return path.
        self.capture_decision_bits = capture_decision_bits
        self.original_update = None
        self.events: list[dict[str, Any]] = []

    @staticmethod
    def inherited_update_method(cache_class):
        """Return the real inherited update implementation, never our wrapper."""
        for base in cache_class.__mro__[1:]:
            candidate = base.__dict__.get("update")
            if candidate is not None:
                return candidate
        raise AttributeError("DMS cache class has no inherited update method")

    def __enter__(self):
        # The official DMSCache inherits Cache.update rather than defining an
        # update method. Looking it up on DMSCache after installing a wrapper
        # can resolve to that wrapper, so bind the owning parent implementation.
        self.original_update = self.inherited_update_method(self.cache_class)

        def observed_update(cache, key_states, value_states, layer_idx, cache_kwargs):
            decisions = cache_kwargs["eviction_info"]
            if decisions.ndim != 3 or decisions.shape[0] != 1 or decisions.shape[1] != EXPECTED_KV_HEADS:
                raise AssertionError(f"unexpected native DMS decision shape: {tuple(decisions.shape)}")
            decision_cpu = decisions.detach().to(device="cpu", dtype=torch.int8).contiguous()
            if not bool(((decision_cpu == 0) | (decision_cpu == 1)).all().item()):
                raise AssertionError("official DMS decisions are not binary")
            q_len = int(decision_cpu.shape[-1])
            before = [0] * EXPECTED_KV_HEADS if len(cache) <= layer_idx else [
                int(value) for value in cache[layer_idx].get_seq_lengths().detach().to(device="cpu", dtype=torch.int64).tolist()
            ]
            result = self.original_update(cache, key_states, value_states, layer_idx, cache_kwargs)
            after = [int(value) for value in cache[layer_idx].get_seq_lengths().detach().to(device="cpu", dtype=torch.int64).tolist()]
            event = {
                "layer": int(layer_idx),
                "call_index": len(self.events),
                "kind": "prefill" if q_len > 1 else "decode",
                "q_len": q_len,
                "decision_sha256": hashlib.sha256(decision_cpu.numpy().tobytes()).hexdigest(),
                "decision_ones_by_kv_head": [int(value) for value in decision_cpu.sum(dim=(0, 2)).tolist()],
                "cache_lengths_before": before,
                "cache_lengths_after": after,
            }
            if self.capture_decision_bits:
                # The copy is intentionally in-memory only here.  M1's JSON
                # schema remains summary-only; M2 owns any compact raw-stream
                # artifact and its provenance contract.
                event["decision_bits"] = decision_cpu.squeeze(0).numpy().copy()
            self.events.append(event)
            return result

        self.cache_class.update = observed_update
        return self

    def __exit__(self, exc_type, exc, traceback):
        assert self.original_update is not None
        self.cache_class.update = self.original_update
        return False


def run_native_pass(model, input_ids: torch.Tensor, decode_steps: int, recorder: DMSUpdateRecorder | None) -> dict[str, Any]:
    cache = None
    generated: list[int] = []
    logit_digests: list[str] = []
    context = recorder if recorder is not None else _NullContext()
    with torch.no_grad(), context:
        outputs = model(input_ids=input_ids, use_cache=True)
        cache = outputs.past_key_values
        logits = outputs.logits
        logit_digests.append(tensor_digest(logits[:, -1:, :]))
        for _ in range(decode_steps):
            next_token = logits[:, -1, :].argmax(dim=-1, keepdim=True)
            generated.extend(int(value) for value in next_token.detach().to(device="cpu").flatten().tolist())
            outputs = model(input_ids=next_token, past_key_values=cache, use_cache=True)
            cache = outputs.past_key_values
            logits = outputs.logits
            logit_digests.append(tensor_digest(logits[:, -1:, :]))
    return {
        "generated_token_ids": generated,
        "generated_token_sha256": hashlib.sha256(bytes().join(int(value).to_bytes(4, "little", signed=False) for value in generated)).hexdigest(),
        "last_logit_sha256_by_forward": logit_digests,
        "final_cache_lengths_by_layer_kv_head": cache_state(cache, EXPECTED_LAYERS),
        "final_cache_lengths_sha256": stable_hash(cache_state(cache, EXPECTED_LAYERS)),
    }


class _NullContext(AbstractContextManager):
    def __exit__(self, exc_type, exc, traceback):
        return False


def summarize_events(events: list[dict[str, Any]], *, decode_steps: int) -> dict[str, Any]:
    expected_events = EXPECTED_LAYERS * (1 + decode_steps)
    if len(events) != expected_events:
        raise AssertionError(f"observed {len(events)} cache updates, expected {expected_events}")
    by_layer: list[dict[str, Any]] = []
    for layer in range(EXPECTED_LAYERS):
        rows = [row for row in events if row["layer"] == layer]
        if len(rows) != 1 + decode_steps or rows[0]["kind"] != "prefill" or any(row["kind"] != "decode" for row in rows[1:]):
            raise AssertionError(f"layer {layer}: incomplete prefill/decode native DMS event coverage")
        if any(len(row["decision_ones_by_kv_head"]) != EXPECTED_KV_HEADS for row in rows):
            raise AssertionError(f"layer {layer}: incomplete KV-head decision coverage")
        final_lengths = rows[-1]["cache_lengths_after"]
        logical_history = sum(int(row["q_len"]) for row in rows)
        by_layer.append(
            {
                "layer": layer,
                "decision_ones_by_kv_head": [sum(int(row["decision_ones_by_kv_head"][head]) for row in rows) for head in range(EXPECTED_KV_HEADS)],
                "logical_history_tokens": logical_history,
                "final_native_cache_lengths_by_kv_head": final_lengths,
                "native_eviction_observed_by_kv_head": [int(length) < logical_history for length in final_lengths],
            }
        )
    return {
        "event_count": len(events),
        "all_36_layers_all_8_kv_heads_covered": True,
        "decision_ones_total": sum(sum(row["decision_ones_by_kv_head"]) for row in by_layer),
        "native_eviction_observed": any(any(row["native_eviction_observed_by_kv_head"]) for row in by_layer),
        "layers": by_layer,
        "event_summary_sha256": stable_hash(events),
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"DMS-M1 output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.context_repetitions < 2 or args.decode_steps < 2:
        raise ValueError("DMS-M1 requires context-repetitions >= 2 and decode-steps >= 2")
    m0 = read_completed_m0(args.m0_manifest)
    provenance = validate_input_contract(args, m0)
    config = {key: (str(value) if isinstance(value, Path) else value) for key, value in vars(args).items() if key != "output_dir"}
    if args.validate_inputs_only:
        manifest = {
            "schema_version": M1_SCHEMA,
            "status": "input_validated_only",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": git_commit(),
            "config": config,
            "config_hash": stable_hash(config),
            "m0_provenance": provenance,
            "boundaries": ["No model, checkpoint custom code, tokenizer, cache, decision, or generation call occurred.", "This is a prerequisite check, not completed DMS-M1 semantic evidence or hardware evidence."],
        }
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / "dms_m1_native_semantic_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"DMS M1 inputs validated: {args.output_dir}")
        return

    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    device = torch.device(args.device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("DMS-M1 requires an explicitly selected available CUDA device")
    seed_everything(args.seed)
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_root, local_files_only=True, trust_remote_code=True)
    config_object = AutoConfig.from_pretrained(args.snapshot_root, local_files_only=True, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.snapshot_root,
        config=config_object,
        local_files_only=True,
        trust_remote_code=True,
        dtype=torch.bfloat16,
        device_map="auto",
    ).eval()
    if len(model.model.layers) != EXPECTED_LAYERS or int(model.config.num_key_value_heads) != EXPECTED_KV_HEADS:
        raise AssertionError("loaded official DMS model differs from the M0-bound 36-layer/8-KV-head structure")
    input_ids = model_input(tokenizer, request, model.device)
    if int(input_ids.shape[1]) <= int(model.config.dms_window_size):
        raise ValueError("DMS-M1 request must exceed the official DMS decision-delay window")
    cache_module = importlib.import_module(model.__class__.__module__.rsplit(".", 1)[0] + ".dms_cache")
    print("Pass 1/2: official DMS native cache without observer...")
    baseline = run_native_pass(model, input_ids, args.decode_steps, recorder=None)
    print("Pass 2/2: identical official DMS pass with read-only cache-update observer...")
    with DMSUpdateRecorder(cache_module.DMSCache) as recorder:
        observed = run_native_pass(model, input_ids, args.decode_steps, recorder=recorder)
    if baseline != observed:
        raise AssertionError("DMS-M1 observer changed official DMS token/logit/cache-state digests")
    summary = summarize_events(recorder.events, decode_steps=args.decode_steps)
    if args.require_native_eviction and not summary["native_eviction_observed"]:
        raise AssertionError("required native DMS eviction was not observed")
    manifest = {
        "schema_version": M1_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "functional official-DMS native-cache observer with trace-derived decision/state summaries; not modeled or measured hardware evidence",
        "m0_provenance": provenance,
        "request": {"request_id": request["request_id"], "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}), "input_shape": list(input_ids.shape)},
        "trace_off_on_equivalence": {"token_logit_cache_digests_identical": True, "baseline": baseline, "observer": observed},
        "native_dms_trace_summary": summary,
        "observational_guards": {
            "official_dms_model_and_base_tokenizer_bound_to_completed_m0": True,
            "all_36_layers_all_8_kv_heads_observed_each_prefill_decode_call": True,
            "official_binary_dms_decisions_observed": True,
            "observer_did_not_change_token_logit_or_native_cache_state_digests": True,
            "native_dms_cache_used": True,
            "kvpress_dmspress_used": False,
            "kvzap_predictor_used": False,
            "route_a_backend_instantiated": False,
            "fake_key_attention_used": False,
            "generation_api_used": False,
            "native_eviction_observed": summary["native_eviction_observed"],
        },
        "boundaries": [
            "DMS decisions and native cache lengths are trace-derived software state from one fixed request, not a trained-DMS quality result or workload distribution.",
            "DMS uses delayed native eviction and cache-slot reuse. This gate does not relabel that native cache as Route-A hot/pending/packed cold storage and does not establish Route-A compatibility.",
            "No field is allocator data, HBM/DRAM traffic, true hardware latency, throughput, energy, area, hardware acceleration, architecture specification, or RTL evidence.",
        ],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "dms_m1_native_semantic_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"DMS M1 native semantic gate passed: {args.output_dir}")


if __name__ == "__main__":
    main()
