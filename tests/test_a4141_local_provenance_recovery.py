#!/usr/bin/env python3
"""Focused no-model check for the tracked A4.14.1 recovery record."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_a4141_local_provenance_recovery_record() -> None:
    subprocess.run(
        ["python3", "tools/validate_a4141_local_provenance_recovery.py"],
        cwd=ROOT,
        check=True,
    )
