# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json

import pytest

from kvpress import KVzapPress
from tools.run_kvzap_trace import PRESETS, build_builtin_request, load_jsonl_request, make_dms_press


@pytest.mark.parametrize("preset", PRESETS)
def test_builtin_trace_presets_are_distinct_and_long(preset):
    request = build_builtin_request(preset, context_repetitions=4)
    assert request["request_id"] == f"builtin_{preset}_trace"
    assert request["dataset"] == "builtin"
    assert request["context"]
    assert request["question"]


def test_retrieval_preset_contains_needle():
    request = build_builtin_request("retrieval", context_repetitions=4)
    assert "ORCHID-7429" in request["context"]
    assert request["subset"] == "retrieval"


def test_load_jsonl_request_requires_selection_for_multiple_rows(tmp_path):
    path = tmp_path / "requests.jsonl"
    requests = [
        {"request_id": "r0", "context": "context zero", "question": "question zero"},
        {
            "request_id": "r1",
            "dataset": "longbench",
            "subset": "reasoning",
            "context": "context one",
            "question": "question one",
        },
    ]
    path.write_text("\n".join(json.dumps(request) for request in requests) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="select one with --request-id"):
        load_jsonl_request(path, request_id=None)

    selected = load_jsonl_request(path, request_id="r1")
    assert selected == requests[1]


def test_load_jsonl_request_adds_metadata_defaults(tmp_path):
    path = tmp_path / "request.jsonl"
    request = {"request_id": "r0", "context": "context", "question": "question"}
    path.write_text(json.dumps(request) + "\n", encoding="utf-8")

    selected = load_jsonl_request(path, request_id=None)

    assert selected == {**request, "dataset": "custom", "subset": "custom"}


def test_trace_passes_use_independent_dms_state():
    scorer = KVzapPress(model_type="mlp")
    first = make_dms_press(scorer, threshold=-4.0, window_size=128)
    second = make_dms_press(scorer, threshold=-4.0, window_size=128)

    assert first.press is second.press
    assert first.scores_buffer is not second.scores_buffer
