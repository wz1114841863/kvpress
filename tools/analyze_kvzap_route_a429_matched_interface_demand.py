"""A4.2.9 no-model matched-workload split-source interface-demand study."""
from __future__ import annotations

import argparse, gzip, hashlib, json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

A428_SCHEMA = "kvzap-route-a428-matched-horizon-workload-stability-1.0"
A422_SCHEMA = "kvzap-route-a422-scheduler-merge-placement-1.0"
A429_SCHEMA = "kvzap-route-a429-matched-interface-demand-1.0"
SOURCES = ("hot", "pending", "packed")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.2.9 matched-workload modeled split-source interface-demand analysis; no model execution.")
    p.add_argument("--a428-report", type=Path, required=True)
    p.add_argument("--a422-report", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return p.parse_args()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def complete(path: Path, schema: str) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if data.get("schema_version") != schema or data.get("status") != "complete":
        raise ValueError(f"not a completed {schema}: {path}")
    return data


def q(values: list[int], fraction: float) -> int | None:
    return sorted(values)[int((len(values) - 1) * fraction)] if values else None


def read_events(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle]
    if not events:
        raise ValueError("empty A424 logical-event artifact")
    return events


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    fanin, exports, records = Counter(), Counter(), {s: [] for s in SOURCES}
    groups: dict[tuple[int, int], dict[str, Any]] = defaultdict(lambda: {"events": 0, "exports": 0, "records": {s: [] for s in SOURCES}, "pages": [], "tails": []})
    for event in events:
        active = [d for d in event["source_decisions"] if d["outcome"] == "partial"]
        n = len(active); fanin[str(n)] += 1
        group = groups[(int(event["layer"]), int(event["kv_head"]))]
        group["events"] += 1; group["exports"] += n; group["pages"].append(int(event["packed_page_count"])); group["tails"].append(int(event["packed_tail_tokens"]))
        for decision in active:
            source, count = decision["source"], int(decision["record_count"])
            exports[source] += 1; records[source].append(count); group["records"][source].append(count)
    total = len(events)
    rows = [{"layer": layer, "kv_head": head, "event_count": row["events"], "modeled_split_state_exports": row["exports"], "modeled_split_exports_per_event": row["exports"] / row["events"], "record_count_p95_by_source": {s: q(row["records"][s], .95) for s in SOURCES}, "packed_page_witness_p95": q(row["pages"], .95), "packed_page_witness_max": max(row["pages"]), "packed_tail_witness_p95": q(row["tails"], .95)} for (layer, head), row in sorted(groups.items())]
    return {"event_count": total, "exact_fan_in_counts": dict(fanin), "modeled_split_state_exports": {"total": sum(exports.values()), "by_source": dict(exports), "per_event": sum(exports.values()) / total, "additional_reduction_inputs_total": sum((int(n) - 1) * count for n, count in fanin.items()), "co_located_exports": 0}, "partial_record_count_distribution": {s: {"sample_count": len(v), "p50": q(v,.5), "p95": q(v,.95), "max": max(v, default=None)} for s,v in records.items()}, "per_layer_kv_head": rows}


def main() -> None:
    a = parse_args()
    if a.output_dir.exists(): raise FileExistsError(f"output directory already exists: {a.output_dir}")
    a428, a422 = complete(a.a428_report, A428_SCHEMA), complete(a.a422_report, A422_SCHEMA)
    if not all(a428.get("observational_guards", {}).get(k) is True for k in ("shared_actual_policy_decode_calls", "all_workloads_semantics_certified", "all_workloads_a424_event_guards_verified")): raise ValueError("A428 guards insufficient")
    if not all(a422.get("observational_guards", {}).get(k) is True for k in ("co_located_and_split_interfaces_explicit", "no_hardware_parameter_selected", "no_model_execution")): raise ValueError("A422 interface guards insufficient")
    workloads = a428.get("per_workload", {})
    if set(workloads) != {"summarization", "retrieval", "reasoning"}: raise ValueError("A428 must contain exactly three workloads")
    results = {}
    for name, row in workloads.items():
        base = a.a428_report.parent / name / "ordered_events"
        manifest, events = base / "a424_ordered_logical_event_manifest.json", base / "a424_ordered_logical_attention_events.jsonl.gz"
        if digest(manifest) != row["a424_manifest_sha256"] or digest(events) != row["logical_event_sha256"]: raise ValueError(f"A428 hash binding fails for {name}")
        results[name] = {"a424_manifest_sha256": row["a424_manifest_sha256"], "logical_event_sha256": row["logical_event_sha256"], "summary": summarize(read_events(events))}
    config = {"a428_report": str(a.a428_report), "a428_report_sha256": digest(a.a428_report), "a422_report": str(a.a422_report), "a422_report_sha256": digest(a.a422_report)}
    output = {"schema_version": A429_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": config, "config_hash": stable_hash(config), "per_workload": results, "observational_guards": {"a428_matched_horizon_guards_verified": True, "a422_interface_contract_guards_verified": True, "all_a424_hash_bindings_verified": True, "co_located_zero_cross_engine_exports_explicit": True, "split_exports_counted_as_modeled_interface_units": True, "no_hardware_parameter_selected": True}, "boundaries": ["Split state exports and reduction inputs are modeled interface units derived from logical active sources, not bytes, cycles, timestamps, queue occupancy, FIFO depth, latency, throughput, HBM traffic, energy, area, hardware, or RTL evidence.", "A424 records invocation order only; it does not reveal source completion or reduction arrival."]}
    a.output_dir.mkdir(parents=True); path=a.output_dir/"a429_matched_interface_demand_report.json"; path.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n"); print(f"A4.2.9 completed: {path}")

if __name__ == "__main__": main()
