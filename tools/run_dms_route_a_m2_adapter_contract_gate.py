#!/usr/bin/env python3
"""Replay the official DMS delayed-eviction/slot-reuse control contract.

DMS-M2 is intentionally narrower than a Route-A implementation.  It captures
the official trained-DMS binary decisions on one fixed request, then validates
an independent controller that reproduces only documented delayed eviction and
native-slot reuse.  It neither moves K/V data, replaces attention, creates a
packed-cold store, nor makes a hardware claim.
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
    DMSUpdateRecorder,
    EXPECTED_KV_HEADS,
    EXPECTED_LAYERS,
    M1_SCHEMA,
    git_commit,
    model_input,
    read_completed_m0,
    run_native_pass,
    stable_hash,
    summarize_events,
    validate_input_contract,
)
from tools.run_kvzap_trace import PRESETS, build_builtin_request, load_jsonl_request, seed_everything
from tools.validate_dms_m0_official_provenance import sha256_file


M2_SCHEMA = "route-a-dms-m2-delayed-eviction-adapter-contract-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "DMS-M2 official decision capture plus delayed-eviction/slot-reuse "
            "controller replay; not Route-A attention, hardware, or a benchmark."
        )
    )
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--context-repetitions", type=int, default=8)
    parser.add_argument("--m0-manifest", type=Path, required=True, help="Completed exact-source DMS-M0 manifest.")
    parser.add_argument("--m1-manifest", type=Path, required=True, help="Completed exact-source DMS-M1 manifest.")
    parser.add_argument("--snapshot-root", type=Path, required=True, help="Pinned local official DMS snapshot root.")
    parser.add_argument("--tokenizer-root", type=Path, required=True, help="Pinned local base Qwen3 tokenizer snapshot.")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--decode-steps", type=int, default=4, help="Fixed greedy decode forwards after prefill.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validate-inputs-only", action="store_true", help="Write only a fresh no-model prerequisite manifest.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def read_completed_m1(path: Path, *, m0_manifest: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"DMS-M1 manifest is absent: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != M1_SCHEMA or report.get("status") != "complete":
        raise ValueError("DMS-M2 requires a completed route-a-dms-m1-native-semantic-gate-1.0 manifest")
    equivalence = report.get("trace_off_on_equivalence")
    guards = report.get("observational_guards")
    provenance = report.get("m0_provenance")
    if not isinstance(equivalence, dict) or equivalence.get("token_logit_cache_digests_identical") is not True:
        raise ValueError("DMS-M1 lacks successful trace-off/on observer equivalence")
    if not isinstance(guards, dict) or guards.get("official_binary_dms_decisions_observed") is not True:
        raise ValueError("DMS-M1 lacks observed official binary decisions")
    if not isinstance(provenance, dict) or provenance.get("m0_manifest_sha256") != sha256_file(m0_manifest):
        raise ValueError("DMS-M1 is not bound to the supplied completed DMS-M0 manifest")
    native = report.get("native_dms_trace_summary")
    if not isinstance(native, dict) or native.get("all_36_layers_all_8_kv_heads_covered") is not True:
        raise ValueError("DMS-M1 lacks full layer/KV-head native coverage")
    return report


def public_event(event: dict[str, Any]) -> dict[str, Any]:
    """Drop in-memory decision bits before summary hashing or JSON serialization."""
    return {key: value for key, value in event.items() if key != "decision_bits"}


class DelayedEvictionSlotReuseController:
    """Pure-Python functional model of DMS's per-KV-head control state.

    Each decision bit labels the immediately preceding arrival.  A labeled
    arrival is reused only after it becomes the ring's next eviction candidate;
    otherwise the logical native cache length grows.  ``slot`` is an abstract
    native cache index, never a K/V address or hardware allocation.
    """

    def __init__(self, window_size: int):
        if window_size < 2:
            raise ValueError("DMS delayed-eviction controller requires window_size >= 2")
        self.window_size = window_size
        self.recent: list[dict[str, int]] = [{"slot": 0, "evict": 0} for _ in range(window_size)]
        self.recent_position = 0
        self.cache_length = 0

    def consume(self, decisions: np.ndarray) -> list[int]:
        if decisions.ndim != 1:
            raise ValueError(f"one KV-head decision stream must be rank-1, got {decisions.shape}")
        if not np.isin(decisions, [0, 1]).all():
            raise ValueError("DMS decision stream is not binary")
        slots: list[int] = []
        for decision in decisions.tolist():
            candidate_index = self.recent_position % self.window_size
            candidate = self.recent[candidate_index]
            evict = int(candidate["evict"] == 1)
            final_slot = int(candidate["slot"] if evict else self.cache_length)
            previous_index = (self.recent_position + self.window_size - 1) % self.window_size
            if self.cache_length > 0:
                self.recent[previous_index]["evict"] = int(decision)
            self.recent[candidate_index] = {"slot": final_slot, "evict": 0}
            self.recent_position += 1
            self.cache_length += 1 - evict
            slots.append(final_slot)
        return slots

    def state_digest(self) -> str:
        return stable_hash(
            {
                "window_size": self.window_size,
                "recent": self.recent,
                "recent_position": self.recent_position,
                "cache_length": self.cache_length,
            }
        )


def replay_native_contract(events: list[dict[str, Any]], *, window_size: int) -> dict[str, Any]:
    """Replay every captured event and require native cache-length agreement."""
    if len(events) == 0:
        raise ValueError("DMS-M2 needs at least one captured native update event")
    controllers = [
        [DelayedEvictionSlotReuseController(window_size) for _ in range(EXPECTED_KV_HEADS)]
        for _ in range(EXPECTED_LAYERS)
    ]
    replay_events: list[dict[str, Any]] = []
    source_slot_reuse_events = 0
    for event in events:
        layer = int(event["layer"])
        decisions = event.get("decision_bits")
        if not isinstance(decisions, np.ndarray) or decisions.shape != (EXPECTED_KV_HEADS, int(event["q_len"])):
            raise AssertionError(f"layer {layer}: missing or malformed captured DMS decision bits")
        before = [controller.cache_length for controller in controllers[layer]]
        if before != event["cache_lengths_before"]:
            raise AssertionError(f"layer {layer} call {event['call_index']}: controller/native pre-update length mismatch")
        slots_by_head = [controllers[layer][head].consume(decisions[head]) for head in range(EXPECTED_KV_HEADS)]
        after = [controller.cache_length for controller in controllers[layer]]
        if after != event["cache_lengths_after"]:
            raise AssertionError(f"layer {layer} call {event['call_index']}: controller/native post-update length mismatch")
        source_slot_reuse_events += sum(
            int(any(slot < before[head] for slot in slots_by_head[head])) for head in range(EXPECTED_KV_HEADS)
        )
        replay_events.append(
            {
                "layer": layer,
                "call_index": int(event["call_index"]),
                "kind": event["kind"],
                "q_len": int(event["q_len"]),
                "cache_lengths_before": before,
                "cache_lengths_after": after,
                "abstract_slot_digest_by_kv_head": [
                    hashlib.sha256(np.asarray(slots, dtype=np.int32).tobytes()).hexdigest() for slots in slots_by_head
                ],
                "controller_state_digest_by_kv_head": [controller.state_digest() for controller in controllers[layer]],
            }
        )
    return {
        "event_count": len(replay_events),
        "all_36_layers_all_8_kv_heads_replayed": len({row["layer"] for row in replay_events}) == EXPECTED_LAYERS,
        "per_event_native_cache_length_agreement": True,
        "abstract_slot_reuse_observed_layer_head_events": source_slot_reuse_events,
        "replay_event_summary_sha256": stable_hash(replay_events),
        "final_controller_cache_lengths_by_layer_kv_head": [
            [controller.cache_length for controller in layer_controllers] for layer_controllers in controllers
        ],
        "final_controller_state_sha256_by_layer_kv_head": [
            [controller.state_digest() for controller in layer_controllers] for layer_controllers in controllers
        ],
    }


def write_decision_stream(path: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Write only binary decision bits and structural event delimiters, never K/V or tokens."""
    flattened: list[np.ndarray] = []
    offsets = [0]
    for event in events:
        decisions = event.get("decision_bits")
        if not isinstance(decisions, np.ndarray):
            raise AssertionError("DMS-M2 decision stream write requires captured bits")
        flat = decisions.astype(np.uint8, copy=False).reshape(-1)
        flattened.append(flat)
        offsets.append(offsets[-1] + int(flat.size))
    np.savez_compressed(
        path,
        schema_version=np.asarray(["route-a-dms-decision-stream-1.0"]),
        decision_bits=np.concatenate(flattened) if flattened else np.empty((0,), dtype=np.uint8),
        event_bit_offsets=np.asarray(offsets, dtype=np.int64),
        event_layer=np.asarray([event["layer"] for event in events], dtype=np.int16),
        event_call_index=np.asarray([event["call_index"] for event in events], dtype=np.int16),
        event_q_len=np.asarray([event["q_len"] for event in events], dtype=np.int32),
        event_kind_code=np.asarray([0 if event["kind"] == "prefill" else 1 for event in events], dtype=np.int8),
    )
    return {
        "path": path.name,
        "sha256": sha256_file(path),
        "schema_version": "route-a-dms-decision-stream-1.0",
        "event_count": len(events),
        "kv_heads_per_event": EXPECTED_KV_HEADS,
        "contents": "binary official-DMS decision bits plus layer/call/q-length/kind delimiters only; no token IDs, text, K/V, attention, logits, allocator, or timing data",
    }


