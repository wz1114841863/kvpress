#!/usr/bin/env python3
"""DMS-M4 read-only active-resident attention semantic gate.

It keeps official DMS cache update and FlashAttention authoritative, then
replays each q_len=1 active native slot list in FP32.  No Route-A backend,
packed-cold source, scheduler, or hardware model is introduced.
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

import numpy as np
import torch
import transformers
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

from tools.run_dms_route_a_m1_native_semantic_gate import (
    DMSUpdateRecorder, EXPECTED_KV_HEADS, EXPECTED_LAYERS, git_commit,
    model_input, read_completed_m0, run_native_pass, stable_hash,
    validate_input_contract,
)
from tools.run_dms_route_a_m2_adapter_contract_gate import read_completed_m1
from tools.run_dms_route_a_m3_active_topology_gate import M3_SCHEMA, read_completed_m2, replay_topology
from tools.run_kvzap_trace import PRESETS, build_builtin_request, load_jsonl_request, seed_everything
from tools.validate_dms_m0_official_provenance import sha256_file

M4_SCHEMA = "route-a-dms-m4-active-resident-attention-gate-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DMS-M4 read-only active-resident FlashAttention replay; not Route-A mapping, benchmark, or hardware measurement.")
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--context-repetitions", type=int, default=8)
    for stage in ("m0", "m1", "m2", "m3"):
        parser.add_argument(f"--{stage}-manifest", type=Path, required=True)
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--tokenizer-root", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--decode-steps", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--atol", type=float, default=0.03)
    parser.add_argument("--rtol", type=float, default=0.03)
    parser.add_argument("--validate-inputs-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def read_completed_m3(path: Path, *, m0_manifest: Path, m2_manifest: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"DMS-M3 manifest is absent: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != M3_SCHEMA or report.get("status") != "complete":
        raise ValueError("DMS-M4 requires a completed route-a-dms-m3-active-native-slot-topology-1.0 manifest")
    if report.get("m0_provenance", {}).get("m0_manifest_sha256") != sha256_file(m0_manifest):
        raise ValueError("DMS-M3 is not bound to supplied M0 manifest")
    if report.get("m2_provenance", {}).get("m2_manifest_sha256") != sha256_file(m2_manifest):
        raise ValueError("DMS-M3 is not bound to supplied M2 manifest")
    for name, section in (("M3 control stream", report.get("official_native_control_capture", {}).get("control_stream", {})), ("M3 final topology", report.get("active_native_slot_topology", {}).get("artifact", {}))):
        artifact = path.parent / str(section.get("path", ""))
        if not artifact.is_file() or sha256_file(artifact) != section.get("sha256"):
            raise ValueError(f"{name} is absent or differs from M3 SHA-256")
    return report


def gather_native_slots(key_blocks: torch.Tensor, value_blocks: torch.Tensor, block_table: torch.Tensor, sequence_lengths: torch.Tensor) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
    """Gather only active native slots in the logical order passed to FlashAttention."""
    if key_blocks.shape != value_blocks.shape or key_blocks.ndim != 4 or key_blocks.shape[2] != 1:
        raise ValueError("DMS-M4 requires matching rank-4 native key/value blocks")
    if block_table.ndim != 2 or sequence_lengths.ndim != 1 or block_table.shape[0] != sequence_lengths.numel():
        raise ValueError("DMS-M4 native block-table/page-batch mismatch")
    block_size = int(key_blocks.shape[1]); keys, values = [], []
    for batch, length in enumerate(sequence_lengths.detach().to("cpu", dtype=torch.int64).tolist()):
        if length <= 0:
            raise ValueError("DMS-M4 decode attention has an empty native resident list")
        positions = torch.arange(length, device=key_blocks.device, dtype=torch.long)
        table_index = positions // block_size
        if int(table_index[-1]) >= block_table.shape[1]:
            raise ValueError("DMS-M4 native sequence exceeds supplied block table")
        block_ids = block_table[batch, table_index].to(dtype=torch.long)
        if bool((block_ids < 0).any().item()):
            raise ValueError("DMS-M4 encountered unresolved active native block-table entry")
        offset = positions % block_size
        keys.append(key_blocks[block_ids, offset, 0, :]); values.append(value_blocks[block_ids, offset, 0, :])
    return keys, values


def replay_active_resident_attention(query: torch.Tensor, key_slots: list[torch.Tensor], value_slots: list[torch.Tensor], native_output: torch.Tensor, *, scale: float, atol: float, rtol: float) -> dict[str, Any]:
    """FP32 semantic replay; FlashAttention's reduction order need not be bitwise equal."""
    if query.ndim != 4 or query.shape[1] != 1 or native_output.shape != query.shape:
        raise ValueError("DMS-M4 requires q_len=1 matching FlashAttention query/output layouts")
    if len(key_slots) != query.shape[0] or len(value_slots) != query.shape[0]:
        raise ValueError("DMS-M4 page-batch count differs between query and resident slots")
    rows = []
    for batch, (keys, values) in enumerate(zip(key_slots, value_slots)):
        if keys.ndim != 2 or keys.shape != values.shape or keys.shape[1] != query.shape[-1]:
            raise ValueError("DMS-M4 malformed gathered native resident K/V")
        q, k, v = query[batch, 0].float(), keys.float(), values.float()
        rows.append(torch.softmax((q @ k.T) * float(scale), dim=-1) @ v)
    manual = torch.stack(rows).unsqueeze(1); observed = native_output.float()
    if not torch.isfinite(manual).all() or not torch.isfinite(observed).all():
        raise AssertionError("DMS-M4 active-resident replay observed nonfinite values")
    difference = (manual - observed).abs()
    return {"accepted": bool(torch.allclose(manual, observed, atol=atol, rtol=rtol)), "page_batch_count": int(query.shape[0]), "query_heads_per_kv_head_group": int(query.shape[2]), "head_dim": int(query.shape[3]), "resident_slot_lengths": [int(item.shape[0]) for item in key_slots], "max_abs_difference": float(difference.max().item()), "mean_abs_difference": float(difference.mean().item()), "manual_output_sha256": hashlib.sha256(manual.detach().cpu().contiguous().numpy().tobytes()).hexdigest(), "official_output_sha256": hashlib.sha256(observed.detach().cpu().contiguous().numpy().tobytes()).hexdigest()}


