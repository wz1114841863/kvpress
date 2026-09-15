#!/usr/bin/env python3
"""Validate DMS active-native-slot topology without replacing DMS attention.

DMS-M3 is a control/topology gate.  It observes official DMS ring metadata and
replays the binary decisions into abstract logical-source positions.  No K/V
payload, token ID/text, attention result, Route-A backend, or hardware model is
introduced.  This asks whether the documented native resident-slot lifecycle is
expressible as a bounded adapter contract before attempting any attention
substitution.
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
    git_commit,
    model_input,
    read_completed_m0,
    run_native_pass,
    stable_hash,
    summarize_events,
    validate_input_contract,
)
from tools.run_dms_route_a_m2_adapter_contract_gate import M2_SCHEMA, read_completed_m1
from tools.run_kvzap_trace import PRESETS, build_builtin_request, load_jsonl_request, seed_everything
from tools.validate_dms_m0_official_provenance import sha256_file


M3_SCHEMA = "route-a-dms-m3-active-native-slot-topology-1.0"
DECISION_STREAM_SCHEMA = "route-a-dms-decision-stream-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "DMS-M3 native active-slot topology replay; not Route-A attention, "
            "a hardware model, or a benchmark."
        )
    )
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--preset", choices=PRESETS, default="retrieval")
    request.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--context-repetitions", type=int, default=8)
    parser.add_argument("--m0-manifest", type=Path, required=True)
    parser.add_argument("--m1-manifest", type=Path, required=True)
    parser.add_argument("--m2-manifest", type=Path, required=True)
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--tokenizer-root", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--decode-steps", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validate-inputs-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def read_completed_m2(path: Path, *, m0_manifest: Path, m1_manifest: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"DMS-M2 manifest is absent: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != M2_SCHEMA or report.get("status") != "complete":
        raise ValueError("DMS-M3 requires a completed route-a-dms-m2-delayed-eviction-adapter-contract-1.0 manifest")
    if report.get("m0_provenance", {}).get("m0_manifest_sha256") != sha256_file(m0_manifest):
        raise ValueError("DMS-M2 is not bound to the supplied completed DMS-M0 manifest")
    if report.get("m1_provenance", {}).get("m1_manifest_sha256") != sha256_file(m1_manifest):
        raise ValueError("DMS-M2 is not bound to the supplied completed DMS-M1 manifest")
    guards = report.get("observational_guards")
    replay = report.get("independent_controller_replay")
    capture = report.get("official_dms_capture")
    stream = capture.get("decision_stream") if isinstance(capture, dict) else None
    if not isinstance(guards, dict) or guards.get("per_event_native_cache_length_agreement") is not True:
        raise ValueError("DMS-M2 lacks per-event native cache-length agreement")
    if not isinstance(replay, dict) or replay.get("all_36_layers_all_8_kv_heads_replayed") is not True:
        raise ValueError("DMS-M2 lacks full layer/KV-head controller coverage")
    if not isinstance(stream, dict) or stream.get("schema_version") != DECISION_STREAM_SCHEMA:
        raise ValueError("DMS-M2 lacks the required compact official decision stream")
    stream_path = path.parent / str(stream.get("path", ""))
    if not stream_path.is_file() or sha256_file(stream_path) != stream.get("sha256"):
        raise ValueError("DMS-M2 decision stream is missing or differs from its recorded SHA-256")
    with np.load(stream_path, allow_pickle=False) as arrays:
        if arrays["schema_version"].tolist() != [DECISION_STREAM_SCHEMA]:
            raise ValueError("DMS-M2 decision stream schema payload differs from its manifest")
        if int(arrays["event_layer"].shape[0]) != int(stream.get("event_count", -1)):
            raise ValueError("DMS-M2 decision stream event count differs from its manifest")
    return report


def public_event(event: dict[str, Any]) -> dict[str, Any]:
    """Drop in-memory tensors before JSON summaries."""
    return {
        key: value
        for key, value in event.items()
        if key not in {"decision_bits", "native_recent_info", "native_recent_info_position"}
    }


class ActiveSlotTopologyController:
    """Pure-Python DMS control model with logical-source provenance.

    ``slot`` follows the native DMS cache's logical slot index.  ``source`` is
    only the zero-based arrival serial within one layer/KV-head; it is not an
    input token ID, a K/V address, or physical-memory metadata.
    """

    def __init__(self, window_size: int):
        if window_size < 2:
            raise ValueError("DMS active-slot topology controller requires window_size >= 2")
        self.window_size = window_size
        self.recent: list[dict[str, int]] = [{"slot": 0, "evict": 0, "source": -1} for _ in range(window_size)]
        self.recent_position = 0
        self.cache_length = 0
        self.arrival_count = 0
        self.slot_to_source: list[int] = []

    def consume(self, decisions: np.ndarray) -> list[int]:
        if decisions.ndim != 1 or not np.isin(decisions, [0, 1]).all():
            raise ValueError("DMS-M3 controller requires a binary rank-1 decision stream")
        slots: list[int] = []
        for decision in decisions.tolist():
            candidate_index = self.recent_position % self.window_size
            candidate = self.recent[candidate_index]
            evict = int(candidate["evict"] == 1)
            slot = int(candidate["slot"] if evict else self.cache_length)
            if evict:
                if slot >= self.cache_length:
                    raise AssertionError("controller attempted to reuse a nonresident native slot")
            else:
                if slot != len(self.slot_to_source):
                    raise AssertionError("controller append slot is not the next native logical slot")
                self.slot_to_source.append(-1)
            previous_index = (self.recent_position + self.window_size - 1) % self.window_size
            if self.cache_length > 0:
                self.recent[previous_index]["evict"] = int(decision)
            self.recent[candidate_index] = {"slot": slot, "evict": 0, "source": self.arrival_count}
            self.slot_to_source[slot] = self.arrival_count
            self.arrival_count += 1
            self.recent_position += 1
            self.cache_length += 1 - evict
            slots.append(slot)
        self.assert_invariants()
        return slots

    def native_recent_info(self) -> np.ndarray:
        return np.asarray([[entry["slot"], entry["evict"]] for entry in self.recent], dtype=np.int32)

    def active_sources(self) -> list[int]:
        return list(self.slot_to_source[: self.cache_length])

    def assert_invariants(self) -> None:
        active = self.active_sources()
        if len(active) != self.cache_length or any(value < 0 or value >= self.arrival_count for value in active):
            raise AssertionError("controller active slot/source domain is invalid")
        if len(set(active)) != len(active):
            raise AssertionError("controller maps multiple active native slots to one source arrival")
        for entry in self.recent:
            if entry["slot"] < 0 or entry["slot"] >= max(self.cache_length, 1):
                raise AssertionError("controller recent ring points outside native logical slots")


def replay_topology(events: list[dict[str, Any]], *, window_size: int) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    controllers = [[ActiveSlotTopologyController(window_size) for _ in range(EXPECTED_KV_HEADS)] for _ in range(EXPECTED_LAYERS)]
    event_count = 0
    native_control_agreement = True
    for event in events:
        layer = int(event["layer"])
        decisions = event.get("decision_bits")
        native_recent = event.get("native_recent_info")
        native_position = event.get("native_recent_info_position")
        expected_shape = (EXPECTED_KV_HEADS, int(event["q_len"]))
        if not isinstance(decisions, np.ndarray) or decisions.shape != expected_shape:
            raise AssertionError(f"layer {layer}: malformed captured decision stream")
        if not isinstance(native_recent, np.ndarray) or native_recent.shape != (EXPECTED_KV_HEADS, window_size, 2):
            raise AssertionError(f"layer {layer}: malformed native recent-info metadata")
        if not isinstance(native_position, np.ndarray) or native_position.shape != (EXPECTED_KV_HEADS,):
            raise AssertionError(f"layer {layer}: malformed native recent-info cursor")
        before = [controller.cache_length for controller in controllers[layer]]
        if before != event["cache_lengths_before"]:
            raise AssertionError(f"layer {layer} call {event['call_index']}: native/controller pre-length mismatch")
        for head in range(EXPECTED_KV_HEADS):
            controllers[layer][head].consume(decisions[head])
            if not np.array_equal(controllers[layer][head].native_recent_info(), native_recent[head]):
                native_control_agreement = False
                raise AssertionError(f"layer {layer} head {head} call {event['call_index']}: native/controller ring metadata mismatch")
            if controllers[layer][head].recent_position != int(native_position[head]):
                native_control_agreement = False
                raise AssertionError(f"layer {layer} head {head} call {event['call_index']}: native/controller ring cursor mismatch")
        after = [controller.cache_length for controller in controllers[layer]]
        if after != event["cache_lengths_after"]:
            raise AssertionError(f"layer {layer} call {event['call_index']}: native/controller post-length mismatch")
        event_count += 1
    final_lengths = np.asarray([[controller.cache_length for controller in row] for row in controllers], dtype=np.int32)
    max_length = int(final_lengths.max())
    active_sources = np.full((EXPECTED_LAYERS, EXPECTED_KV_HEADS, max_length), -1, dtype=np.int32)
    nonmonotonic: list[dict[str, int]] = []
    for layer in range(EXPECTED_LAYERS):
        for head in range(EXPECTED_KV_HEADS):
            sources = controllers[layer][head].active_sources()
            active_sources[layer, head, : len(sources)] = sources
            inversions = sum(int(right < left) for left, right in zip(sources, sources[1:]))
            if inversions:
                nonmonotonic.append({"layer": layer, "kv_head": head, "adjacent_descents": inversions})
    histories = np.asarray([[controller.arrival_count for controller in row] for row in controllers], dtype=np.int32)
    if not bool((histories == histories[0, 0]).all()):
        raise AssertionError("all layer/KV-head controllers must see the same fixed request horizon")
    summary = {
        "event_count": event_count,
        "all_36_layers_all_8_kv_heads_replayed": event_count > 0,
        "per_event_native_cache_length_agreement": True,
        "per_event_native_ring_metadata_agreement": native_control_agreement,
        "final_logical_history_tokens": int(histories[0, 0]),
        "final_active_native_slot_count_total": int(final_lengths.sum()),
        "final_discarded_source_arrivals_total": int((histories - final_lengths).sum()),
        "final_active_source_unique_per_layer_kv_head": True,
        "final_active_physical_slot_order_nonmonotonic_layer_kv_heads": nonmonotonic,
        "final_active_physical_slot_order_nonmonotonic_count": len(nonmonotonic),
        "final_length_sha256": hashlib.sha256(final_lengths.tobytes()).hexdigest(),
        "final_active_source_topology_sha256": hashlib.sha256(active_sources.tobytes()).hexdigest(),
    }
    return summary, final_lengths, active_sources


def write_control_trace(path: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    decisions = [event["decision_bits"].astype(np.uint8, copy=False).reshape(-1) for event in events]
    offsets = np.zeros((len(events) + 1,), dtype=np.int64)
    offsets[1:] = np.cumsum([item.size for item in decisions], dtype=np.int64)
    np.savez_compressed(
        path,
        schema_version=np.asarray(["route-a-dms-native-control-trace-1.0"]),
        decision_bits=np.concatenate(decisions),
        event_bit_offsets=offsets,
        event_layer=np.asarray([event["layer"] for event in events], dtype=np.int16),
        event_call_index=np.asarray([event["call_index"] for event in events], dtype=np.int16),
        event_q_len=np.asarray([event["q_len"] for event in events], dtype=np.int32),
        event_kind_code=np.asarray([0 if event["kind"] == "prefill" else 1 for event in events], dtype=np.int8),
        native_cache_lengths_before=np.asarray([event["cache_lengths_before"] for event in events], dtype=np.int32),
        native_cache_lengths_after=np.asarray([event["cache_lengths_after"] for event in events], dtype=np.int32),
        native_recent_info=np.stack([event["native_recent_info"] for event in events]).astype(np.int32, copy=False),
        native_recent_info_position=np.stack([event["native_recent_info_position"] for event in events]).astype(np.int32, copy=False),
    )
    return {"path": path.name, "sha256": sha256_file(path), "schema_version": "route-a-dms-native-control-trace-1.0", "event_count": len(events)}


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"DMS-M3 output directory already exists: {args.output_dir}")
    if args.request_id is not None and args.input_jsonl is None:
        raise ValueError("--request-id requires --input-jsonl")
    if args.context_repetitions < 2 or args.decode_steps < 2:
        raise ValueError("DMS-M3 requires context-repetitions >= 2 and decode-steps >= 2")
    m0 = read_completed_m0(args.m0_manifest)
    m1 = read_completed_m1(args.m1_manifest, m0_manifest=args.m0_manifest)
    m2 = read_completed_m2(args.m2_manifest, m0_manifest=args.m0_manifest, m1_manifest=args.m1_manifest)
    provenance = validate_input_contract(args, m0)
    config = {key: (str(value) if isinstance(value, Path) else value) for key, value in vars(args).items() if key != "output_dir"}
    m2_provenance = {"m2_manifest_path": str(args.m2_manifest), "m2_manifest_sha256": sha256_file(args.m2_manifest), "m2_decision_stream": m2["official_dms_capture"]["decision_stream"]}
    if args.validate_inputs_only:
        manifest = {
            "schema_version": M3_SCHEMA,
            "status": "input_validated_only",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": git_commit(),
            "config": config,
            "config_hash": stable_hash(config),
            "m0_provenance": provenance,
            "m2_provenance": m2_provenance,
            "boundaries": ["No model, custom checkpoint code, tokenizer, cache, decision, generation, or controller replay call occurred.", "This is not completed DMS-M3 topology, Route-A, hardware, or performance evidence."],
        }
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / "dms_m3_active_topology_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"DMS M3 inputs validated: {args.output_dir}")
        return

    request = load_jsonl_request(args.input_jsonl, args.request_id) if args.input_jsonl else build_builtin_request(args.preset, args.context_repetitions)
    request_provenance = {"request_id": request["request_id"], "content_sha256": stable_hash({"context": request["context"], "question": request["question"]})}
    if m1.get("request", {}).get("content_sha256") != request_provenance["content_sha256"] or m2.get("request", {}).get("content_sha256") != request_provenance["content_sha256"]:
        raise ValueError("DMS-M3 fixed request differs from its M1/M2-bound request provenance")
    device = torch.device(args.device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("DMS-M3 requires an explicitly selected available CUDA device")
    seed_everything(args.seed)
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_root, local_files_only=True, trust_remote_code=True)
    config_object = AutoConfig.from_pretrained(args.snapshot_root, local_files_only=True, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(args.snapshot_root, config=config_object, local_files_only=True, trust_remote_code=True, dtype=torch.bfloat16, device_map="auto").eval()
    if len(model.model.layers) != EXPECTED_LAYERS or int(model.config.num_key_value_heads) != EXPECTED_KV_HEADS:
        raise AssertionError("loaded official DMS model differs from the M0-bound 36-layer/8-KV-head structure")
    ring_window = int(model.config.dms_window_size) + 1
    if ring_window != int(m2["official_dms_capture"]["dms_cache_ring_window_size"]):
        raise AssertionError("loaded official DMS cache ring window differs from completed M2")
    input_ids = model_input(tokenizer, request, model.device)
    if int(input_ids.shape[1]) <= int(model.config.dms_window_size):
        raise ValueError("DMS-M3 request must exceed the official DMS decision-delay window")
    cache_module = importlib.import_module(model.__class__.__module__.rsplit(".", 1)[0] + ".dms_cache")
    print("Pass 1/2: official DMS native cache without topology observation...")
    baseline = run_native_pass(model, input_ids, args.decode_steps, recorder=None)
    print("Pass 2/2: official DMS with read-only decision/ring-metadata observation...")
    with DMSUpdateRecorder(cache_module.DMSCache, capture_decision_bits=True, capture_native_control_state=True) as recorder:
        observed = run_native_pass(model, input_ids, args.decode_steps, recorder=recorder)
    if baseline != observed:
        raise AssertionError("DMS-M3 observation changed official DMS token/logit/cache-state digests")
    events = recorder.events
    observed_summary = summarize_events([public_event(event) for event in events], decode_steps=args.decode_steps)
    replay, final_lengths, active_sources = replay_topology(events, window_size=ring_window)
    if final_lengths.tolist() != observed["final_cache_lengths_by_layer_kv_head"]:
        raise AssertionError("DMS-M3 final topology controller/native cache-length matrix differs")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    control_stream = write_control_trace(args.output_dir / "dms_m3_native_control_trace.npz", events)
    topology_path = args.output_dir / "dms_m3_final_active_slot_topology.npz"
    np.savez_compressed(topology_path, schema_version=np.asarray(["route-a-dms-active-native-slot-topology-1.0"]), final_cache_lengths=final_lengths, active_source_arrival_serial_by_native_slot=active_sources)
    topology_artifact = {"path": topology_path.name, "sha256": sha256_file(topology_path), "contents": "final logical-source arrival serial per active native slot, padded with -1; no token IDs/text or K/V payload"}
    manifest = {
        "schema_version": M3_SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "trace-derived official DMS decision/ring-metadata observation plus functional modeled active-native-slot topology replay; not hardware measurement",
        "m0_provenance": provenance,
        "m2_provenance": m2_provenance,
        "request": {**request_provenance, "input_shape": list(input_ids.shape)},
        "trace_off_on_equivalence": {"token_logit_cache_digests_identical": True},
        "official_native_control_capture": {"native_event_summary": observed_summary, "ring_window_size": ring_window, "control_stream": control_stream},
        "active_native_slot_topology": {**replay, "artifact": topology_artifact},
        "observational_guards": {"official_dms_model_and_base_tokenizer_bound_to_completed_m0": True, "completed_m2_decision_stream_bound": True, "all_36_layers_all_8_kv_heads_replayed": replay["all_36_layers_all_8_kv_heads_replayed"], "per_event_native_cache_length_agreement": replay["per_event_native_cache_length_agreement"], "per_event_native_ring_metadata_agreement": replay["per_event_native_ring_metadata_agreement"], "final_native_cache_length_matrix_agreement": True, "native_dms_cache_used": True, "kvpress_dmspress_used": False, "kvzap_predictor_used": False, "route_a_backend_instantiated": False, "attention_replaced": False, "fake_key_attention_used": False, "generation_api_used": False},
        "boundaries": ["Native decision/ring metadata is trace-derived software state for one fixed request. The logical-source/native-slot map is a functional modeled replay verified against that metadata.", "This does not establish a Route-A hot/pending/packed-cold mapping or functional attention substitution. Active physical-slot order may not be chronological; no order-invariance or numerical attention claim is made here.", "No field is K/V payload, physical capacity, allocator behavior, HBM/DRAM traffic, true hardware latency, throughput, energy, area, quality, hardware acceleration, architecture specification, or RTL evidence."],
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }
    (args.output_dir / "dms_m3_active_topology_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"DMS M3 active-topology gate passed: {args.output_dir}")


if __name__ == "__main__":
    main()
