#!/usr/bin/env python3
"""Validate the tracked A4.14.1 recovery record and, on request, local bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/synthesis_eligibility_manifest.json"
RECORD = ROOT / "analysis/a4141_local_provenance_recovery_20261016.md"

EXPECTED = {
    "analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/a4141_accounted_net_benefit_ledger_report.json": "0f43ec6dc30912210e4c565ebdd57554b02b7ca3f22326a498924e4cf1f2fdcb",
    "analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4131_source.json": "ba6ec8291d213317e953dd0ac3a050524cf10a327705c6390fe652531a98950c",
    "analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4133_source.json": "fea9780d44238f5128008793a12e605e411a95355eaa44e4ad6f71f8b6a735f1",
    "analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4135_source.json": "8a3c07255d8e6382807701b437935c89207b60065df5d671dacad0b8cfb7a502",
    "analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4140_source.json": "3d3cc52eade09c20ed305159d78b7bc43673db0072a4d1b9bc211bd061ae8034",
    "analysis/experiments/route_a4140_workload_aligned_metadata_cost_01/input_artifacts/a4112b_source.json": "57da81a6fb7e3a9540fad2d0a45ba28ae418ffc69d9e81ef2fbf02090dcdc3a3",
    "analysis/experiments/route_a4140_workload_aligned_metadata_cost_01/input_artifacts/lifecycle/retrieval/a4112b_external_storage_lifecycle.jsonl.gz": "0b5ca92920b4a9a243cc3631bbb37005d558bf8330251eb9e5080746bed87f30",
    "analysis/experiments/route_a4140_workload_aligned_metadata_cost_01/input_artifacts/lifecycle/summarization/a4112b_external_storage_lifecycle.jsonl.gz": "60aa2000582d350400de1dd3e8f77abb07196b5690522aa6e9fb5c16860d7cdf",
    "analysis/experiments/route_a4140_workload_aligned_metadata_cost_01/input_artifacts/lifecycle/reasoning/a4112b_external_storage_lifecycle.jsonl.gz": "3776cd5c0a2170fc5e7f4952a178c624e479777da710491b1a7e0405f263b74f",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-local-artifacts", action="store_true")
    args = parser.parse_args()

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    recovery = data["a4141_local_provenance_recovery"]
    assert recovery["status"] == "complete_read_only_recovery_and_preflight"
    assert recovery["record"] == "analysis/a4141_local_provenance_recovery_20261016.md"
    assert recovery["recovered_artifact_count"] == len(EXPECTED)
    assert recovery["report_sha256"] == EXPECTED[next(iter(EXPECTED))]
    assert RECORD.is_file()
    text = RECORD.read_text(encoding="utf-8")
    for path, digest in EXPECTED.items():
        assert path in text, path
        assert digest in text, digest
    for phrase in [
        "no new A4 output",
        "created.` The boolean checks",
        "not physical\nenergy validation",
        "Still unresolved",
    ]:
        assert phrase in text, phrase

    if not args.require_local_artifacts:
        print("PASS: A4.14.1 recovery record is internally consistent")
        return 0

    for relative, digest in EXPECTED.items():
        path = ROOT / relative
        assert path.is_file(), path
        assert sha256(path) == digest, path
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--", relative], cwd=ROOT, check=False
        )
        assert ignored.returncode == 0, relative
    report = json.loads((ROOT / next(iter(EXPECTED))).read_text(encoding="utf-8"))
    assert report["schema_version"] == "kvzap-route-a4141-accounted-net-benefit-ledger-1.0"
    assert report["status"] == "complete"
    assert len(report["workload_rows"]) == 3
    print("PASS: A4.14.1 recovered local bytes match all recorded provenance hashes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
