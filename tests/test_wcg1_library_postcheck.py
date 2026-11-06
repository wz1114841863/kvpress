"""Regress the redirected-report error that invalidated WCG1 library probe r2."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "hardware/route_a/dc/run_wcg1_library_cost_probe.sh"
POSTCHECK = re.search(r"<<'PY'\n(.*?)\nPY", RUNNER.read_text(), re.S).group(1)


def fixture(tmp_path):
    (tmp_path / "metadata").mkdir()
    (tmp_path / "native.log").write_text("KVZAP_WCG1_LIBRARY_METADATA_PASS cells=16 gates=10\n")
    (tmp_path / "metadata/cells.tsv").write_text(
        "cell\tarea\n" + "".join(f"cell{i}\t2.52\n" for i in range(16))
    )
    for name in ("lib_cell_attributes.rpt", "lib_pin_attributes.rpt", "library_identity.tsv"):
        (tmp_path / "metadata" / name).write_text("valid nonempty metadata\n")
    return tmp_path


def check(path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["postcheck", str(path)])
    exec(compile(POSTCHECK, str(RUNNER), "exec"), {})


def test_complete_library_metadata_passes(tmp_path, monkeypatch):
    check(fixture(tmp_path), monkeypatch)


def test_redirected_report_error_overrides_native_success_marker(tmp_path, monkeypatch):
    path = fixture(tmp_path)
    (path / "metadata/library.rpt").write_text(
        "Error: The report_lib command failed to run. Check Library Compiler. (LCSH-3)\n"
    )
    with pytest.raises(AssertionError):
        check(path, monkeypatch)


def test_missing_cell_price_fails(tmp_path, monkeypatch):
    path = fixture(tmp_path)
    (path / "metadata/cells.tsv").write_text("cell\tarea\ncell0\t\n")
    with pytest.raises(AssertionError):
        check(path, monkeypatch)


def test_native_error_overrides_native_success_marker(tmp_path, monkeypatch):
    path = fixture(tmp_path)
    with (path / "native.log").open("a") as stream:
        stream.write("Error: unexpected library input\n")
    with pytest.raises(AssertionError):
        check(path, monkeypatch)
