# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_baseline_artifacts_match_manifest():
    manifest = json.loads((REPOSITORY_ROOT / "analysis/baseline_freeze.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "frozen"
    assert manifest["experiment_id"] == "kvzap-baseline-20260806T043908Z"
    assert manifest["config_hash"] == "b1d3a4704b3cba56a1d31d47054c3e886bfff11bdfb8c0ca2ae89315433da1e6"
    for relative_path, expected in manifest["artifacts"].items():
        artifact = REPOSITORY_ROOT / relative_path
        assert artifact.is_file()
        assert artifact.stat().st_size == expected["bytes"]
        assert sha256(artifact) == expected["sha256"]
