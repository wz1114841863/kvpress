# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

import hashlib
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_frozen_balanced_v2_artifacts_match_manifest():
    freeze = json.loads((REPOSITORY_ROOT / "analysis/longbench_balanced_v2_freeze.json").read_text())
    assert freeze["status"] == "frozen"
    assert freeze["pilot_id"] == "longbench_balanced_v2"
    assert freeze["request_count"] == 45
    assert freeze["request_status"] == {"complete": 45, "failed": 0, "offline_validation_errors": 0}
    for relative_path, expected in freeze["artifact_sha256"].items():
        if expected.get("locally_available") is False:
            assert expected["sha256_from_preparation_manifest"]
            continue
        path = REPOSITORY_ROOT / relative_path
        assert path.is_file()
        assert path.stat().st_size == expected["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected["sha256"]
