"""Official DMS native-slot attention replay under its own tolerance contract.

Native logical-slot/block-table order is preserved; this is not packed cold.
"""
from __future__ import annotations

import hashlib
from typing import Any
import torch

def gather_native_slots(key_blocks: torch.Tensor, value_blocks: torch.Tensor, block_table: torch.Tensor, sequence_lengths: torch.Tensor) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
    """Gather only active native slots in the logical order passed to FlashAttention."""
    if key_blocks.shape != value_blocks.shape or key_blocks.ndim != 4 or key_blocks.shape[2] != 1:
        raise ValueError("DMS-M4 requires matching rank-4 native key/value blocks")
    if block_table.ndim != 2 or sequence_lengths.ndim != 1 or block_table.shape[0] != sequence_lengths.numel():
        raise ValueError("DMS-M4 native block-table/page-batch mismatch")
    block_size = int(key_blocks.shape[1]); keys, values = [], []
    for batch, length in enumerate(sequence_lengths.detach().to("cpu", dtype=torch.int64).tolist()):
        if length <= 0:
            raise ValueError("DMS-M4 decode attention has an empty native resident list")
        positions = torch.arange(length, device=key_blocks.device, dtype=torch.long)
        table_index = positions // block_size
        if int(table_index[-1]) >= block_table.shape[1]:
            raise ValueError("DMS-M4 native sequence exceeds supplied block table")
        block_ids = block_table[batch, table_index].to(dtype=torch.long)
        if bool((block_ids < 0).any().item()):
            raise ValueError("DMS-M4 encountered unresolved active native block-table entry")
        offset = positions % block_size
        keys.append(key_blocks[block_ids, offset, 0, :]); values.append(value_blocks[block_ids, offset, 0, :])
    return keys, values

def replay_active_resident_attention(query: torch.Tensor, key_slots: list[torch.Tensor], value_slots: list[torch.Tensor], native_output: torch.Tensor, *, scale: float, atol: float, rtol: float) -> dict[str, Any]:
    """FP32 semantic replay; FlashAttention's reduction order need not be bitwise equal."""
    if query.ndim != 4 or query.shape[1] != 1 or native_output.shape != query.shape:
        raise ValueError("DMS-M4 requires q_len=1 matching FlashAttention query/output layouts")
    if len(key_slots) != query.shape[0] or len(value_slots) != query.shape[0]:
        raise ValueError("DMS-M4 page-batch count differs between query and resident slots")
    rows = []
    for batch, (keys, values) in enumerate(zip(key_slots, value_slots)):
        if keys.ndim != 2 or keys.shape != values.shape or keys.shape[1] != query.shape[-1]:
            raise ValueError("DMS-M4 malformed gathered native resident K/V")
        q, k, v = query[batch, 0].float(), keys.float(), values.float()
        rows.append(torch.softmax((q @ k.T) * float(scale), dim=-1) @ v)
    manual = torch.stack(rows).unsqueeze(1); observed = native_output.float()
    if not torch.isfinite(manual).all() or not torch.isfinite(observed).all():
        raise AssertionError("DMS-M4 active-resident replay observed nonfinite values")
    difference = (manual - observed).abs()
    return {"accepted": bool(torch.allclose(manual, observed, atol=atol, rtol=rtol)), "page_batch_count": int(query.shape[0]), "query_heads_per_kv_head_group": int(query.shape[2]), "head_dim": int(query.shape[3]), "resident_slot_lengths": [int(item.shape[0]) for item in key_slots], "max_abs_difference": float(difference.max().item()), "mean_abs_difference": float(difference.mean().item()), "manual_output_sha256": hashlib.sha256(manual.detach().cpu().contiguous().numpy().tobytes()).hexdigest(), "official_output_sha256": hashlib.sha256(observed.detach().cpu().contiguous().numpy().tobytes()).hexdigest()}
