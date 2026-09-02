"""Validate A4.1.0 timing and allocator instrumentation without loading a model."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import torch

from kvpress.route_a_measurement import (
    cuda_memory_snapshot,
    initialize_output_directory,
    raw_record,
    reset_cuda_peak_memory,
    require_cuda_device,
    summarize_reported_repetitions,
    time_cuda_region,
    write_completed_manifest,
    write_raw_repetitions,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A4.1.0 no-model CUDA timing/allocator harness; not a KVzap performance experiment.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    parser.add_argument("--device", default="cuda", help="CUDA device for --self-check; CPU is rejected.")
    parser.add_argument("--warmup-repetitions", type=int, default=3)
    parser.add_argument("--measured-repetitions", type=int, default=10)
    parser.add_argument("--tensor-elements", type=int, default=1 << 20, help="Element count for the no-model CUDA add self-check.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Validate configuration and output schema without touching CUDA.")
    mode.add_argument("--self-check", action="store_true", help="Run synchronized CUDA tensor-add instrumentation only; no model is loaded.")
    return parser.parse_args()


def git_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], check=False, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main() -> None:
    args = parse_args()
    if min(args.warmup_repetitions, args.measured_repetitions, args.tensor_elements) <= 0:
        raise ValueError("warmup repetitions, measured repetitions, and tensor elements must be positive")
    config = {
        "mode": "self_check" if args.self_check else "dry_run",
        "device": args.device,
        "warmup_repetitions": args.warmup_repetitions,
        "measured_repetitions": args.measured_repetitions,
        "tensor_elements": args.tensor_elements,
    }
    initialize_output_directory(args.output_dir, config=config, git_commit=git_commit())
    if args.dry_run:
        path = write_completed_manifest(args.output_dir, config=config, git_commit=git_commit(), summary={"raw_repetitions": 0, "reason": "dry run; CUDA was not touched"}, status="dry_run")
        print(f"A4.1.0 dry-run harness completed: {path}")
        return

    device = require_cuda_device(args.device)
    source = torch.ones(args.tensor_elements, device=device)
    destination = torch.empty_like(source)
    records = []
    total = args.warmup_repetitions + args.measured_repetitions
    for order in range(total):
        warmup = order < args.warmup_repetitions
        before = reset_cuda_peak_memory(device)
        _result, timing = time_cuda_region(lambda: torch.add(source, source, out=destination), device=device)
        after = cuda_memory_snapshot(device)
        records.append(raw_record(path="harness_self_check", component="cuda_tensor_add", repetition=order if warmup else order - args.warmup_repetitions, execution_order=order, warmup=warmup, timing=timing, memory_before=before, memory_after=after))
    raw_path = write_raw_repetitions(args.output_dir, records)
    summary = summarize_reported_repetitions(records)
    summary["raw_repetitions"] = len(records)
    summary["raw_path"] = raw_path.name
    summary["device_name"] = torch.cuda.get_device_name(device)
    path = write_completed_manifest(args.output_dir, config=config, git_commit=git_commit(), summary=summary)
    print(f"A4.1.0 CUDA self-check completed: {path}")


if __name__ == "__main__":
    main()
