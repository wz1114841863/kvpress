# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run a predictor-only pilot as one fresh exporter process per JSONL request."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_trace import validate_trace


RUN_SCHEMA = "kvzap-predictor-pilot-run-1.0"
DEFAULT_MODEL_REVISION = "b968826d9c46dd6066d109eabc6255188de91218"
DEFAULT_PREDICTOR_REVISION = "bd5c5917846617da4311539859c137a262a6348b"
REQUIRED_TRACE_FILES = {
    "manifest.json",
    "score_mask.npz",
    "request_summary.csv",
    "layer_head_summary.csv",
    "gate_a_evidence.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run each selected JSONL request through the frozen predictor-only exporter in a fresh process. "
            "The runner supports deterministic shards, per-request logs, strict resume, and failure recording."
        )
    )
    parser.add_argument("input_jsonl", type=Path, help="Prepared request JSONL.")
    parser.add_argument(
        "--input-manifest",
        type=Path,
        help="Preparation manifest. Defaults to INPUT_JSONL with suffix .manifest.json.",
    )
    parser.add_argument(
        "--allow-unmanifested-input",
        action="store_true",
        help="Allow a custom JSONL without a preparation manifest (not recommended for frozen experiments).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help=(
            "Root for request traces, logs, and pilot_run_manifest.json. Defaults to "
            "traces/pilots/<input-stem>_shard<index>."
        ),
    )
    parser.add_argument(
        "--gate-a-evidence",
        type=Path,
        default=Path("traces/hardware_predictor_gate_a_01"),
        help="Frozen Gate-A evidence passed to every exporter process.",
    )
    parser.add_argument(
        "--exporter",
        type=Path,
        default=Path("tools/export_kvzap_predictor_trace.py"),
        help="Frozen single-request predictor-only exporter.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used for child processes.")
    parser.add_argument("--threshold", type=float, default=-4.0)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--predictor-revision", default=DEFAULT_PREDICTOR_REVISION)
    parser.add_argument("--num-shards", type=int, default=1, help="Total deterministic request shards.")
    parser.add_argument("--shard-index", type=int, default=0, help="Shard handled by this invocation.")
    parser.add_argument(
        "--max-requests",
        type=int,
        help="Optional cap after sharding, useful for a one-request remote validation.",
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip only complete traces that pass offline validation (default: true).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue with later requests after recording a failed child process.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=0,
        help="Per-request timeout; 0 disables the timeout.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print commands without writing.")
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def default_output_root(input_jsonl: Path, shard_index: int) -> Path:
    return Path("traces/pilots") / f"{input_jsonl.stem}_shard{shard_index}"


def get_git_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return "unknown"
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        check=False,
        capture_output=True,
        text=True,
    )
    dirty = status.returncode == 0 and bool(status.stdout.strip())
    return f"{result.stdout.strip()}+dirty" if dirty else result.stdout.strip()


def load_requests(path: Path) -> list[dict[str, Any]]:
    requests = []
    seen_ids = set()
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            request = json.loads(line)
            missing = {"request_id", "context", "question"} - set(request)
            if missing:
                raise ValueError(f"{path}:{line_number} missing fields: {sorted(missing)}")
            request_id = str(request["request_id"])
            if request_id in seen_ids:
                raise ValueError(f"Duplicate request_id {request_id!r} in {path}")
            seen_ids.add(request_id)
            request["request_id"] = request_id
            request.setdefault("dataset", "custom")
            request.setdefault("subset", "custom")
            request["_input_line"] = line_number
            requests.append(request)
    if not requests:
        raise ValueError(f"No requests found in {path}")
    return requests


