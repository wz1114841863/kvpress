from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools/validate_rtl3_9_b3_atomic_publication_authority_activation.py"


def test_rtl3_9_b3_manifest_validator_and_help_pass() -> None:
    assert subprocess.run(
        [sys.executable, str(VALIDATOR), "--help"], cwd=ROOT, check=False,
        capture_output=True, text=True,
    ).returncode == 0
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)], cwd=ROOT, check=False,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASS: RTL3.9-B3" in result.stdout


def test_validator_rejects_invalid_status(tmp_path: Path) -> None:
    manifest = json.loads((ROOT / "analysis/rtl3_9_b3_atomic_publication_authority_activation_manifest.json").read_text(encoding="utf-8"))
    manifest["status"] = "invalid"
    path = tmp_path / "bad_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = subprocess.run([sys.executable, str(VALIDATOR), "--manifest", str(path)],
                            cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode != 0
