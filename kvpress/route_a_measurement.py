"""A4.1.0 measurement primitives, intentionally independent of any model.

These helpers establish timing, allocator, raw-record, and output-directory
contracts before Qwen or any Route-A measurement is attempted.  They do not
claim that allocator bytes are HBM traffic or that a Python self-check measures
model performance.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

import torch


A41_RAW_SCHEMA = "kvzap-route-a41-raw-repetition-1.0"
A41_HARNESS_SCHEMA = "kvzap-route-a41-harness-1.0"
MEASURED_PATHS = frozenset({"full_kv_bypass", "same_mask_dense_replay", "same_mask_route_a_replay", "online_dense_predictor_control", "harness_self_check"})

T = TypeVar("T")


@dataclass(frozen=True)
class CudaMemorySnapshot:
    """PyTorch allocator counters in bytes, never physical HBM counters."""

    allocated_bytes: int
    reserved_bytes: int
    peak_allocated_bytes: int
    peak_reserved_bytes: int


@dataclass(frozen=True)
class TimingSample:
    """Synchronized host and CUDA-event elapsed time in milliseconds."""

    wall_ms: float
    cuda_event_ms: float


def require_cuda_device(device: str | torch.device) -> torch.device:
    """Reject CPU and unavailable CUDA before a timing or allocator call."""
    resolved = torch.device(device)
    if resolved.type != "cuda":
        raise ValueError("A4.1 timing requires an explicit CUDA device; CPU timing is rejected")
    if not torch.cuda.is_available():
        raise RuntimeError("A4.1 timing requires CUDA, but torch.cuda.is_available() is false")
    return resolved


def cuda_memory_snapshot(device: str | torch.device) -> CudaMemorySnapshot:
    """Read allocator counters after synchronization, with byte units explicit."""
    resolved = require_cuda_device(device)
    torch.cuda.synchronize(resolved)
    return CudaMemorySnapshot(
        allocated_bytes=int(torch.cuda.memory_allocated(resolved)),
        reserved_bytes=int(torch.cuda.memory_reserved(resolved)),
        peak_allocated_bytes=int(torch.cuda.max_memory_allocated(resolved)),
        peak_reserved_bytes=int(torch.cuda.max_memory_reserved(resolved)),
    )


def reset_cuda_peak_memory(device: str | torch.device) -> CudaMemorySnapshot:
    """Synchronize, reset allocator peaks, then return the reset baseline."""
    resolved = require_cuda_device(device)
    torch.cuda.synchronize(resolved)
    torch.cuda.reset_peak_memory_stats(resolved)
    return cuda_memory_snapshot(resolved)


def time_cuda_region(operation: Callable[[], T], *, device: str | torch.device) -> tuple[T, TimingSample]:
    """Time one region with host wall time and CUDA events after synchronization."""
    resolved = require_cuda_device(device)
    torch.cuda.synchronize(resolved)
    start_event = torch.cuda.Event(enable_timing=True)
    end_event = torch.cuda.Event(enable_timing=True)
    wall_start = time.perf_counter_ns()
    start_event.record()
    result = operation()
    end_event.record()
    torch.cuda.synchronize(resolved)
    wall_ms = (time.perf_counter_ns() - wall_start) / 1_000_000.0
    cuda_event_ms = float(start_event.elapsed_time(end_event))
    if not math.isfinite(wall_ms) or not math.isfinite(cuda_event_ms) or wall_ms < 0 or cuda_event_ms < 0:
        raise AssertionError("CUDA timing produced a non-finite or negative duration")
    return result, TimingSample(wall_ms=wall_ms, cuda_event_ms=cuda_event_ms)


def _require_finite_number(value: Any, name: str, *, minimum: float | None = None) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return number


def validate_raw_repetition(record: dict[str, Any]) -> None:
    """Validate one raw record before it can contribute to a distribution."""
    required = {
        "schema_version", "path", "component", "repetition", "execution_order", "warmup",
        "wall_ms", "cuda_event_ms", "memory_before", "memory_after",
    }
    missing = required - set(record)
    if missing:
        raise ValueError(f"raw repetition is missing fields: {sorted(missing)}")
    if record["schema_version"] != A41_RAW_SCHEMA:
        raise ValueError("unexpected raw repetition schema")
    if record["path"] not in MEASURED_PATHS:
        raise ValueError("unknown measured path")
    if not isinstance(record["component"], str) or not record["component"].strip():
        raise ValueError("component must be a non-empty string")
    for name in ("repetition", "execution_order"):
        if not isinstance(record[name], int) or isinstance(record[name], bool) or record[name] < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if not isinstance(record["warmup"], bool):
        raise ValueError("warmup must be boolean")
    _require_finite_number(record["wall_ms"], "wall_ms", minimum=0.0)
    _require_finite_number(record["cuda_event_ms"], "cuda_event_ms", minimum=0.0)
    for snapshot_name in ("memory_before", "memory_after"):
        snapshot = record[snapshot_name]
        if not isinstance(snapshot, dict):
            raise ValueError(f"{snapshot_name} must be a byte-valued allocator snapshot")
        expected = set(CudaMemorySnapshot.__dataclass_fields__)
        if set(snapshot) != expected:
            raise ValueError(f"{snapshot_name} has unexpected allocator fields")
        for field, value in snapshot.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{snapshot_name}.{field} must be a non-negative integer byte count")


def summarize_values(values: list[float]) -> dict[str, float | int]:
    """Return distribution statistics without dropping raw measurements."""
    if not values:
        raise ValueError("cannot summarize an empty measurement series")
    checked = [_require_finite_number(value, "measurement", minimum=0.0) for value in values]
    ordered = sorted(checked)

    def percentile(percent: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        rank = (len(ordered) - 1) * percent / 100.0
        low, high = math.floor(rank), math.ceil(rank)
        return ordered[low] if low == high else ordered[low] + (ordered[high] - ordered[low]) * (rank - low)

    return {
        "count": len(ordered),
        "min": ordered[0],
        "median": percentile(50.0),
        "mean": statistics.fmean(ordered),
        "stddev": statistics.stdev(ordered) if len(ordered) > 1 else 0.0,
        "p90": percentile(90.0),
        "p95": percentile(95.0),
        "max": ordered[-1],
    }


def summarize_reported_repetitions(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize only non-warmup samples, grouped by path and component."""
    for record in records:
        validate_raw_repetition(record)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        if not record["warmup"]:
            groups.setdefault((record["path"], record["component"]), []).append(record)
    if not groups:
        raise ValueError("no reported repetitions are available")
    return {
        "schema_version": "kvzap-route-a41-summary-1.0",
        "groups": [
            {
                "path": path,
                "component": component,
                "reported_repetitions": len(rows),
                "wall_ms": summarize_values([float(row["wall_ms"]) for row in rows]),
                "cuda_event_ms": summarize_values([float(row["cuda_event_ms"]) for row in rows]),
                "peak_allocated_bytes": summarize_values([float(row["memory_after"]["peak_allocated_bytes"]) for row in rows]),
                "peak_reserved_bytes": summarize_values([float(row["memory_after"]["peak_reserved_bytes"]) for row in rows]),
            }
            for (path, component), rows in sorted(groups.items())
        ],
    }


