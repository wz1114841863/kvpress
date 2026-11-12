#!/usr/bin/env python3
"""No-model check of the recorded A4.14.1 availability status."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_a4141_recorded_recovery_status() -> None:
    subprocess.run(
        ["python3", "tools/validate_a4141_local_provenance_recovery.py"],
        cwd=ROOT,
        check=True,
    )
