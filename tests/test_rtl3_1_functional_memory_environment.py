import copy
import subprocess
import sys
from pathlib import Path

import pytest

from kvpress.rtl3_1_functional_memory_environment import (
    RTL31FunctionalMemoryEnvironmentError,
    load,
    validate,
    validate_hashes,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "analysis/rtl3_1_functional_memory_environment_manifest.json"
VALIDATOR = ROOT / "tools/validate_rtl3_1_functional_memory_environment.py"


def payload():
    return load(MANIFEST)


def test_rtl31_remains_testbench_only_and_preserves_both_rtl30_stops():
    manifest = payload()
    validate(manifest)
    assert manifest["owner"] == "testbench_route_a_functional_memory_environment"
    assert manifest["unresolved_stops"] == [
        "packed_read_association_owner blocks rtl3_2",
        "partial_provider_query_position_contract blocks rtl3_5",
    ]


def test_rtl31_rejects_authority_or_premature_s2_scope():
    manifest = payload()
    bad = copy.deepcopy(manifest)
    bad["forbidden"].remove("payload metadata or residency authority transfer")
    with pytest.raises(RTL31FunctionalMemoryEnvironmentError, match="evidence boundary"):
        validate(bad)
    bad = copy.deepcopy(manifest)
    bad["unresolved_stops"] = []
    with pytest.raises(RTL31FunctionalMemoryEnvironmentError, match="cannot clear"):
        validate(bad)


def test_hashes_and_cli_are_reproducible():
    manifest = payload()
    validate_hashes(manifest, ROOT)
    bad = copy.deepcopy(manifest)
    bad["source_sha256"]["analysis/rtl3_1_functional_memory_environment_contract.md"] = "0" * 64
    with pytest.raises(RTL31FunctionalMemoryEnvironmentError, match="hash-bound"):
        validate_hashes(bad, ROOT)
    assert "--manifest" in subprocess.run([sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
    assert "passed" in subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True, check=True).stdout