def initialize_output_directory(output_dir: Path, *, config: dict[str, Any], git_commit: str) -> Path:
    """Create a fresh A4.1 directory and immutable-before-run start record."""
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)
    path = output_dir / "a41_harness_started.json"
    payload = {
        "schema_version": A41_HARNESS_SCHEMA,
        "status": "started",
        "git_commit": git_commit,
        "config": config,
        "boundaries": [
            "This is A4.1.0 harness infrastructure, not a model measurement.",
            "Allocator counters are PyTorch allocator bytes, not HBM traffic.",
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_raw_repetitions(output_dir: Path, records: list[dict[str, Any]]) -> Path:
    """Write validated raw records once; never append or overwrite a prior file."""
    for record in records:
        validate_raw_repetition(record)
    path = output_dir / "a41_raw_repetitions.jsonl"
    if path.exists():
        raise FileExistsError(f"raw repetitions already exist: {path}")
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")
    return path


def write_completed_manifest(output_dir: Path, *, config: dict[str, Any], git_commit: str, summary: dict[str, Any], status: str = "complete") -> Path:
    """Write the after-run record separately from the immutable start record."""
    if status not in {"complete", "dry_run"}:
        raise ValueError("invalid harness completion status")
    path = output_dir / "a41_harness_manifest.json"
    if path.exists():
        raise FileExistsError(f"harness manifest already exists: {path}")
    payload = {
        "schema_version": A41_HARNESS_SCHEMA,
        "status": status,
        "git_commit": git_commit,
        "config": config,
        "summary": summary,
        "boundaries": [
            "No Qwen or KVzap model was loaded by this harness record.",
            "Self-check timing validates instrumentation only and is not A4.1 model performance evidence.",
            "Allocator bytes are not HBM traffic, throughput, energy, area, or RTL evidence.",
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def raw_record(*, path: str, component: str, repetition: int, execution_order: int, warmup: bool, timing: TimingSample, memory_before: CudaMemorySnapshot, memory_after: CudaMemorySnapshot) -> dict[str, Any]:
    record = {
        "schema_version": A41_RAW_SCHEMA,
        "path": path,
        "component": component,
        "repetition": repetition,
        "execution_order": execution_order,
        "warmup": warmup,
        "wall_ms": timing.wall_ms,
        "cuda_event_ms": timing.cuda_event_ms,
        "memory_before": asdict(memory_before),
        "memory_after": asdict(memory_after),
    }
    validate_raw_repetition(record)
    return record


class CudaComponentRecorder:
    """Record synchronized component samples for one reset backend instance.

    Each component deliberately synchronizes and resets allocator peaks. This
    supports component attribution but is unsuitable for end-to-end timing.
    """

    def __init__(self, *, device: str | torch.device, path: str, repetition: int, execution_order: int, warmup: bool, metadata: dict[str, Any] | None = None) -> None:
        self.device = require_cuda_device(device)
        if path not in MEASURED_PATHS - {"harness_self_check"}:
            raise ValueError("component recorder path must be a declared A4.1 measured path")
        self.path, self.repetition, self.execution_order, self.warmup = path, repetition, execution_order, warmup
        self.metadata = {} if metadata is None else dict(metadata)
        self.records: list[dict[str, Any]] = []

    def measure(self, component: str, operation: Callable[[], T]) -> T:
        before = reset_cuda_peak_memory(self.device)
        result, timing = time_cuda_region(operation, device=self.device)
        after = cuda_memory_snapshot(self.device)
        record = raw_record(path=self.path, component=component, repetition=self.repetition, execution_order=self.execution_order, warmup=self.warmup, timing=timing, memory_before=before, memory_after=after)
        record.update(self.metadata)
        self.records.append(record)
        return result
