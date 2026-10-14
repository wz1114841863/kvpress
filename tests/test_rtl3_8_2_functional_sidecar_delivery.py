from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_8_2_functional_sidecar_delivery.py"
PROVENANCE = ROOT / "analysis/rtl3_8_2_functional_sidecar_delivery_historical_provenance.json"


def test_rtl3_8_2_functional_sidecar_delivery_frozen_manifest_replay_passes() -> None:
    assert subprocess.run(
        [sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, check=False,
        capture_output=True, text=True,
    ).returncode == 0
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, check=False,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASS: RTL3.8.2" in result.stdout
    assert "frozen manifest replayed" in result.stdout


def test_rtl3_8_2_validator_rejects_nonimmutable_provenance_revision(tmp_path: Path) -> None:
    bad = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    bad["frozen_source_commit"] = "0" * 40
    bad_path = tmp_path / "bad_provenance.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--provenance", str(bad_path)],
        cwd=ROOT, check=False, capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "Needed a single revision" in result.stderr or "unknown revision" in result.stderr
