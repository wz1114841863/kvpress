# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json

import pytest
import yaml

from tools.run_kvzap_baseline import (
    build_builtin_requests,
    get_runtime_metadata,
    load_requests,
    removed_fraction_to_factor,
    score_required_substrings,
    stable_hash,
)


def test_removed_fraction_to_factor():
    assert removed_fraction_to_factor(0.0) == 1.0
    assert removed_fraction_to_factor(0.5) == 2.0
    assert removed_fraction_to_factor(0.75) == 4.0
    with pytest.raises(ValueError):
        removed_fraction_to_factor(1.0)


def test_score_required_substrings():
    assert score_required_substrings("The code is ORCHID-7429.", ["orchid-7429"]) == (True, 1.0)
    assert score_required_substrings("Memory bandwidth matters.", ["memory", "quantization"]) == (False, 0.5)
    assert score_required_substrings("Unscored answer", []) == (None, None)


def test_load_requests(tmp_path):
    path = tmp_path / "requests.jsonl"
    request = {"request_id": "r0", "context": "context", "question": "question"}
    path.write_text(json.dumps(request) + "\n", encoding="utf-8")

    loaded = load_requests(path)

    assert loaded == [
        {
            **request,
            "subset": "custom",
            "required_substrings": [],
            "max_new_tokens": 64,
        }
    ]


def test_builtin_requests_and_hash_are_stable():
    requests = build_builtin_requests(context_repetitions=4)
    assert len(requests) == 3
    assert len({request["request_id"] for request in requests}) == len(requests)
    assert "ORCHID-7429" in requests[0]["context"]
    assert stable_hash({"b": 2, "a": 1}) == stable_hash({"a": 1, "b": 2})


def test_runtime_metadata_is_yaml_serializable():
    metadata = get_runtime_metadata()
    assert type(metadata["torch_version"]) is str
    assert type(metadata["transformers_version"]) is str
    yaml.safe_dump(metadata)
