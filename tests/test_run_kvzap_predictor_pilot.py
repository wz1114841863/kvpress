# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from tools.run_kvzap_predictor_pilot import (
    build_child_command,
    default_output_root,
    load_requests,
    request_shard,
    safe_trace_dir_name,
    trace_validation_error,
    verify_input_manifest,
    main,
)


def test_default_output_root_follows_input_and_shard():
    assert default_output_root(Path("pilot_inputs/longbench_balanced_v2.jsonl"), 2) == Path(
        "traces/pilots/longbench_balanced_v2_shard2"
    )


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_load_requests_and_manifest_hash(tmp_path):
    jsonl = tmp_path / "pilot.jsonl"
    write_jsonl(jsonl, [{"request_id": "r0", "context": "c", "question": "q"}])
    digest = hashlib.sha256(jsonl.read_bytes()).hexdigest()
    manifest_path = tmp_path / "pilot.manifest.json"
    manifest_path.write_text(json.dumps({"output_jsonl_sha256": digest}), encoding="utf-8")

    requests = load_requests(jsonl)
    manifest = verify_input_manifest(jsonl, manifest_path)

    assert requests[0]["dataset"] == "custom"
    assert requests[0]["_input_line"] == 1
    assert manifest["output_jsonl_sha256"] == digest

    write_jsonl(
        jsonl,
        [
            {"request_id": "r0", "context": "c", "question": "q"},
            {"request_id": "r0", "context": "c2", "question": "q2"},
        ],
    )
    with pytest.raises(ValueError, match="Duplicate request_id"):
        load_requests(jsonl)


def test_shard_directory_and_child_command_are_deterministic(tmp_path):
    assert request_shard("request-a", 4) == request_shard("request-a", 4)
    assert 0 <= request_shard("request-a", 4) < 4
    name = safe_trace_dir_name("unsafe/request id", 7)
    assert name.startswith("00007_unsafe_request_id_")
    assert "/" not in name

    args = argparse.Namespace(
        python="python",
        exporter=Path("tools/export.py"),
        input_jsonl=tmp_path / "pilot.jsonl",
        gate_a_evidence=Path("traces/gate_a"),
        threshold=-4.0,
        window_size=128,
        seed=42,
        model_revision="model-revision",
        predictor_revision="predictor-revision",
    )
    command = build_child_command(args, "request-a", Path("traces/out"))
    assert command[:2] == ["python", "tools/export.py"]
    assert command[command.index("--request-id") + 1] == "request-a"
    assert command[command.index("--output-dir") + 1] == "traces/out"


def test_incomplete_trace_is_not_resumable(tmp_path):
    trace_dir = tmp_path / "trace"
    trace_dir.mkdir()

    error = trace_validation_error(trace_dir, "r0")

    assert error is not None
    assert "missing files" in error


def test_dry_run_prints_one_fresh_process_command(tmp_path, monkeypatch, capsys):
    jsonl = tmp_path / "pilot.jsonl"
    write_jsonl(jsonl, [{"request_id": "r0", "context": "context", "question": "question"}])
    exporter = tmp_path / "exporter.py"
    exporter.write_text("# test exporter\n", encoding="utf-8")
    gate_a = tmp_path / "gate_a"
    gate_a.mkdir()
    output_root = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_kvzap_predictor_pilot.py",
            str(jsonl),
            "--allow-unmanifested-input",
            "--gate-a-evidence",
            str(gate_a),
            "--exporter",
            str(exporter),
            "--output-root",
            str(output_root),
            "--dry-run",
        ],
    )

    main()

    output = capsys.readouterr().out
    assert "--request-id r0" in output
    assert "Dry run: 1 request(s)" in output
    assert not output_root.exists()
