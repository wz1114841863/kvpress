from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "analysis/successor_synthesis_source_port_filelist_freeze_20261028.json"


def test_successor_freeze_pins_current_source_closure_and_live_ports() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert freeze["status"] == (
        "source_port_filelist_frozen_paired_9bit_functional_conformance_passed_non_cancellable"
    )
    assert freeze["source_anchor"]["excluded_dirty_paths"] == [".gitignore"]

    filelist = freeze["scala_filelist"]
    for group in ("build_inputs", "included_main_sources"):
        for relative, expected in filelist[group].items():
            assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected

    for dut in freeze["candidate_tops"].values():
        source = (ROOT / "hardware/route_a/chisel/src/main/scala/kvpress/routea/top" / f"{dut['class'].rsplit('.', 1)[-1]}.scala").read_text(encoding="utf-8")
        for port in dut["outer_interfaces"]:
            assert f"val {port}" in source


def test_successor_freeze_excludes_skeleton_and_uninstantiated_storage() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    excluded = freeze["scala_filelist"]["excluded_main_sources"]
    assert "RouteAKVSubsystemTop.scala" in " ".join(excluded)
    assert "RouteAM2EntryStorage.scala" in " ".join(excluded)
    assert freeze["candidate_tops"]["route_a"]["direct_pending_limit"].startswith("valid_count=1")


def test_successor_freeze_blocks_s2_cancellation_on_geometry() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    geometry = freeze["paired_s2_geometry_gate"]
    assert "3-bit" in geometry["full_kv_focused_functional_test"]
    assert "9-bit" in geometry["route_a_anchor"]
    assert geometry["status"].startswith("same-parameter functional conformance passed")
    assert "S2_PAIRED_9BIT_CONFORMANCE_EXIT=0" in geometry["paired_9bit_regression"]
    assert "common_cost_cancellation" in freeze["prohibited_conclusions"]
