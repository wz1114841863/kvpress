#!/usr/bin/env python3
"""Validate Gate-RTL0.4 Python-scoreboard oracle bindings; no RTL claim."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Gate-RTL0.4 scoreboard-oracle planning; no RTL, timing, or PPA claim.")
    parser.add_argument("--manifest", type=Path, default=Path("analysis/rtl_entry_scoreboard_oracle_manifest.json"))
    args = parser.parse_args(); data = json.loads(args.manifest.read_text())
    matrix = json.loads(Path(data["assertion_matrix"]).read_text()); expected = {r["id"] for r in matrix["records"]}; bindings = data.get("bindings", [])
    ids = {b.get("assertion_id") for b in bindings}
    if ids != expected or len(ids) != len(bindings): raise SystemExit("oracle validation failed: assertion binding inventory drift")
    for binding in bindings:
        if not all(binding.get(k) for k in ("rtl_owner", "oracle", "entry_points", "observe", "forbidden_adapter")): raise SystemExit(f"oracle validation failed: incomplete {binding['assertion_id']}")
        if not Path(binding["oracle"]).is_file(): raise SystemExit(f"oracle validation failed: missing {binding['oracle']}")
    print(f"Gate-RTL0 scoreboard oracle manifest passed: {args.manifest}"); return 0
if __name__ == "__main__": raise SystemExit(main())
