# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Small, explicit KVzap trace recorder for correctness-first experiments."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch


SCHEMA_VERSION = "1.0"
TENSOR_LAYOUT = "L,H,T"


class KVzapTraceRecorder:
    """Collect DMS/KVzap score and mask events for one batch-size-one request.

    The recorder deliberately performs device-to-CPU copies. It is intended for
    trace collection, not latency measurement.
    """

    def __init__(self, request_id: str, near_threshold_epsilon: float = 0.25):
        if near_threshold_epsilon < 0:
            raise ValueError("near_threshold_epsilon must be non-negative")
        self.request_id = request_id
        self.near_threshold_epsilon = near_threshold_epsilon
        self.events: list[dict[str, Any]] = []
        self._layer_call_counts: dict[int, int] = {}
        self._cumulative_drops: dict[tuple[int, int], int] = {}

    def __call__(
        self,
        *,
        layer_idx: int,
        prefilling: bool,
        cache_len: int,
        q_len: int,
        score_start: int,
        scores: torch.Tensor,
        predicted_drop_mask: torch.Tensor,
        threshold: float,
        matured_start: int | None,
        matured_scores: torch.Tensor | None,
        matured_drop_mask: torch.Tensor | None,
        cumulative_drop_mask: torch.Tensor,
        score_buffer_length: int,
        cumulative_masked_tokens: int,
        compression_ratio: float,
    ) -> None:
        if scores.ndim != 3 or scores.shape[0] != 1:
            raise ValueError(f"Trace supports scores shaped [1,H,T], got {tuple(scores.shape)}")
        if scores.shape[-1] != q_len:
            raise ValueError(f"score length {scores.shape[-1]} does not match q_len {q_len}")
        if predicted_drop_mask.shape != scores.shape:
            raise ValueError("predicted_drop_mask and scores must have matching [1,H,T] shapes")

        scores_cpu = scores.detach().to(dtype=torch.float32, device="cpu").numpy()[0]
        predicted_drop = predicted_drop_mask.detach().to(device="cpu").numpy()[0].astype(np.bool_, copy=False)
        if matured_drop_mask is None:
            if matured_scores is not None or matured_start is not None:
                raise ValueError("Matured trace fields must either all be set or all be None")
            matured_drop = np.zeros((scores_cpu.shape[0], 0), dtype=np.bool_)
        else:
            if matured_scores is None or matured_start is None:
                raise ValueError("Matured trace fields must either all be set or all be None")
            if matured_drop_mask.shape != matured_scores.shape or matured_drop_mask.shape[0] != 1:
                raise ValueError("matured_scores and matured_drop_mask must have matching [1,H,T] shapes")
            matured_drop = matured_drop_mask.detach().to(device="cpu").numpy()[0].astype(np.bool_, copy=False)

        if cumulative_drop_mask.ndim != 3 or cumulative_drop_mask.shape[0] != 1:
            raise ValueError(
                f"cumulative_drop_mask must be shaped [1,H,T], got {tuple(cumulative_drop_mask.shape)}"
            )
        if cumulative_drop_mask.shape[1] != scores_cpu.shape[0] or cumulative_drop_mask.shape[2] != cache_len:
            raise ValueError(
                f"cumulative_drop_mask shape {tuple(cumulative_drop_mask.shape)} is incompatible with "
                f"scores heads={scores_cpu.shape[0]} and cache_len={cache_len}"
            )
        cumulative_drop = (
            cumulative_drop_mask.detach().to(device="cpu").numpy()[0].astype(np.bool_, copy=True)
        )

        step = self._layer_call_counts.get(layer_idx, 0)
        self._layer_call_counts[layer_idx] = step + 1
        inferred_per_head_cumulative = []
        for head_idx in range(scores_cpu.shape[0]):
            key = (layer_idx, head_idx)
            self._cumulative_drops[key] = self._cumulative_drops.get(key, 0) + int(matured_drop[head_idx].sum())
            inferred_per_head_cumulative.append(self._cumulative_drops[key])
        per_head_cumulative = cumulative_drop.sum(axis=-1).astype(np.int64).tolist()
        inferred_total = sum(inferred_per_head_cumulative)
        exact_total = sum(per_head_cumulative)
        if exact_total != cumulative_masked_tokens:
            raise AssertionError(
                f"Canonical DMS mask counted {exact_total} drops, but DMS reports {cumulative_masked_tokens}"
            )
        resynchronized = inferred_total != exact_total
        if resynchronized:
            for head_idx, count in enumerate(per_head_cumulative):
                self._cumulative_drops[(layer_idx, head_idx)] = count

        self.events.append(
            {
                "layer": layer_idx,
                "step": step,
                "phase": "prefill" if prefilling else "decode",
                "cache_len": cache_len,
                "q_len": q_len,
                "score_start": score_start,
                "scores": scores_cpu,
                "original_score_dtype": str(scores.dtype),
                "predicted_drop": predicted_drop,
                "threshold": threshold,
                "matured_start": matured_start,
                "matured_drop": matured_drop,
                "cumulative_drop": cumulative_drop,
                "incremental_resynchronized": resynchronized,
                "score_buffer_length": score_buffer_length,
                "per_head_cumulative_drops": per_head_cumulative,
                "compression_ratio": compression_ratio,
            }
        )

    def to_arrays(self) -> dict[str, np.ndarray]:
        if not self.events:
            raise RuntimeError("No trace events were recorded")
        layers = max(event["layer"] for event in self.events) + 1
        heads = self.events[0]["scores"].shape[0]
        tokens = max(event["cache_len"] for event in self.events)
        shape = (layers, heads, tokens)
        scores = np.full(shape, np.nan, dtype=np.float32)
        score_valid_mask = np.zeros(shape, dtype=np.bool_)
        predicted_drop_mask = np.zeros(shape, dtype=np.bool_)
        final_drop_mask = np.zeros(shape, dtype=np.bool_)

        for event in self.events:
            layer = event["layer"]
            if event["scores"].shape[0] != heads:
                raise ValueError("KV-head count changed within a request")
            start = event["score_start"]
            end = start + event["scores"].shape[-1]
            if start < 0 or end > tokens:
                raise ValueError(f"Invalid score interval [{start}, {end}) for T={tokens}")
            if score_valid_mask[layer, :, start:end].any():
                raise ValueError(f"Overlapping score interval for layer {layer}: [{start}, {end})")
            scores[layer, :, start:end] = event["scores"]
            score_valid_mask[layer, :, start:end] = True
            predicted_drop_mask[layer, :, start:end] = event["predicted_drop"]

            cumulative_end = event["cumulative_drop"].shape[-1]
            final_drop_mask[layer, :, :cumulative_end] = event["cumulative_drop"]

        return {
            "scores": scores,
            "score_valid_mask": score_valid_mask,
            "predicted_drop_mask": predicted_drop_mask,
            "final_drop_mask": final_drop_mask,
            "shape": np.asarray(shape, dtype=np.int64),
        }

    def validate(self, sliding_window: int) -> dict[str, np.ndarray]:
        arrays = self.to_arrays()
        valid = arrays["score_valid_mask"]
        final_drop = arrays["final_drop_mask"]
        if np.any(final_drop & ~valid):
            raise AssertionError("Final mask contains a drop at a position without a recorded score")
        valid_counts = valid.sum(axis=-1)
        if not np.all(valid_counts == valid_counts[0, 0]):
            raise AssertionError("Layers/KV heads do not cover the same number of scored tokens")
        expected_positions = np.arange(valid.shape[-1]) < valid_counts[0, 0]
        if not np.all(valid == expected_positions):
            raise AssertionError("Scored token positions must be contiguous and start at zero")
        if sliding_window:
            for layer in range(valid.shape[0]):
                valid_positions = np.flatnonzero(valid[layer].any(axis=0))
                recent = valid_positions[-sliding_window:]
                if final_drop[layer, :, recent].any():
                    raise AssertionError(f"Layer {layer} drops a token in the protected sliding window")
        return arrays

    def _decoding_rows(self) -> list[dict[str, Any]]:
        rows = []
        for event in self.events:
            matured_tokens = event["matured_drop"].shape[-1]
            for head_idx, cumulative_drops in enumerate(event["per_head_cumulative_drops"]):
                newly_dropped = int(event["matured_drop"][head_idx].sum())
                matured_total = 0 if event["matured_start"] is None else event["matured_start"] + matured_tokens
                rows.append(
                    {
                        "request_id": self.request_id,
                        "step": event["step"],
                        "phase": event["phase"],
                        "layer": event["layer"],
                        "kv_head": head_idx,
                        "cache_tokens": event["cache_len"],
                        "hot_tokens": event["score_buffer_length"],
                        "cold_tokens": matured_total - cumulative_drops,
                        "newly_admitted_tokens": matured_tokens - newly_dropped,
                        "newly_dropped_tokens": newly_dropped,
                        "logical_kept_tokens": event["cache_len"] - cumulative_drops,
                        "cumulative_dropped_tokens": cumulative_drops,
                        "incremental_resynchronized": event["incremental_resynchronized"],
                    }
                )
        return rows

    def write(
        self,
        output_dir: Path,
        *,
        manifest: dict[str, Any],
        request_metadata: dict[str, Any],
        sliding_window: int,
    ) -> dict[str, Path]:
        arrays = self.validate(sliding_window)
        output_dir.mkdir(parents=True, exist_ok=False)
        paths = {
            "manifest": output_dir / "manifest.json",
            "score_mask": output_dir / "score_mask.npz",
            "request_summary": output_dir / "request_summary.csv",
            "layer_head_summary": output_dir / "layer_head_summary.csv",
            "decoding": output_dir / "decoding_events.csv",
        }

        complete_manifest = {
            "schema_version": SCHEMA_VERSION,
            "tensor_layout": TENSOR_LAYOUT,
            "score_dtype": "float32",
            "original_score_dtype": self.events[0]["original_score_dtype"],
            "mask_dtype": "bool",
            "mask_encoding": "unpacked pilot trace",
            "near_threshold_epsilon": self.near_threshold_epsilon,
            "contains_attention_matrix": False,
            "incremental_resynchronization_events": sum(
                event["incremental_resynchronized"] for event in self.events
            ),
            "summary_format": "csv",
            **manifest,
        }
        paths["manifest"].write_text(json.dumps(complete_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        np.savez_compressed(paths["score_mask"], **arrays)

        valid = arrays["score_valid_mask"]
        final_drop = arrays["final_drop_mask"] & valid
        logical_total = int(valid.sum())
        logical_removed = int(final_drop.sum())
        logical_kept = logical_total - logical_removed
        request_row = {
            "request_id": self.request_id,
            **request_metadata,
            "logical_kept_kv": logical_kept,
            "logical_total_kv": logical_total,
            "removed_fraction": logical_removed / logical_total,
            "compression_factor": logical_total / logical_kept if logical_kept else float("inf"),
        }
        self._write_csv(paths["request_summary"], [request_row])

        layer_head_rows = []
        threshold = float(self.events[0]["threshold"])
        for layer in range(valid.shape[0]):
            for head in range(valid.shape[1]):
                head_valid = valid[layer, head]
                head_scores = arrays["scores"][layer, head, head_valid]
                removed = int(final_drop[layer, head].sum())
                total = int(head_valid.sum())
                layer_head_rows.append(
                    {
                        "request_id": self.request_id,
                        "layer": layer,
                        "kv_head": head,
                        "sequence_tokens": total,
                        "kept_tokens": total - removed,
                        "removed_tokens": removed,
                        "retention_ratio": (total - removed) / total,
                        "score_mean": float(head_scores.mean()),
                        "score_std": float(head_scores.std()),
                        "score_min": float(head_scores.min()),
                        "score_max": float(head_scores.max()),
                        "margin_abs_mean": float(np.abs(head_scores - threshold).mean()),
                        "near_threshold_fraction": float(
                            (np.abs(head_scores - threshold) <= self.near_threshold_epsilon).mean()
                        ),
                    }
                )
        self._write_csv(paths["layer_head_summary"], layer_head_rows)
        self._write_csv(paths["decoding"], self._decoding_rows())
        return paths

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        if not rows:
            raise ValueError(f"Cannot write empty CSV: {path}")
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
