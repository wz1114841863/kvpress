import pytest

from tools.build_kvzap_route_a4130_payload_interface_inventory import payload_layout, validate_target


def test_qwen_reference_payload_word_and_page_arithmetic():
    layout = payload_layout(head_dim=128, scalar_bits=16, page_tokens=64, position_bits=64)
    assert layout["key_word_bytes"] == 256
    assert layout["value_word_bytes"] == 256
    assert layout["kv_token_word_bytes"] == 512
    assert layout["page_payload_bytes"] == 32768
    assert layout["logical_position_sidecar_bytes"] == 512
    assert layout["reference_page_payload_plus_position_sidecar_bytes"] == 33280


def test_payload_layout_rejects_fractional_byte_shape():
    with pytest.raises(ValueError, match="whole-byte"):
        payload_layout(head_dim=128, scalar_bits=15, page_tokens=64, position_bits=64)


def test_target_validation_requires_the_a4130_qwen_page_contract():
    target = {
        "model": {
            "hf_id": "Qwen/Qwen3-8B", "num_hidden_layers": 36, "num_key_value_heads": 8,
            "head_dim": 128, "cache_dtype": "bfloat16", "kv_bytes_per_layer_head_token": 512,
        },
        "route_a": {"hot_window_tokens": 128, "page_tokens_candidates": [64, 128]},
    }
    assert validate_target(target)["page_tokens"] == 64
    target["route_a"]["page_tokens_candidates"] = [128]
    with pytest.raises(ValueError, match="window/page"):
        validate_target(target)
