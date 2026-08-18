# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from tools.prepare_kvzap_real_pilot import (
    balanced_take,
    context_token_count,
    length_bucket,
    parse_length_bins,
    parse_task_specs,
    resolve_hub_revision,
    select_pilot_rows,
)


class PlainTokenizer:
    chat_template = None
    bos_token = "<bos>"

    def encode(self, text, add_special_tokens=False):
        assert add_special_tokens is False
        return list(text)


class FakeHubApi:
    def dataset_info(self, repo_id, revision):
        assert repo_id == "dataset/repo"
        assert revision == "main"
        return type("Info", (), {"sha": "dataset-sha"})()

    def model_info(self, repo_id, revision):
        assert repo_id == "model/repo"
        return type("Info", (), {"sha": revision})()


def candidate(category, task, source_index, token_count):
    return {
        "category": category,
        "task": task,
        "source_index": source_index,
        "context_sha256": f"hash-{category}-{task}-{source_index}",
        "length_bucket": (0, 10) if token_count < 10 else (10, 20),
    }


def test_parse_specs_bins_and_context_count():
    assert parse_task_specs(["retrieval:qasper"]) == [("retrieval", "qasper")]
    assert parse_length_bins(["0:10", "10:20"]) == [(0, 10), (10, 20)]
    assert length_bucket(10, [(0, 10), (10, 20)]) == (10, 20)
    assert context_token_count(PlainTokenizer(), "abc") == len("<bos>abc")

    with pytest.raises(ValueError, match="Overlapping"):
        parse_length_bins(["0:10", "9:20"])
    with pytest.raises(ValueError, match="Duplicate"):
        parse_task_specs(["retrieval:qasper", "retrieval:qasper"])


def test_resolve_hub_revision_uses_repository_metadata():
    api = FakeHubApi()
    assert resolve_hub_revision(api, "dataset/repo", "main", repo_type="dataset") == "dataset-sha"
    immutable_revision = "a" * 40
    assert resolve_hub_revision(api, "model/repo", immutable_revision, repo_type="model") == immutable_revision

    with pytest.raises(ValueError, match="Unsupported"):
        resolve_hub_revision(api, "model/repo", immutable_revision, repo_type="space")


def test_balanced_take_round_robins_tasks_deterministically():
    rows = [candidate("retrieval", "a", index, 5) for index in range(4)]
    rows += [candidate("retrieval", "b", index, 5) for index in range(4)]

    first = balanced_take(rows, 4, seed=42)
    second = balanced_take(list(reversed(rows)), 4, seed=42)

    assert [(row["task"], row["source_index"]) for row in first] == [
        (row["task"], row["source_index"]) for row in second
    ]
    assert {row["task"] for row in first} == {"a", "b"}


def test_select_pilot_rows_reports_bucket_shortfalls():
    rows = [
        candidate("retrieval", "a", 0, 5),
        candidate("retrieval", "b", 1, 5),
        candidate("retrieval", "a", 2, 15),
    ]

    selected, report = select_pilot_rows(
        rows,
        bins=[(0, 10), (10, 20)],
        samples_per_bucket=2,
        seed=42,
    )

    assert len(selected) == 3
    assert [row["shortfall"] for row in report] == [0, 1]