class _NullContext(AbstractContextManager):
    def __exit__(self, exc_type, exc, traceback):
        return False


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"DMS-M2 output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.context_repetitions < 2 or args.decode_steps < 2:
        raise ValueError("DMS-M2 requires context-repetitions >= 2 and decode-steps >= 2")
    m0 = read_completed_m0(args.m0_manifest)
    m1 = read_completed_m1(args.m1_manifest, m0_manifest=args.m0_manifest)
    provenance = validate_input_contract(args, m0)
    config = {key: (str(value) if isinstance(value, Path) else value) for key, value in vars(args).items() if key != "output_dir"}
    m1_provenance = {
        "m1_manifest_path": str(args.m1_manifest),
        "m1_manifest_sha256": sha256_file(args.m1_manifest),
        "m1_event_summary_sha256": m1["native_dms_trace_summary"]["event_summary_sha256"],
    }
    if args.validate_inputs_only:
        manifest = {
            "schema_version": M2_SCHEMA,
            "status": "input_validated_only",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": git_commit(),
            "config": config,
            "config_hash": stable_hash(config),
            "m0_provenance": provenance,
            "m1_provenance": m1_provenance,
            "boundaries": [
                "No model, checkpoint custom code, tokenizer, cache, decision, generation, or controller replay call occurred.",
                "This is a prerequisite check, not completed DMS-M2 adapter-contract, Route-A, hardware, or performance evidence.",
            ],
        }
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / "dms_m2_adapter_contract_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"DMS M2 inputs validated: {args.output_dir}")
        return

    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    request_provenance = {
        "request_id": request["request_id"],
        "content_sha256": stable_hash({"context": request["context"], "question": request["question"]}),
    }
    if m1.get("request", {}).get("content_sha256") != request_provenance["content_sha256"]:
        raise ValueError("DMS-M2 fixed request differs from the request bound by completed DMS-M1")
    device = torch.device(args.device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("DMS-M2 requires an explicitly selected available CUDA device")
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
    dms_window_size = int(model.config.dms_window_size) + 1
    input_ids = model_input(tokenizer, request, model.device)
    if int(input_ids.shape[1]) <= int(model.config.dms_window_size):
        raise ValueError("DMS-M2 request must exceed the official DMS decision-delay window")
    cache_module = importlib.import_module(model.__class__.__module__.rsplit(".", 1)[0] + ".dms_cache")
    print("Pass 1/2: official DMS native cache without decision capture...")
    baseline = run_native_pass(model, input_ids, args.decode_steps, recorder=None)
    print("Pass 2/2: official DMS with read-only binary-decision capture...")
    with DMSUpdateRecorder(cache_module.DMSCache, capture_decision_bits=True) as recorder:
        observed = run_native_pass(model, input_ids, args.decode_steps, recorder=recorder)
    if baseline != observed:
        raise AssertionError("DMS-M2 capture changed official DMS token/logit/cache-state digests")
    events = recorder.events
    public_events = [public_event(event) for event in events]
    observed_summary = summarize_events(public_events, decode_steps=args.decode_steps)
    # M1 records a summary hash, not its raw decision stream.  The M1 run can
    # also have used a different available GPU.  Retain the comparison as
    # provenance, but make this gate's evidence the trace-off/on-equivalent
    # native capture and its own exact per-event controller agreement.
    m1_event_comparison = {
        "bound_m1_event_summary_sha256": m1["native_dms_trace_summary"]["event_summary_sha256"],
        "m2_observed_event_summary_sha256": observed_summary["event_summary_sha256"],
        "identical": observed_summary["event_summary_sha256"] == m1["native_dms_trace_summary"]["event_summary_sha256"],
        "interpretation": "informational cross-run summary comparison only; M2 correctness is gated by its own trace-off/on equivalence and per-event native-length replay agreement",
    }
    replay = replay_native_contract(events, window_size=dms_window_size)
    if replay["final_controller_cache_lengths_by_layer_kv_head"] != observed["final_cache_lengths_by_layer_kv_head"]:
        raise AssertionError("DMS-M2 final controller/native cache-length matrix differs")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    stream = write_decision_stream(args.output_dir / "dms_m2_official_decision_stream.npz", events)
    manifest = {
        "schema_version": M2_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "trace-derived official binary-decision/native-cache observations plus functional independent delayed-eviction/slot-reuse controller replay; not hardware measurement",
        "m0_provenance": provenance,
        "m1_provenance": m1_provenance,
        "request": {**request_provenance, "input_shape": list(input_ids.shape)},
        "trace_off_on_equivalence": {"token_logit_cache_digests_identical": True},
        "official_dms_capture": {
            "native_event_summary": observed_summary,
            "m1_event_summary_comparison": m1_event_comparison,
            "decision_stream": stream,
            "dms_cache_ring_window_size": dms_window_size,
            "dms_configured_decision_window_size": int(model.config.dms_window_size),
        },
        "independent_controller_replay": replay,
        "observational_guards": {
            "official_dms_model_and_base_tokenizer_bound_to_completed_m0": True,
            "completed_m1_observer_equivalence_and_full_coverage_bound": True,
            "captured_official_binary_decision_stream": True,
            "all_36_layers_all_8_kv_heads_replayed": replay["all_36_layers_all_8_kv_heads_replayed"],
            "per_event_native_cache_length_agreement": replay["per_event_native_cache_length_agreement"],
            "final_native_cache_length_matrix_agreement": True,
            "native_dms_cache_used": True,
            "kvpress_dmspress_used": False,
            "kvzap_predictor_used": False,
            "route_a_backend_instantiated": False,
            "packed_cold_store_instantiated": False,
            "fake_key_attention_used": False,
            "generation_api_used": False,
        },
        "boundaries": [
            "The captured binary decisions and native cache-length agreement are trace-derived software evidence for one fixed request; the controller is a functional, explicitly scoped delayed-eviction/slot-reuse contract replay.",
            "Abstract controller slots are native-cache-index semantics only. They are not K/V payload movement, a Route-A hot/pending/packed-cold mapping, physical capacity, allocator behavior, or an external storage interface.",
            "No field is HBM/DRAM traffic, true hardware latency, throughput, energy, area, hardware acceleration, architecture specification, quality result, or RTL evidence.",
        ],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    (args.output_dir / "dms_m2_adapter_contract_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"DMS M2 adapter-contract gate passed: {args.output_dir}")


if __name__ == "__main__":
    main()
