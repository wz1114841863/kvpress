from pathlib import Path

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import (
    LLAMA_SCHEMA,
    QWEN_SCHEMA,
    validate_anchor,
)


ROOT = Path("analysis/experiments")


def test_a442_validates_both_anchor_contracts_without_numeric_pooling():
    qwen = validate_anchor(
        path=ROOT / "route_a441_qwen_deferred_activation_fixed8_single_gpu3_01" / "a441_qwen_deferred_activation_contract_report.json",
        expected_schema=QWEN_SCHEMA,
        anchor="qwen3_8b",
    )
    llama = validate_anchor(
        path=ROOT / "route_a440_deferred_activation_llama31_fixed8_single_gpu3_01" / "a440_deferred_activation_contract_report.json",
        expected_schema=LLAMA_SCHEMA,
        anchor="llama31_8b_instruct",
    )
    assert qwen["layer_count"] == 36
    assert llama["layer_count"] == 32
    assert [row["workload"] for row in qwen["workload_rows"]] == ["retrieval", "summarization", "reasoning"]
    assert all(row["bypass_branch"]["route_a_logical_state_constructed"] is False for anchor in (qwen, llama) for row in anchor["workload_rows"])
    assert all(row["activation_branch"]["commit_count_per_layer"] == 1 for anchor in (qwen, llama) for row in anchor["workload_rows"])
