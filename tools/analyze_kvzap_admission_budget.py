"""Summarize A3.5c budgeted-admission burst and backlog behavior offline."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_trace import get_git_commit
from tools.simulate_kvzap_route_a3_traffic import sha256
from tools.validate_kvzap_admission_shadow import validate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze one validated A3.5c budgeted-admission shadow directory without loading a model.")
    parser.add_argument("shadow_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory only; existing directories are never overwritten.")
    return parser.parse_args()


def percentile(values: list[int], fraction: float) -> int:
    values = sorted(values)
    return values[min(len(values) - 1, math.ceil(len(values) * fraction) - 1)] if values else 0


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    validate(args.shadow_dir)
    manifest = json.loads((args.shadow_dir / "admission_shadow_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a35-admission-shadow-1.3":
        raise ValueError("Budget analysis requires A3.5c schema 1.3 output")
    rows = list(csv.DictReader((args.shadow_dir / "admission_shadow_v2_tasks.csv").open()))
    packed = [int(row["packed_admitted_tokens"]) for row in rows if int(row["packed_admitted_tokens"])]
    pending = [int(row["pending_tokens_after"]) for row in rows]
    summary: dict[str, Any] = {
        "schema_version": "kvzap-route-a35c-budget-analysis-1.0",
        "git_commit": get_git_commit(),
        "source_dir": str(args.shadow_dir),
        "source_manifest_sha256": sha256(args.shadow_dir / "admission_shadow_manifest.json"),
        "source_tasks_sha256": sha256(args.shadow_dir / "admission_shadow_v2_tasks.csv"),
        "admission_flush_token_budget": manifest["admission_flush_token_budget"],
        "deferred_admission_decode_steps": manifest["deferred_admission_decode_steps"],
        "submission_mode": manifest["submission_mode"],
        "task_rows": len(rows),
        "nonempty_pack_batches": len(packed),
        "packed_tokens_total": sum(packed),
        "packed_tokens_p50": percentile(packed, .50),
        "packed_tokens_p95": percentile(packed, .95),
        "packed_tokens_p99": percentile(packed, .99),
        "packed_tokens_max": max(packed, default=0),
        "packed_bytes_p99": percentile(packed, .99) * int(manifest["config"]["kv_bytes_per_layer_head_token"]),
        "max_pending_tokens_per_layer": max(pending, default=0),
        "pending_tokens_at_end": int(manifest["shadow_summary"]["pending_tokens_at_end"]),
        "queue_drained_by_end": int(manifest["shadow_summary"]["pending_tokens_at_end"]) == 0,
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "admission_budget_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A3.5c budget analysis: p99={summary['packed_tokens_p99']} tokens, max_pending={summary['max_pending_tokens_per_layer']}, pending_end={summary['pending_tokens_at_end']}")


if __name__ == "__main__":
    main()
