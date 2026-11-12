#!/usr/bin/env python3
"""A4.9.1 declared-candidate metadata-engine replay (no model/RTL)."""
from __future__ import annotations

from kvpress.research.metadata import LAYOUT, CANDIDATES, candidate_summarize as summarize, candidate_duration as duration, candidate_replay as replay

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a4721_metadata_physical_dse import SCHEMA as A4721_SCHEMA
from tools.analyze_kvzap_route_a4720_metadata_storage_sufficiency import (
    SCHEMA as A4720_SCHEMA, modeled_object_bits, semantic_record_bits,
)
from tools.analyze_kvzap_route_a480_commit_aware_backlog import (
    dependency_predecessors, iter_contexts, make_scheduled_transactions,
)
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

SCHEMA = "kvzap-route-a491-candidate-metadata-engine-1.0"
A490_SCHEMA = "kvzap-route-a490-eager-rmw-envelope-1.0"
# Every tuple is a declared abstract candidate, not a selected implementation.


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.9.1 trace-driven declared-candidate metadata-engine cycle model; not measured hardware timing.")
    p.add_argument("--a468220-trace", type=Path, required=True)
    p.add_argument("--a471-trace", type=Path, required=True)
    p.add_argument("--a4720-report", type=Path, required=True)
    p.add_argument("--a4721-report", type=Path, required=True)
    p.add_argument("--a490-report", type=Path, required=True)
    p.add_argument("--post-trace-cycle-limit", type=int, default=4096, help="Declared model drain bound in abstract cycles, not latency.")
    p.add_argument("--preflight-only", action="store_true")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory.")
    return p.parse_args()




def validate(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    a490 = read_completed(args.a490_report, A490_SCHEMA, "A4.9.0 _03")
    a4721 = read_completed(args.a4721_report, A4721_SCHEMA, "A4.7.2.1 _03")
    a4720 = read_completed(args.a4720_report, A4720_SCHEMA, "A4.7.2.0")
    if not all(a490["envelope_exit_observation"].values()): raise ValueError("A4.9.0 exit incomplete")
    if a490["input_artifacts"]["a468220_trace_sha256"] != sha256_file(args.a468220_trace): raise ValueError("A4.9.0 record trace hash mismatch")
    if a490["input_artifacts"]["a471_trace_sha256"] != sha256_file(args.a471_trace): raise ValueError("A4.9.0 transaction trace hash mismatch")
    if a490["input_artifacts"]["a4721_report_sha256"] != sha256_file(args.a4721_report): raise ValueError("A4.9.0 physical-DSE hash mismatch")
    if a490["input_artifacts"]["a4720_report_sha256"] != sha256_file(args.a4720_report): raise ValueError("A4.9.0 field-width report hash mismatch")
    if not any(x.get("layout") == LAYOUT for x in a4721["static_candidate_rows"]): raise ValueError("fixed layout missing")
    return a490, a4721, a4720


def entry_sufficiency(a4721: dict[str, Any]) -> dict[str, Any]:
    """Select one declared per-head/reuse reference and make word padding explicit."""
    row = next((x for x in a4721["static_candidate_rows"] if x.get("layout") == LAYOUT and x.get("storage_scope") == "per_head" and x.get("namespace_policy") == "reuse_after_terminal_commit" and int(x.get("generation_bits", -1)) == 0), None)
    if row is None: raise ValueError("declared A4.9.1 per-head reuse reference absent")
    widths = {k: int(v) for k, v in row["cross_context_joint_safe_field_widths_bits"].items()}
    raw = modeled_object_bits(LAYOUT, semantic_record_bits(widths))
    padded = {name: ((bits + 63) // 64) * 64 for name, bits in raw.items()}
    counts = {k: int(v) for k, v in row["cross_context_joint_safe_modeled_storage_object_counts"].items()}
    raw_total = sum(counts[name] * raw[name] for name in counts)
    if raw_total != int(row["cross_context_joint_safe_modeled_metadata_bits"]): raise AssertionError("joint-safe object accounting mismatch")
    if any(raw[name] > padded[name] or padded[name] % 64 for name in raw): raise AssertionError("candidate entry padding insufficient")
    return {"storage_scope": row["storage_scope"], "namespace_policy": row["namespace_policy"], "generation_bits": row["generation_bits"], "context_count": row["context_count"], "joint_safe_field_widths_bits": widths, "modeled_object_raw_width_bits": raw, "candidate_entry_width_bits": padded, "modeled_object_counts": counts, "joint_safe_raw_metadata_bits": raw_total, "candidate_aligned_metadata_bits": sum(counts[name] * padded[name] for name in counts), "alignment_bits": 64, "physical_entry_boundary": "This word-padded entry accounting is a declared candidate model, not an SRAM macro allocation or measurement."}






def main() -> None:
    args = parse_args(); a490, a4721, _a4720 = validate(args); entries = entry_sufficiency(a4721)
    if args.preflight_only:
        print("A4.9.1 preflight passed: A4.9.0 exit and immutable input bindings validated; no output created."); return
    if args.output_dir.exists(): raise FileExistsError(args.output_dir)
    rows=[]
    for key, record_ops, groups in iter_contexts(args.a468220_trace, args.a471_trace):
        predecessors, _ = dependency_predecessors(record_ops, groups)
        for candidate in CANDIDATES:
            profile={"layout": LAYOUT, "bank_count": candidate["banks"], "bank_mapping": candidate["mapping"]}
            txs, ops = make_scheduled_transactions(groups, predecessors, profile)
            out=replay(txs, ops, candidate, args.post_trace_cycle_limit)
            rows.append({"anchor":key[0],"workload":key[1],"evaluation_horizon_append_opportunities":key[2],"organization_label":key[3],"candidate":candidate,"result":out})
    report={"schema_version":SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"input_artifacts":{"a468220_trace_sha256":sha256_file(args.a468220_trace),"a471_trace_sha256":sha256_file(args.a471_trace),"a4720_report_sha256":sha256_file(args.a4720_report),"a4721_report_sha256":sha256_file(args.a4721_report),"a490_report_sha256":sha256_file(args.a490_report)},"candidate_entry_sufficiency":entries,"config":{"candidates":CANDIDATES,"fixed_layout":LAYOUT,"entry_alignment_bits":64,"boundary":"Candidate parameters and abstract cycles are declared model assumptions. Results are not measured hardware timing, throughput, bandwidth, energy, area, an architecture selection, or RTL evidence."},"semantic_guards":{"a490_exit_and_hash_chain_validated":True,"joint_safe_field_widths_fit_every_declared_word_padded_modeled_object":True,"fifo_ownership_and_commit_predecessors_reused_unchanged":True,"candidate_queue_overflow_is_observed_never_dropped":True,"no_model_or_pruning_path_loaded":True,"no_hardware_measurement_claim":True},"candidate_context_rows":rows}
    report["config_hash"]=stable_hash(report["config"])
    args.output_dir.mkdir(parents=True); path=args.output_dir/"a491_candidate_metadata_engine_report.json"; path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(f"A4.9.1 complete: {path} sha256={hashlib.sha256(path.read_bytes()).hexdigest()} rows={len(rows)}")

if __name__ == "__main__": main()