class FlashResidentAttentionRecorder(AbstractContextManager):
    def __init__(self, module, *, atol: float, rtol: float):
        self.module, self.atol, self.rtol, self.original, self.records = module, atol, rtol, None, []

    def __enter__(self):
        self.original = self.module.flash_attn_with_kvcache
        def observed_flash(query, key_cache, value_cache, *args, **kwargs):
            output = self.original(query, key_cache, value_cache, *args, **kwargs)
            if int(query.shape[1]) != 1:
                raise AssertionError("DMS-M4 recorder unexpectedly observed non-decode FlashAttention")
            keys, values = gather_native_slots(key_cache, value_cache, kwargs["block_table"], kwargs["cache_seqlens"])
            self.records.append(replay_active_resident_attention(query, keys, values, output, scale=float(kwargs["softmax_scale"]), atol=self.atol, rtol=self.rtol))
            return output
        self.module.flash_attn_with_kvcache = observed_flash
        return self

    def __exit__(self, exc_type, exc, traceback):
        assert self.original is not None
        self.module.flash_attn_with_kvcache = self.original
        return False


class CombinedObservation(AbstractContextManager):
    def __init__(self, update: DMSUpdateRecorder, flash: FlashResidentAttentionRecorder): self.update, self.flash = update, flash
    def __enter__(self): self.update.__enter__(); self.flash.__enter__(); return self
    def __exit__(self, exc_type, exc, traceback):
        return bool(self.flash.__exit__(exc_type, exc, traceback) or self.update.__exit__(exc_type, exc, traceback))


