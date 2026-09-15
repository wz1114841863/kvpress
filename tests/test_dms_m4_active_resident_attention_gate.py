import pytest
import torch

from tools.run_dms_route_a_m4_active_resident_attention_gate import M4_SCHEMA, gather_native_slots, replay_active_resident_attention


def test_m4_schema_is_explicitly_active_resident_only():
    assert M4_SCHEMA == "route-a-dms-m4-active-resident-attention-gate-1.0"


def test_m4_gathers_native_slots_in_block_table_order():
    keys = torch.arange(4 * 2 * 1 * 2, dtype=torch.float32).reshape(4, 2, 1, 2)
    got_keys, got_values = gather_native_slots(keys, keys + 100, torch.tensor([[2, 0], [1, 3]], dtype=torch.int32), torch.tensor([3, 2]))
    assert got_keys[0].tolist() == [[8.0, 9.0], [10.0, 11.0], [0.0, 1.0]]
    assert got_values[1].tolist() == [[104.0, 105.0], [106.0, 107.0]]


def test_m4_fp32_replay_accepts_manual_native_layout():
    query = torch.tensor([[[[1.0, 0.0], [0.0, 1.0]]]])
    keys, values = [torch.tensor([[1.0, 0.0], [0.0, 1.0]])], [torch.tensor([[4.0, 0.0], [0.0, 8.0]])]
    native = (torch.softmax(query[0, 0] @ keys[0].T, dim=-1) @ values[0]).unsqueeze(0).unsqueeze(1)
    assert replay_active_resident_attention(query, keys, values, native, scale=1.0, atol=1e-6, rtol=1e-6)["accepted"]


def test_m4_rejects_non_decode_layout():
    query = torch.ones((1, 2, 1, 2))
    with pytest.raises(ValueError, match="q_len=1"):
        replay_active_resident_attention(query, [torch.ones((1, 2))], [torch.ones((1, 2))], query, scale=1.0, atol=1e-3, rtol=1e-3)
