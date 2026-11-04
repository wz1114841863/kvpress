#!/usr/bin/env python3
"""Wrap immutable PM1 combinational selector SV with matched Q/D registers."""

from __future__ import annotations

import argparse
from pathlib import Path


ENTRIES = 36720
INDEX_WIDTH = 16


def wrapper(side: str) -> str:
    child = f"pm1_{side}_selector"
    top = f"pm1_{side}_registered_selector"
    return f"""

// PM1 r2 measurement-only wrapper. Both sides use this exact Q/D boundary.
module {top}(
  input clock,
  input reset,
  input io_serial_in,
  output io_selected_valid,
  output [{INDEX_WIDTH - 1}:0] io_selected_index
);
  reg [{ENTRIES - 1}:0] allocated;
  reg selected_valid_q;
  reg [{INDEX_WIDTH - 1}:0] selected_index_q;
  wire selected_valid_d;
  wire [{INDEX_WIDTH - 1}:0] selected_index_d;

  {child} selector(
    .clock(clock),
    .reset(reset),
    .io_allocated(allocated),
    .io_selected_valid(selected_valid_d),
    .io_selected_index(selected_index_d)
  );

  always @(posedge clock) begin
    if (reset) begin
      allocated <= {ENTRIES}'b0;
      selected_valid_q <= 1'b0;
      selected_index_q <= {INDEX_WIDTH}'b0;
    end else begin
      allocated <= {{allocated[{ENTRIES - 2}:0], io_serial_in}};
      selected_valid_q <= selected_valid_d;
      selected_index_q <= selected_index_d;
    end
  end

  assign io_selected_valid = selected_valid_q;
  assign io_selected_index = selected_index_q;
endmodule
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    for side in ("original", "banked"):
        child = f"pm1_{side}_selector"
        source = args.input_dir / f"{child}.sv"
        text = source.read_text()
        required = (
            f"module {child}",
            "input            clock",
            "                   reset,",
            "io_allocated",
            "io_selected_valid",
            "io_selected_index",
        )
        for token in required:
            if token not in text:
                raise ValueError(f"{source}: missing expected token {token!r}")
        output = args.output_dir / f"pm1_{side}_registered_selector.sv"
        output.write_text(text.rstrip() + wrapper(side))
    print(f"PM1_REGISTERED_WRAPPER_INPUT_PASS root={args.output_dir}")


if __name__ == "__main__":
    main()