def summarize_attention(records: list[dict[str, Any]], *, decode_steps: int) -> dict[str, Any]:
    if len(records) != EXPECTED_LAYERS * decode_steps:
        raise AssertionError(f"DMS-M4 observed {len(records)} decode FlashAttention calls, expected {EXPECTED_LAYERS * decode_steps}")
    if not all(record["accepted"] for record in records):
        raise AssertionError("DMS-M4 active-resident replay exceeded declared numerical tolerance")
    lengths = [length for record in records for length in record["resident_slot_lengths"]]
    return {"decode_flash_attention_call_count": len(records), "all_36_layers_all_decode_steps_observed": True, "all_active_resident_replays_within_declared_tolerance": True, "resident_slot_length_min": min(lengths), "resident_slot_length_max": max(lengths), "max_abs_difference": max(record["max_abs_difference"] for record in records), "mean_of_per_call_mean_abs_difference": float(np.mean([record["mean_abs_difference"] for record in records])), "query_heads_per_kv_head_group_values": sorted({record["query_heads_per_kv_head_group"] for record in records}), "head_dim_values": sorted({record["head_dim"] for record in records})}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists(): raise FileExistsError(f"DMS-M4 output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None: raise ValueError("--request-id requires --input-jsonl")
    if args.context_repetitions < 2 or args.decode_steps < 2: raise ValueError("DMS-M4 requires context-repetitions >= 2 and decode-steps >= 2")
    if args.atol <= 0 or args.rtol <= 0: raise ValueError("DMS-M4 tolerances must be positive")
    m0 = read_completed_m0(args.m0_manifest); m1 = read_completed_m1(args.m1_manifest, m0_manifest=args.m0_manifest); m2 = read_completed_m2(args.m2_manifest, m0_manifest=args.m0_manifest, m1_manifest=args.m1_manifest); m3 = read_completed_m3(args.m3_manifest, m0_manifest=args.m0_manifest, m2_manifest=args.m2_manifest)
    provenance = validate_input_contract(args, m0)
    config = {key: (str(value) if isinstance(value, Path) else value) for key, value in vars(args).items() if key != "output_dir"}
    prior = {"m1_manifest_sha256": sha256_file(args.m1_manifest), "m2_manifest_sha256": sha256_file(args.m2_manifest), "m3_manifest_sha256": sha256_file(args.m3_manifest), "m3_control_trace_sha256": m3["official_native_control_capture"]["control_stream"]["sha256"], "m3_final_topology_sha256": m3["active_native_slot_topology"]["artifact"]["sha256"]}
    if args.validate_inputs_only:
        args.output_dir.mkdir(parents=True, exist_ok=False)
        data = {"schema_version": M4_SCHEMA, "status": "input_validated_only", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": git_commit(), "config": config, "config_hash": stable_hash(config), "m0_provenance": provenance, "prior_provenance": prior, "boundaries": ["No model, cache, K/V, attention, decoder, or controller replay ran.", "This is not completed DMS-M4, Route-A mapping, hardware, or performance evidence."]}
        (args.output_dir / "dms_m4_active_resident_attention_manifest.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(f"DMS M4 inputs validated: {args.output_dir}"); return
    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    request_p = {"request_id": request["request_id"], "content_sha256": stable_hash({"context": request["context"], "question": request["question"]})}
    for label, report in (("M1", m1), ("M2", m2), ("M3", m3)):
        if report.get("request", {}).get("content_sha256") != request_p["content_sha256"]: raise ValueError(f"DMS-M4 fixed request differs from {label}-bound request provenance")
    device = torch.device(args.device)
    if device.type != "cuda" or not torch.cuda.is_available(): raise RuntimeError("DMS-M4 requires an explicitly selected available CUDA device")
    seed_everything(args.seed)
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_root, local_files_only=True, trust_remote_code=True)
    model_config = AutoConfig.from_pretrained(args.snapshot_root, local_files_only=True, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(args.snapshot_root, config=model_config, local_files_only=True, trust_remote_code=True, dtype=torch.bfloat16, device_map="auto").eval()
    if len(model.model.layers) != EXPECTED_LAYERS or int(model.config.num_key_value_heads) != EXPECTED_KV_HEADS: raise AssertionError("loaded official DMS model differs from M0-bound structure")
    input_ids = model_input(tokenizer, request, model.device)
    if int(input_ids.shape[1]) <= int(model.config.dms_window_size): raise ValueError("DMS-M4 request must exceed official decision-delay window")
    module_prefix = model.__class__.__module__.rsplit(".", 1)[0]
    cache_module, attention_module = importlib.import_module(module_prefix + ".dms_cache"), importlib.import_module(module_prefix + ".dms_attention")
    print("Pass 1/2: official DMS native cache without M4 observation..."); baseline = run_native_pass(model, input_ids, args.decode_steps, recorder=None)
    print("Pass 2/2: official DMS with read-only native slot and FlashAttention observation...")
    update, flash = DMSUpdateRecorder(cache_module.DMSCache, capture_decision_bits=True, capture_native_control_state=True), FlashResidentAttentionRecorder(attention_module, atol=args.atol, rtol=args.rtol)
    with CombinedObservation(update, flash): observed = run_native_pass(model, input_ids, args.decode_steps, recorder=None)
    if baseline != observed: raise AssertionError("DMS-M4 observation changed official DMS token/logit/cache-state digests")
    replay, final_lengths, _ = replay_topology(update.events, window_size=int(model.config.dms_window_size) + 1)
    if final_lengths.tolist() != observed["final_cache_lengths_by_layer_kv_head"]: raise AssertionError("DMS-M4 topology replay/final native cache-length mismatch")
    attention = summarize_attention(flash.records, decode_steps=args.decode_steps)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    data = {"schema_version": M4_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": git_commit(), "config": config, "config_hash": stable_hash(config), "execution_classification": "trace-derived official DMS native cache/FlashAttention observation plus functional FP32 active-resident attention replay; not hardware measurement", "m0_provenance": provenance, "prior_provenance": prior, "request": {**request_p, "input_shape": list(input_ids.shape)}, "trace_off_on_equivalence": {"token_logit_cache_digests_identical": True}, "fresh_native_control_topology": {key: replay[key] for key in ("event_count", "per_event_native_cache_length_agreement", "per_event_native_ring_metadata_agreement", "final_active_source_unique_per_layer_kv_head", "final_active_physical_slot_order_nonmonotonic_count")}, "active_resident_attention": attention, "observational_guards": {"official_dms_model_and_base_tokenizer_bound_to_completed_m0": True, "m1_m2_m3_provenance_bound": True, "native_dms_cache_used": True, "fresh_control_topology_replayed": True, "all_36_layers_all_decode_steps_observed": attention["all_36_layers_all_decode_steps_observed"], "all_active_resident_replays_within_declared_tolerance": attention["all_active_resident_replays_within_declared_tolerance"], "attention_replaced": False, "route_a_backend_instantiated": False, "kvpress_dmspress_used": False, "kvzap_predictor_used": False, "fake_key_attention_used": False, "generation_api_used": False, "no_kv_payload_serialized": True}, "boundaries": ["Official DMS cache update and FlashAttention return path remain authoritative; K/V are read only in memory and never persisted.", "The functional replay services one native resident source in official logical-slot/block-table order. It does not prove a hot/pending/packed-cold mapping, split-source merge, or reordering invariance.", "FP32 tolerance is a numerical diagnostic only, not capacity, allocator, HBM/DRAM traffic, hardware latency, throughput, energy, area, quality, architecture, or RTL evidence."], "torch_version": str(torch.__version__), "transformers_version": str(transformers.__version__)}
    (args.output_dir / "dms_m4_active_resident_attention_manifest.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"DMS M4 active-resident attention gate passed: {args.output_dir}")

if __name__ == "__main__": main()
