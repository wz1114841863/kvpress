#!/usr/bin/env python3
"""Bind A4.11.2b external-storage lifecycle scalars to the fixed A4.10 model."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from kvpress.route_a_attention import RouteALifecycleTransitionRecorder
from tools.analyze_kvzap_route_a4721_metadata_physical_dse import bank_index
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash
from tools.run_kvzap_route_a412_whole_decode_gate import read_source
from tools.simulate_kvzap_route_a410_queue_contract import ORGANIZATIONS, replay
from tools.simulate_kvzap_route_a492_record_granular_engine import MicroOp
from tools.analyze_kvzap_route_a480_commit_aware_backlog import ScheduledTransaction


SCHEMA = "kvzap-route-a4112b-external-storage-binding-1.0"
MANIFEST_SCHEMA = "kvzap-route-a4112b-external-storage-lifecycle-1.0"
WORKLOADS = ("retrieval", "summarization", "reasoning")
WINDOW = 128
PAGE_TOKENS = 64
POST_TRACE_DRAIN_LIMIT = 4096


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.11.2b no-model external-storage lifecycle to fixed-A4.10 binding report; not a hardware calibration.")
    p.add_argument("--a410-report", type=Path, required=True)
    p.add_argument("--a4111-report", type=Path, required=True)
    for workload in WORKLOADS:
        p.add_argument(f"--{workload}-manifest", type=Path, required=True)
    p.add_argument("--preflight-only", action="store_true")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} is absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def read_events(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def summarize(values: list[int]) -> dict[str, int]:
    if not values:
        return {"count": 0, "min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "sum": 0}
    values = sorted(values); n = len(values)
    return {"count": n, "min": values[0], "p50": values[int((n - 1) * .5)], "p95": values[int((n - 1) * .95)], "p99": values[int((n - 1) * .99)], "max": values[-1], "sum": sum(values)}


def expected_heads(events: list[dict[str, Any]]) -> dict[int, list[int]]:
    result: dict[int, list[int]] = {}
    for event in events:
        layer = int(event["layer"])
        heads = [int(row["kv_head"]) for row in event["heads"]]
        if heads != list(range(len(heads))):
            raise ValueError("lifecycle event KV-head order is not contiguous")
        prior = result.setdefault(layer, heads)
        if prior != heads:
            raise ValueError("lifecycle event KV-head coverage changes by append")
    if sorted(result) != list(range(36)) or sum(map(len, result.values())) != 288:
        raise ValueError("A4.11.2b requires all 36 layers and 288 KV heads")
    return result


def validate_event_rows(events: list[dict[str, Any]], heads: dict[int, list[int]]) -> None:
    last_end: dict[int, int] = {}
    for sequence, event in enumerate(events):
        if int(event.get("logical_transition_sequence", -1)) != sequence or event.get("timestamps_recorded") is not False:
            raise ValueError("lifecycle trace sequence/timestamp guard failed")
        layer, start, end = int(event["layer"]), int(event["start_position"]), int(event["end_position"])
        if event.get("phase") not in {"prefill", "multi_token", "decode"} or end < start or int(event["input_token_count"]) != end - start + 1:
            raise ValueError("lifecycle event dimensions are invalid")
        if start != last_end.get(layer, -1) + 1:
            raise ValueError("lifecycle layer positions are non-contiguous")
        last_end[layer] = end
        if [int(row["kv_head"]) for row in event["heads"]] != heads[layer]:
            raise ValueError("lifecycle event head coverage differs from expected")
        for row in event["heads"]:
            fields = ("pending_tokens_before_maturity", "matured_kept_tokens", "matured_dropped_tokens", "pending_tokens_after_maturity", "admitted_tokens", "pending_tokens_after_service", "packed_tokens_before", "packed_tokens_after_service", "packed_page_count_after_service", "packed_full_page_count_after_service", "packed_tail_tokens_after_service")
            if any(not isinstance(row.get(key), int) or row[key] < 0 for key in fields):
                raise ValueError("lifecycle event scalar field is invalid")
            if row["pending_tokens_after_maturity"] != row["pending_tokens_before_maturity"] + row["matured_kept_tokens"]:
                raise ValueError("lifecycle maturity conservation failed")
            if row["pending_tokens_after_service"] != row["pending_tokens_after_maturity"] - row["admitted_tokens"]:
                raise ValueError("lifecycle service conservation failed")
            if row["packed_tokens_after_service"] != row["packed_tokens_before"] + row["admitted_tokens"]:
                raise ValueError("lifecycle packed conservation failed")
    for layer in heads:
        first = next(event for event in events if int(event["layer"]) == layer)
        if first["phase"] != "prefill" or int(first["start_position"]) != 0:
            raise ValueError("trace was not armed before external-storage prefill")


def mature_positions(event: dict[str, Any]) -> range:
    first = max(0, int(event["start_position"]) - WINDOW)
    last = int(event["end_position"]) - WINDOW
    return range(first, last + 1) if first <= last else range(0)


def direct_and_converted(events: list[dict[str, Any]], replay_events, candidate: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct retained maturity from frozen masks and lower a fixed span group.

    One group is one (append event, layer, KV head, 64-token logical span)
    containing one or more retained tokens.  It has a declared head-control RMW
    and span-owner RMW member, preserves per-head FIFO, and is only the fixed
    token-to-span binding conversion -- not an observed hardware transaction.
    """
    previous_by_head: dict[tuple[int, int], int] = {}
    transactions: list[ScheduledTransaction] = []
    members: dict[int, tuple[MicroOp, ...]] = {}
    opportunities = [("external_lifecycle_append", int(event["logical_transition_sequence"])) for event in events]
    arrivals = service = dropped = 0
    pending_after_maturity: list[int] = []; pending_after_service: list[int] = []
    packed_pages: list[int] = []; packed_full_pages: list[int] = []
    per_layer_pending: Counter[int] = Counter()
    for event in events:
        layer, ordinal = int(event["layer"]), int(event["logical_transition_sequence"])
        positions = list(mature_positions(event))
        for row in event["heads"]:
            head = int(row["kv_head"])
            retained = [position for position in positions if bool(replay_events[layer][(head, position)][0])]
            rejected = len(positions) - len(retained)
            if len(retained) != row["matured_kept_tokens"] or rejected != row["matured_dropped_tokens"]:
                raise ValueError("reconstructed frozen-mask maturity differs from external-storage trace")
            arrivals += len(retained); dropped += rejected; service += int(row["admitted_tokens"])
            pending_after_maturity.append(int(row["pending_tokens_after_maturity"])); pending_after_service.append(int(row["pending_tokens_after_service"]))
            packed_pages.append(int(row["packed_page_count_after_service"])); packed_full_pages.append(int(row["packed_full_page_count_after_service"]))
            per_layer_pending[layer] = max(per_layer_pending[layer], int(row["pending_tokens_after_maturity"]))
            by_span: dict[int, int] = Counter(position // PAGE_TOKENS for position in retained)
            for span, token_count in sorted(by_span.items()):
                index = len(transactions); head_key = (layer, head)
                predecessors = frozenset(() if head_key not in previous_by_head else (previous_by_head[head_key],))
                head_object = ("head_control", (layer, head))
                span_object = ("span_owner", (layer, head, span))
                head_bank = bank_index(candidate["mapping"], candidate["banks"], head_object, layer=layer, head=head)
                span_bank = bank_index(candidate["mapping"], candidate["banks"], span_object, layer=layer, head=head)
                op_members = (
                    MicroOp(index, head_object, head_bank, "rmw"),
                    MicroOp(index, span_object, span_bank, "rmw"),
                )
                transactions.append(ScheduledTransaction(index=index, phase="external_lifecycle_append", checkpoint=ordinal, layer=layer, head=head, arrival_ordinal=ordinal, predecessors=predecessors, demands=Counter((item.bank, item.operation) for item in op_members), banks=frozenset(item.bank for item in op_members)))
                members[index] = op_members; previous_by_head[head_key] = index
    result = replay(transactions, opportunities, members, candidate, ORGANIZATIONS[-1], POST_TRACE_DRAIN_LIMIT)
    final = { (int(event["layer"]), int(row["kv_head"])): int(row["pending_tokens_after_service"]) for event in events for row in event["heads"] }
    return {
        "direct_software_observation": {"matured_kept_tokens": arrivals, "matured_dropped_tokens": dropped, "logical_admission_service_tokens": service, "trace_end_residual_pending_tokens": sum(final.values()), "trace_end_residual_nonempty_heads": sum(value > 0 for value in final.values()), "per_head_pending_after_maturity": summarize(pending_after_maturity), "per_head_pending_after_service": summarize(pending_after_service), "per_layer_pending_after_maturity_max": summarize(list(per_layer_pending.values())), "packed_page_count_per_head": summarize(packed_pages), "packed_full_page_count_per_head": summarize(packed_full_pages)},
        "fixed_token_span_transaction_conversion": {"token_to_span_tokens": PAGE_TOKENS, "conversion_group": "one append-event/layer/KV-head/logical-span fragment", "transaction_members": ["head_control_rmw", "span_owner_rmw"], "per_head_fifo_predecessor": True, "generated_transaction_groups": len(transactions), "retained_tokens_reconstructed_from_frozen_replay_mask": arrivals, "boundary": "This deterministic conversion is an A4.11.2b binding input, not an observed ready/commit/bank/RMW event and not the immutable A4.7.1 transaction trace."},
        "fixed_a410_ha8_wide_local32_shared256_staging512_envelope": result,
    }


def validate_manifest(path: Path, workload: str, a4111_hash: str, candidate: dict[str, Any]) -> dict[str, Any]:
    manifest = read_json(path, f"{workload} manifest")
    if manifest.get("schema_version") != MANIFEST_SCHEMA or manifest.get("status") != "complete":
        raise ValueError(f"{workload}: lifecycle run is incomplete or incompatible")
    config = manifest.get("config", {})
    if config.get("preset") != workload or config.get("window_size") != WINDOW or config.get("page_tokens") != PAGE_TOKENS or config.get("admission_budget") != 512:
        raise ValueError(f"{workload}: fixed external-storage configuration changed")
    binding = manifest.get("a4111_binding", {})
    if binding.get("report_sha256") != a4111_hash or binding.get("a4111_same_mask_dense_route_a_token_digest_equal") is not True:
        raise ValueError(f"{workload}: A4.11.1 exact-token binding is absent")
    guards = manifest.get("observational_guards", {})
    required = ("trace_armed_before_external_storage_prefill", "trace_off_trace_on_generated_token_ids_equal", "trace_on_same_mask_dense_generated_token_ids_equal", "replay_mask_consumption_complete_all_paths", "all_layers_all_kv_heads_external_storage_covered", "recorder_final_packed_pending_cold_state_unchanged", "no_drop_or_reorder_or_new_full_kv_fallback", "policy_reference_not_used_as_correctness_oracle")
    if any(guards.get(name) is not True for name in required):
        raise ValueError(f"{workload}: external-storage lifecycle guard is incomplete")
    outcomes = manifest.get("outcomes", {})
    dense, off, on = outcomes.get("same_mask_dense", {}), outcomes.get("external_storage_trace_off", {}), outcomes.get("external_storage_trace_on", {})
    if not (dense.get("generated_token_ids_sha256") == off.get("generated_token_ids_sha256") == on.get("generated_token_ids_sha256")):
        raise ValueError(f"{workload}: exact generated-token digest diverged")
    if off.get("final_state") != on.get("final_state"):
        raise ValueError(f"{workload}: recorder changed external final state")
    trace = manifest.get("lifecycle_transition_trace", {})
    if trace.get("schema_version") != RouteALifecycleTransitionRecorder.SCHEMA or trace.get("recording_semantics", "").startswith("external-storage") is False:
        raise ValueError(f"{workload}: lifecycle trace schema/semantics mismatch")
    trace_path = path.parent / trace.get("path", "")
    if not trace_path.is_file() or sha256_file(trace_path) != trace.get("sha256"):
        raise ValueError(f"{workload}: lifecycle trace hash mismatch")
    events = read_events(trace_path); heads = expected_heads(events); validate_event_rows(events, heads)
    replay_dir = Path(manifest["replay_source"]["directory"])
    source_args = SimpleNamespace(**{
        name: config[name]
        for name in ("model_name", "model_revision", "predictor_name", "predictor_revision", "threshold", "window_size", "page_tokens", "context_repetitions", "max_new_tokens", "seed")
    })
    replay_events, _source, replay_sha = read_source(replay_dir, args=source_args, layers=tuple(range(36)))
    if replay_sha != manifest["replay_source"]["event_file_sha256"]:
        raise ValueError(f"{workload}: replay source hash changed")
    return {"workload": workload, "manifest": str(path), "manifest_sha256": sha256_file(path), "lifecycle_trace": str(trace_path), "lifecycle_trace_sha256": trace["sha256"], "exact_generated_token_ids_sha256": on["generated_token_ids_sha256"], **direct_and_converted(events, replay_events, candidate)}


def main() -> None:
    args = parse_args()
    a410 = read_json(args.a410_report, "A4.10 report")
    if a410.get("schema_version") != "kvzap-route-a410-queue-staging-credit-contract-1.0" or a410.get("status") != "complete":
        raise ValueError("A4.10 report is incomplete or incompatible")
    config = a410.get("config", {})
    if (config.get("fixed_execution"), config.get("local_capacity_per_bank"), config.get("shared_capacity_per_layer"), config.get("staging_capacity_per_layer")) != ("A4.9.2 record-granular only", 32, 256, 512):
        raise ValueError("fixed A4.10 queue/staging contract changed")
    candidates = [row.get("candidate") for row in a410.get("candidate_context_rows", []) if row.get("candidate", {}).get("name") == "ha8_wide"]
    if not candidates or any(candidate != candidates[0] for candidate in candidates):
        raise ValueError("A4.10 HA8-wide catalog is absent or inconsistent")
    candidate = candidates[0]
    a4111_hash = sha256_file(args.a4111_report)
    a4111 = read_json(args.a4111_report, "A4.11.1 report")
    if a4111.get("schema_version") != "kvzap-route-a4111-trace-off-measurement-matrix-1.0" or a4111.get("status") != "complete":
        raise ValueError("A4.11.1 report is incomplete or incompatible")
    rows = [validate_manifest(getattr(args, f"{workload}_manifest"), workload, a4111_hash, candidate) for workload in WORKLOADS]
    if args.preflight_only:
        print("A4.11.2b binding preflight passed: external-storage exact-token guards, scalar traces, and fixed conversion inputs validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": {"stage": "A4.11.2b", "fixed_a410_execution": "record-granular HA8-wide", "local_capacity_per_bank": 32, "shared_capacity_per_layer": 256, "staging_capacity_per_layer": 512, "token_to_span_tokens": PAGE_TOKENS, "post_trace_drain_limit": POST_TRACE_DRAIN_LIMIT}, "input_artifacts": {"a410_report": str(args.a410_report), "a410_report_sha256": sha256_file(args.a410_report), "a4111_report": str(args.a4111_report), "a4111_report_sha256": a4111_hash}, "workloads": rows, "evidence_classes": {"direct_software_observation": ["maturity", "logical pending", "logical service", "packed page state", "trace-end residual"], "deterministic_conversion": ["frozen replay-mask token to 64-token span to append-event transaction group"], "declared_hardware_model_only": ["bank mapping", "ready group", "RMW service", "queue occupancy", "credit latency", "commit timing"]}, "semantic_guards": {"a4111_external_storage_exact_token_guard_remains_bound": True, "trace_on_external_storage_is_token_identical_to_trace_off_and_dense": True, "prefill_armed_external_storage_lifecycle_observed": True, "fixed_a410_parameters_not_retuned": True, "unmapped_hardware_fields_not_synthesized": True, "no_hardware_queue_measurement_or_performance_claim": True}, "boundaries": ["The A4.10 envelope below is a fixed declared-model replay over a deterministic binding conversion. It is not measured FIFO occupancy, hardware timing, SRAM sizing, throughput, energy, area, architecture, or RTL.", "The conversion emits no software ready, micro-op done, bank-port, RMW completion, credit, or physical-commit event. Those fields remain modeled only."], "config_hash": None}
    report["config_hash"] = stable_hash(report["config"])
    args.output_dir.mkdir(parents=True)
    path = args.output_dir / "a4112b_external_storage_lifecycle_binding_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.11.2b binding complete: {path} sha256={sha256_file(path)} workloads={len(rows)}")


if __name__ == "__main__":
    main()
