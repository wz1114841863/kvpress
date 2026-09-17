#!/usr/bin/env python3
"""A4.3.7 no-model, non-pooled Qwen/Llama micro-event Q comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


QWEN_SCHEMA = "kvzap-route-a435-microevent-quantum-sweep-1.0"
LLAMA_SCHEMA = "kvzap-route-a436-llama31-microevent-quantum-sweep-1.0"
SCHEMA = "kvzap-route-a437-cross-anchor-microevent-envelope-1.0"
QUANTA = (1, 8, 32)
WORKLOADS = ("retrieval", "summarization", "reasoning")
METRICS = (
    "logical_event_count",
    "prefill_event_count",
    "max_prefill_event_tokens",
    "pending_p95",
    "pending_max",
    "admitted_tokens_total",
    "packed_tokens_max",
    "full_pages_max",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_report(path: Path, *, expected_schema: str, anchor: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{anchor} report is absent: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("schema_version") != expected_schema or report.get("status") != "complete":
        raise ValueError(f"{anchor} report is not a completed expected schema")
    config = report.get("config")
    if not isinstance(config, dict) or config.get("admission_budgets") != list(QUANTA) or config.get("prefill_maturity_chunk_tokens") != 64:
        raise ValueError(f"{anchor} report lacks the bounded Q={{1,8,32}}/chunk-64 contract")
    if report.get("architecture_spec_gate", {}).get("eligible") is not False or report.get("architecture_spec_gate", {}).get("rtl_authorized") is not False:
        raise ValueError(f"{anchor} input incorrectly authorizes an architecture or RTL")
    if anchor == "llama":
        guards = report.get("observational_guards")
        if config.get("fixed_new_tokens") != 8 or not isinstance(guards, dict) or guards.get("m41_non_strict_summarization_context_retained") is not True:
            raise ValueError("Llama report lacks its required fixed-continuation or record-only context")
    return report


def normalize_workload_row(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("preset") not in WORKLOADS or not isinstance(row.get("quantum_rows"), list):
        raise ValueError("malformed workload row")
    indexed = {value.get("admission_budget"): value.get("transition_summary") for value in row["quantum_rows"]}
    if set(indexed) != set(QUANTA) or any(not isinstance(value, dict) for value in indexed.values()):
        raise ValueError(f"{row.get('preset')}: requires Q=1,8,32 exactly once")
    values: dict[int, dict[str, int]] = {}
    for quantum in QUANTA:
        summary = indexed[quantum]
        if set(METRICS) - set(summary):
            raise ValueError(f"{row['preset']} Q={quantum}: transition summary is incomplete")
        values[quantum] = {metric: int(summary[metric]) for metric in METRICS}
        if any(value < 0 for value in values[quantum].values()) or values[quantum]["max_prefill_event_tokens"] != 64:
            raise ValueError(f"{row['preset']} Q={quantum}: invalid logical summary")
    for metric in ("logical_event_count", "prefill_event_count", "max_prefill_event_tokens"):
        if len({values[quantum][metric] for quantum in QUANTA}) != 1:
            raise ValueError(f"{row['preset']}: micro-event workload changed across Q for {metric}")
    return {"preset": row["preset"], "quantum_summaries": [{"admission_budget": quantum, **values[quantum]} for quantum in QUANTA]}


def reduction(base: int, target: int) -> dict[str, float | int | None]:
    return {
        "absolute_reduction": base - target,
        "relative_reduction_fraction": None if base == 0 else (base - target) / base,
    }


def summarize_direction(row: dict[str, Any]) -> dict[str, Any]:
    values = {item["admission_budget"]: item for item in row["quantum_summaries"]}
    one, eight, thirtytwo = values[1], values[8], values[32]
    nonincreasing = lambda metric: one[metric] >= eight[metric] >= thirtytwo[metric]
    nondecreasing = lambda metric: one[metric] <= eight[metric] <= thirtytwo[metric]
    return row | {
        "within_row_q_sensitivity": {
            "q1_to_q8": {
                "pending_p95": reduction(one["pending_p95"], eight["pending_p95"]),
                "pending_max": reduction(one["pending_max"], eight["pending_max"]),
                "full_pages_max_absolute_increase": eight["full_pages_max"] - one["full_pages_max"],
            },
            "q1_to_q32": {
                "pending_p95": reduction(one["pending_p95"], thirtytwo["pending_p95"]),
                "pending_max": reduction(one["pending_max"], thirtytwo["pending_max"]),
                "full_pages_max_absolute_increase": thirtytwo["full_pages_max"] - one["full_pages_max"],
            },
            "direction_matrix": {
                "pending_p95_nonincreasing": nonincreasing("pending_p95"),
                "pending_max_nonincreasing": nonincreasing("pending_max"),
                "full_pages_max_nondecreasing": nondecreasing("full_pages_max"),
                "packed_tokens_max_nondecreasing": nondecreasing("packed_tokens_max"),
                "admitted_tokens_total_nondecreasing": nondecreasing("admitted_tokens_total"),
            },
        }
    }


def anchor_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("per_workload_rows")
    if not isinstance(rows, list) or {row.get("preset") for row in rows if isinstance(row, dict)} != set(WORKLOADS) or len(rows) != len(WORKLOADS):
        raise ValueError("anchor report must retain retrieval, summarization, and reasoning separately")
    return [summarize_direction(normalize_workload_row(row)) for row in sorted(rows, key=lambda item: item["preset"])]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.3.7 non-pooled Qwen/Llama Q-sensitivity envelope; no hardware range, timing, or parameter selection.")
    parser.add_argument("--qwen-report", type=Path, required=True)
    parser.add_argument("--llama-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    qwen = load_report(args.qwen_report, expected_schema=QWEN_SCHEMA, anchor="qwen")
    llama = load_report(args.llama_report, expected_schema=LLAMA_SCHEMA, anchor="llama")
    config = {
        "qwen_report": {"path": str(args.qwen_report), "sha256": sha256(args.qwen_report), "schema_version": QWEN_SCHEMA},
        "llama_report": {"path": str(args.llama_report), "sha256": sha256(args.llama_report), "schema_version": LLAMA_SCHEMA},
        "admission_budgets": list(QUANTA),
        "prefill_maturity_chunk_tokens": 64,
        "comparison_rule": "within_model_workload_row_only; no cross-model numeric pooling, averaging, min/max, or parameter derivation",
    }
    report = {
        "schema_version": SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "config": config,
        "config_hash": stable_hash(config),
        "execution_classification": "no-model, hash-bound comparison of functional/trace-derived micro-event state summaries; not modeled or measured hardware evidence",
        "anchor_rows": [
            {"model_anchor": "kvzap_qwen3_8b", "source_report_sha256": config["qwen_report"]["sha256"], "continuation_scope": "Qwen A4.3.5 native request-specific decode path", "workload_rows": anchor_rows(qwen)},
            {"model_anchor": "kvzap_llama31_8b_instruct", "source_report_sha256": config["llama_report"]["sha256"], "continuation_scope": "M5.1-conditioned fixed_non_eos_continuation_8_tokens; record-only ULP context retained", "workload_rows": anchor_rows(llama)},
        ],
        "observational_guards": {
            "both_completed_reports_hash_bound": True,
            "each_anchor_retains_three_distinct_workload_rows": True,
            "each_row_retains_q1_q8_q32_and_chunk64_contract": True,
            "llama_fixed_continuation_and_non_strict_ulp_context_retained": True,
            "cross_model_numeric_pooling_or_unified_range_created": False,
            "hardware_parameter_selected": False,
        },
        "architecture_spec_gate": {
            "eligible": False,
            "rtl_authorized": False,
            "reason": "A4.3.7 only compares within-row functional Q sensitivity and deliberately creates no common hardware envelope.",
        },
        "boundaries": [
            "Each direction matrix is descriptive and falsifiable within one model/workload row; a different sign in a later row is evidence of dependence, not grounds to rewrite the source result.",
            "Q is a declared reference admission action count. Logical pending/page summaries are not FIFO occupancy, controller rate, physical pages, HBM traffic, capacity, timing, latency, throughput, energy, area, or hardware acceleration.",
            "Qwen and Llama continuation conditions differ and their numeric values are not pooled, averaged, converted to a common resource range, or used to choose a parameter.",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "a437_cross_anchor_microevent_envelope_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.3.7 completed: {output}")


if __name__ == "__main__":
    main()
