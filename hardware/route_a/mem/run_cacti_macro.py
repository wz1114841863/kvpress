#!/usr/bin/env python3
"""Run one explicit Route-A CACTI SRAM proxy macro with provenance checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware.route_a.mem.cacti_runner import CactiMacroRunner, MacroSpec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one explicit public-CACTI Route-A SRAM proxy macro. This is not a PDK, "
            "physical macro, cycle, throughput, workload-energy, architecture, or RTL result."
        )
    )
    parser.add_argument("--name", help="Filesystem-safe macro slug; required unless --preflight-only.")
    parser.add_argument("--role", default="unspecified", help="Human-readable macro role.")
    parser.add_argument("--depth", type=int, help="Entries per physical macro instance; required unless --preflight-only.")
    parser.add_argument("--width-bits", type=int, help="Byte-aligned data width per entry; required unless --preflight-only.")
    parser.add_argument("--instances", type=int, default=1, help="Identical macro instances to aggregate.")
    parser.add_argument("--read-ports", type=int, default=0, help="Explicit exclusive read ports; never inferred.")
    parser.add_argument("--write-ports", type=int, default=0, help="Explicit exclusive write ports; never inferred.")
    parser.add_argument("--readwrite-ports", type=int, default=1, help="Explicit read-write ports; never inferred.")
    parser.add_argument("--technology-node-um", type=float, default=0.032, help="Public CACTI proxy node, not a target PDK declaration.")
    parser.add_argument("--toolchain-root", type=Path, default=Path(__file__).resolve().parent / "cacti_toolchain", help="Route-A CACTI toolchain directory.")
    parser.add_argument("--output-dir", type=Path, help="Previously absent directory for config, raw logs, and record; required unless --preflight-only.")
    parser.add_argument("--preflight-only", action="store_true", help="Validate the locked local toolchain without creating output or executing CACTI.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runner = CactiMacroRunner(args.toolchain_root, args.technology_node_um)
    if args.preflight_only:
        toolchain = runner.validate_toolchain()
        print(json.dumps({key: value for key, value in toolchain.items() if not isinstance(value, Path)}, sort_keys=True))
        return
    if args.output_dir is None:
        raise ValueError("--output-dir is required unless --preflight-only")
    if args.name is None or args.depth is None or args.width_bits is None:
        raise ValueError("--name, --depth, and --width-bits are required unless --preflight-only")
    spec = MacroSpec(
        name=args.name,
        role=args.role,
        depth=args.depth,
        width_bits=args.width_bits,
        instances=args.instances,
        read_ports=args.read_ports,
        write_ports=args.write_ports,
        readwrite_ports=args.readwrite_ports,
    )
    record = runner.run(spec, args.output_dir)
    print(
        f"Route-A CACTI macro complete: {args.output_dir / 'macro_record.json'} "
        f"area_mm2={record['aggregate_data_array_area_mm2']:.9g}"
    )


if __name__ == "__main__":
    main()
