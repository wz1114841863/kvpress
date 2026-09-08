"""A4.1.7.16 provenance-bound long-horizon three-path profiler wrapper."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash

A4167_SCHEMA = "kvzap-route-a4167-long-horizon-three-path-profiler-1.0"
A4166_SCHEMA = "kvzap-route-a4166-long-horizon-three-path-measurement-1.0"
A4163_SCHEMA = "kvzap-route-a4163-cross-workload-three-path-profiler-1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.7.16 long-horizon three-path profiler attribution; diagnostic only, not a timing or hardware benchmark.")
    parser.add_argument("--long-horizon-three-path-measurement", type=Path, required=True)
    parser.add_argument("--warmup-repetitions", type=int, default=1)
    parser.add_argument("--top-operators", type=int, default=30)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def load_completed_a4166(path: Path) -> tuple[dict, Path, dict]:
    if not path.is_file():
        raise FileNotFoundError(f"A4166 long-horizon measurement manifest is missing: {path}")
    measurement = json.loads(path.read_text(encoding="utf-8"))
    if measurement.get("schema_version") != A4166_SCHEMA or measurement.get("status") != "complete":
        raise ValueError("not a completed A4166 long-horizon three-path measurement")
    required = ("a4165_long_horizon_semantics_verified", "a4162_child_complete", "child_source_sha_matches_a4165")
    if any(measurement.get("observational_guards", {}).get(name) is not True for name in required):
        raise ValueError("A4166 prerequisite guards missing")
    pipeline = Path(measurement["config"]["long_horizon_semantic_pipeline"])
    if not pipeline.is_absolute():
        pipeline = (Path.cwd() / pipeline).resolve()
    if not pipeline.is_file():
        raise FileNotFoundError(f"A4165 semantic pipeline bound by A4166 is missing: {pipeline}")
    semantic = json.loads(pipeline.read_text(encoding="utf-8"))
    if semantic.get("schema_version") != "kvzap-route-a4165-long-horizon-semantic-pipeline-1.0" or semantic.get("status") != "complete":
        raise ValueError("A4166 does not bind a completed A4165 semantic pipeline")
    config = semantic.get("config", {})
    if config.get("max_new_tokens", 0) < 32 or config.get("admission_budget") != 512 or config.get("target_layers") != ["all"] or config.get("target_kv_head") != "all":
        raise ValueError("A4165 configuration is not the required all-layer/budget-512 long horizon")
    source_sha = semantic.get("summary", {}).get("replay_event_file_sha256")
    if measurement.get("config", {}).get("replay_event_file_sha256") != source_sha:
        raise ValueError("A4166 parent source SHA-256 differs from its A4165 semantic pipeline")
    return measurement, pipeline, semantic


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    if args.warmup_repetitions <= 0 or args.top_operators <= 0:
        raise ValueError("warm-up repetitions and top operators must be positive")
    measurement, pipeline_path, semantic = load_completed_a4166(args.long_horizon_three_path_measurement)
    root = pipeline_path.parent
    source = root / "source"
    execution = root / "execution_semantic" / "a4151_guard_elided_execution_manifest.json"
    elision = root / "elision_semantic" / "a4154_empty_source_elision_manifest.json"
    child_measurement = args.long_horizon_three_path_measurement.parent / measurement["a4162_child_manifest"]
    for path in (source, execution, elision, child_measurement):
        if not path.exists():
            raise FileNotFoundError(f"A4167 prerequisite is missing: {path}")
    args.output_dir.mkdir(parents=True)
    child = args.output_dir / "three_path_profiler"
    config = semantic["config"]
    command = [
        sys.executable, "tools/run_kvzap_route_a4163_cross_workload_three_path_profiler.py",
        "--preset", str(config["preset"]), "--context-repetitions", str(config["context_repetitions"]),
        "--max-new-tokens", str(config["max_new_tokens"]), "--target-layers", "all", "--target-kv-head", "all",
        "--admission-budget", "512", "--require-cross-workload-source-coverage",
        "--warmup-repetitions", str(args.warmup_repetitions), "--top-operators", str(args.top_operators),
        "--device", args.device, "--replay-source-dir", str(source),
        "--route-a-execution-certification", str(execution), "--empty-source-elision-certification", str(elision),
        "--three-path-measurement-manifest", str(child_measurement), "--output-dir", str(child),
    ]
    environment = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
    print("Running A4163 child profiler at long horizon with the already-cached model artifacts...", flush=True)
    subprocess.run(command, check=True, env=environment)
    child_manifest = child / "a4163_cross_workload_three_path_profiler_manifest.json"
    result = json.loads(child_manifest.read_text(encoding="utf-8"))
    source_sha = semantic["summary"]["replay_event_file_sha256"]
    if result.get("schema_version") != A4163_SCHEMA or result.get("status") != "complete":
        raise AssertionError("A4163 child profiler did not complete")
    if result.get("replay_source", {}).get("event_file_sha256") != source_sha:
        raise AssertionError("A4163 child profiler source SHA-256 differs from A4165")
    required = ("profiler_token_digests_match_certificates", "route_a_source_partial_or_skip_accounting_matches_merge", "phase_rows_coalesced")
    if any(result.get("observational_guards", {}).get(name) is not True for name in required):
        raise AssertionError("A4163 child profiler semantic/accounting guards missing")
    parent_config = {"long_horizon_three_path_measurement": str(args.long_horizon_three_path_measurement), "warmup_repetitions": args.warmup_repetitions, "top_operators": args.top_operators, "device": args.device, "replay_event_file_sha256": source_sha}
    manifest = {
        "schema_version": A4167_SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "config": parent_config, "config_hash": stable_hash(parent_config),
        "a4166_measurement_sha256": hashlib.sha256(args.long_horizon_three_path_measurement.read_bytes()).hexdigest(), "a4163_child_manifest": "three_path_profiler/a4163_cross_workload_three_path_profiler_manifest.json",
        "observational_guards": {"a4166_long_horizon_measurement_verified": True, "a4163_child_complete": True, "child_source_sha_matches_a4165_and_a4166": True, "child_profiler_token_digests_match_certificates": True, "child_route_a_source_partial_or_skip_accounting_matches_merge": True, "child_phase_rows_coalesced": True, "profiler_is_separate_from_repeated_timing": True},
        "boundaries": ["This is one separate long-horizon Python-reference profiler capture per path, not another timing distribution.", "Nested/coalesced profiler rows are structural diagnostics, not latency, HBM traffic, throughput, energy, hardware acceleration, or RTL evidence."],
    }
    output = args.output_dir / "a4167_long_horizon_three_path_profiler_manifest.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.1.7.16 long-horizon three-path profiler completed: {output}")


if __name__ == "__main__":
    main()
