#!/usr/bin/env python3
"""Replay all frozen event/scoreboard prerequisites for RTL3.9-C4-P0."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kvpress.rtl2_historical_provenance import replay_frozen_manifest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "rtl2_4_3_attention_terminal": "analysis/rtl2_4_3_attention_terminal_scoreboard_binding.json",
    "rtl2_5_5_active_state": "analysis/rtl2_5_5_active_state_scoreboard_binding.json",
    "rtl2_6_5c_event_capture_replay": "analysis/rtl2_6_5c_event_capture_replay_manifest.json",
    "rtl3_7c_drain_fault_stall_reset": "analysis/rtl3_7c_drain_fault_stall_reset_scoreboard_manifest.json",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provenance",
        type=Path,
        default=ROOT / "analysis/rtl3_9_c4_p0_event_scoreboard_historical_provenance.json",
        help="C4-P0 immutable event/scoreboard provenance record",
    )
    args = parser.parse_args(argv)
    provenance = json.loads(args.provenance.read_text(encoding="utf-8"))
    assert provenance["schema_version"] == "kvzap-route-a-rtl3-9-c4-p0-event-scoreboard-historical-provenance-1.0"
    assert set(provenance["records"]) == set(EXPECTED)
    total = 0
    for record_id, relative_manifest in EXPECTED.items():
        _, count = replay_frozen_manifest(
            root=ROOT,
            manifest_path=ROOT / relative_manifest,
            provenance_path=args.provenance,
            record_id=record_id,
        )
        total += count
    print(f"PASS: RTL3.9-C4-P0 replayed {len(EXPECTED)} frozen event/scoreboard records ({total} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