def verify_input_manifest(jsonl_path: Path, manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Input manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_hash = manifest.get("output_jsonl_sha256")
    actual_hash = file_sha256(jsonl_path)
    if expected_hash != actual_hash:
        raise ValueError(f"Input JSONL hash differs from preparation manifest: {actual_hash} != {expected_hash}")
    return manifest


def request_shard(request_id: str, num_shards: int) -> int:
    digest = hashlib.sha256(request_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big") % num_shards


def safe_trace_dir_name(request_id: str, input_line: int) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", request_id).strip("._-") or "request"
    digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:10]
    return f"{input_line:05d}_{slug[:72]}_{digest}"


def trace_validation_error(trace_dir: Path, request_id: str) -> str | None:
    missing = sorted(name for name in REQUIRED_TRACE_FILES if not (trace_dir / name).is_file())
    if missing:
        return f"missing files: {missing}"
    try:
        trace = validate_trace(trace_dir)
    except Exception as error:  # noqa: BLE001 - the exact validation failure is persisted for resume diagnostics.
        return f"offline validation failed: {type(error).__name__}: {error}"
    if trace["request"]["request_id"] != request_id:
        return f"request ID mismatch: {trace['request']['request_id']!r} != {request_id!r}"
    if not trace["predictor_only"]:
        return "trace is not predictor-only"
    return None


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def public_request_metadata(request: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in request.items() if key not in {"context", "question"}}


def build_child_command(args: argparse.Namespace, request_id: str, output_dir: Path) -> list[str]:
    return [
        args.python,
        str(args.exporter),
        "--input-jsonl",
        str(args.input_jsonl),
        "--request-id",
        request_id,
        "--gate-a-evidence",
        str(args.gate_a_evidence),
        "--model-revision",
        args.model_revision,
        "--predictor-revision",
        args.predictor_revision,
        "--threshold",
        str(args.threshold),
        "--window-size",
        str(args.window_size),
        "--seed",
        str(args.seed),
        "--output-dir",
        str(output_dir),
    ]


def main() -> None:
    args = parse_args()
    if args.num_shards <= 0 or not 0 <= args.shard_index < args.num_shards:
        raise ValueError("Require --num-shards > 0 and 0 <= --shard-index < --num-shards")
    if args.max_requests is not None and args.max_requests <= 0:
        raise ValueError("--max-requests must be positive")
    if args.output_root is None:
        args.output_root = default_output_root(args.input_jsonl, args.shard_index)
    if args.timeout_seconds < 0:
        raise ValueError("--timeout-seconds must be non-negative")
    if not args.input_jsonl.is_file():
        raise FileNotFoundError(f"Input JSONL not found: {args.input_jsonl}")
    if not args.exporter.is_file():
        raise FileNotFoundError(f"Exporter not found: {args.exporter}")
    if not args.gate_a_evidence.is_dir():
        raise FileNotFoundError(f"Gate-A evidence directory not found: {args.gate_a_evidence}")

    input_manifest_path = args.input_manifest or args.input_jsonl.with_suffix(".manifest.json")
    if args.allow_unmanifested_input:
        input_manifest = None
    else:
        input_manifest = verify_input_manifest(args.input_jsonl, input_manifest_path)
    requests = load_requests(args.input_jsonl)
    selected = [
        request
        for request in requests
        if request_shard(request["request_id"], args.num_shards) == args.shard_index
    ]
    if args.max_requests is not None:
        selected = selected[: args.max_requests]
    if not selected:
        raise ValueError(f"Shard {args.shard_index}/{args.num_shards} selected no requests")

    run_config = {
        "input_jsonl": str(args.input_jsonl),
        "input_jsonl_sha256": file_sha256(args.input_jsonl),
        "input_manifest": None if input_manifest is None else str(input_manifest_path),
        "input_manifest_sha256": None if input_manifest is None else file_sha256(input_manifest_path),
        "exporter": str(args.exporter),
        "exporter_sha256": file_sha256(args.exporter),
        "runner_sha256": file_sha256(Path(__file__)),
        "gate_a_evidence": str(args.gate_a_evidence),
        "threshold": args.threshold,
        "window_size": args.window_size,
        "seed": args.seed,
        "model_revision": args.model_revision,
        "predictor_revision": args.predictor_revision,
        "num_shards": args.num_shards,
        "shard_index": args.shard_index,
    }
    run_config_hash = stable_hash(run_config)
    manifest_path = args.output_root / "pilot_run_manifest.json"
    if args.dry_run:
        for request in selected:
            trace_dir = args.output_root / "requests" / safe_trace_dir_name(
                request["request_id"], request["_input_line"]
            )
            print(shlex.join(build_child_command(args, request["request_id"], trace_dir)))
        print(f"Dry run: {len(selected)} request(s), config_hash={run_config_hash}")
        return

    args.output_root.mkdir(parents=True, exist_ok=True)
    logs_dir = args.output_root / "logs"
    requests_dir = args.output_root / "requests"
    logs_dir.mkdir(exist_ok=True)
    requests_dir.mkdir(exist_ok=True)
    if manifest_path.exists():
        run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if run_manifest.get("run_config_hash") != run_config_hash:
            raise ValueError("Existing pilot_run_manifest.json has a different run configuration")
    else:
        run_manifest = {
            "schema_version": RUN_SCHEMA,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "runner_git_commit": get_git_commit(),
            "run_config_hash": run_config_hash,
            "run_config": run_config,
            "preparation_manifest_summary": None
            if input_manifest is None
            else {
                "schema_version": input_manifest.get("schema_version"),
                "dataset_repo": input_manifest.get("dataset_repo"),
                "dataset_revision_resolved": input_manifest.get("dataset_revision_resolved"),
                "model_tokenizer": input_manifest.get("model_tokenizer"),
                "tokenizer_revision": input_manifest.get("tokenizer_revision"),
            },
            "selected_request_count": len(selected),
            "requests": {},
        }
        atomic_write_json(manifest_path, run_manifest)

    run_manifest["selected_request_count"] = len(selected)
    atomic_write_json(manifest_path, run_manifest)

    failures = 0
    for position, request in enumerate(selected, start=1):
        request_id = request["request_id"]
        directory_name = safe_trace_dir_name(request_id, request["_input_line"])
        trace_dir = requests_dir / directory_name
        log_path = logs_dir / f"{directory_name}.log"
        existing_error = trace_validation_error(trace_dir, request_id) if trace_dir.exists() else "not present"
        if trace_dir.exists() and existing_error is None and args.resume:
            print(f"[{position}/{len(selected)}] SKIP complete {request_id}")
            run_manifest["requests"][request_id] = {
                "status": "complete",
                "resume_skipped": True,
                "trace_dir": str(trace_dir),
                "log": str(log_path),
                "source": public_request_metadata(request),
            }
            atomic_write_json(manifest_path, run_manifest)
            continue
        if trace_dir.exists():
            raise FileExistsError(
                f"Existing trace directory is not resumable for {request_id}: {trace_dir}: {existing_error}. "
                "Move it aside before retrying; the runner never overwrites traces."
            )

        command = build_child_command(args, request_id, trace_dir)
        print(f"[{position}/{len(selected)}] RUN {request_id}")
        print(f"  {shlex.join(command)}")
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            with log_path.open("w", encoding="utf-8") as log_stream:
                completed = subprocess.run(
                    command,
                    stdout=log_stream,
                    stderr=subprocess.STDOUT,
                    check=False,
                    text=True,
                    timeout=args.timeout_seconds or None,
                )
            return_code = completed.returncode
            failure_reason = None if return_code == 0 else f"child return code {return_code}"
        except subprocess.TimeoutExpired:
            return_code = None
            failure_reason = f"timeout after {args.timeout_seconds} seconds"

        validation_error = trace_validation_error(trace_dir, request_id) if trace_dir.exists() else "no trace directory"
        if failure_reason is None and validation_error is not None:
            failure_reason = validation_error
        status = "complete" if failure_reason is None else "failed"
        run_manifest["requests"][request_id] = {
            "status": status,
            "resume_skipped": False,
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "return_code": return_code,
            "failure_reason": failure_reason,
            "trace_dir": str(trace_dir),
            "log": str(log_path),
            "source": public_request_metadata(request),
        }
        atomic_write_json(manifest_path, run_manifest)
        if failure_reason is not None:
            failures += 1
            print(f"  FAILED: {failure_reason}; log={log_path}")
            if not args.continue_on_error:
                raise SystemExit(2)
        else:
            print(f"  COMPLETE: {trace_dir}")

    completed_count = sum(row["status"] == "complete" for row in run_manifest["requests"].values())
    print(f"Pilot shard finished: complete={completed_count}, failures={failures}, manifest={manifest_path}")
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
