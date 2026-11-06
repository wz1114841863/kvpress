#!/usr/bin/env python3
"""Emit a matched, one-bank cell-realization screen, not production RTL."""
import argparse
from pathlib import Path


def design(gated: bool) -> str:
    side = "gated" if gated else "reference"
    lines = [f"module wcg1_{side}(\n" + """input clock, reset, claim_clear,
input accepted_event, binding_offered,
input [5:0] write_layer, input [6:0] write_ordinal,
input [78:0] member_in, input [79:0] suffix_in,
input [5:0] mso_index, f_index, b_index, m_suffix_index,
input [6:0] c_ordinal, input [6:0] member_count,
input [63:0] c_reference, input [79:0] c_suffix,
input c_stage_available, c_sink_ready, c_valid,
output [78:0] mso_member, b_member,
output [63:0] c_member, f_member,
output [79:0] m_suffix, c_suffix_read,
output c_ready, c_issue);
reg launch_fire, launch_binding;
reg [5:0] launch_layer;
reg [6:0] launch_ordinal;
reg [78:0] launch_member;
reg [79:0] launch_suffix;
// Identical upstream registered boundary in both sides; no production change.
always @(posedge clock) begin
  if (reset) launch_fire <= 0; else launch_fire <= accepted_event;
  launch_binding <= binding_offered;
  launch_layer <= write_layer;
  launch_ordinal <= write_ordinal;
  launch_member <= member_in;
  launch_suffix <= suffix_in;
end
wire [78:0] members [0:63];
wire [79:0] suffixes [0:63];
reg [63:0] present, bound;
"""]
    for row in range(64):
        lines += [f"wire me_{row} = launch_fire && launch_layer == 6'd3 && launch_ordinal == 7'd{row};",
                  f"wire se_{row} = me_{row} && launch_binding;",
                  f"always @(posedge clock) begin\n"
                  f" if (reset || claim_clear) begin present[{row}] <= 0; bound[{row}] <= 0; end\n"
                  f" else begin if (me_{row}) present[{row}] <= 1; if (se_{row}) bound[{row}] <= 1; end\nend"]
        for kind, width, source, dest, enable in [
            ("member", 79, "launch_member", "members", f"me_{row}"),
            ("suffix", 80, "launch_suffix", "suffixes", f"se_{row}")]:
            cp = "clock"
            if gated:
                cp = f"{kind}_clock_{row}"
                lines += [f"wire {cp};", f"CKLNQD1BWP12T30P140LVT {kind}_gate_{row}"
                          f"(.CP(clock), .E({enable}), .TE(1'b0), .Q({cp}));"]
            for bit in range(width):
                cell = "DFQD2" if gated else "EDFQD2"
                ep = "" if gated else f", .E({enable})"
                lines.append(f"{cell}BWP12T30P140LVT {kind}_ff_r{row}_b{bit}"
                             f"(.D({source}[{bit}]), .CP({cp}), .Q({dest}[{row}][{bit}]){ep});")
    lines += ["""assign mso_member = members[mso_index];
assign b_member = members[b_index];
assign c_member = members[c_ordinal[5:0]][63:0];
assign f_member = members[f_index][63:0];
assign m_suffix = suffixes[m_suffix_index];
assign c_suffix_read = suffixes[c_ordinal[5:0]];
// Observable legality probe, not a replacement for the full R3 join.
wire legal_c = c_ordinal < 7'd64 && c_ordinal < member_count &&
  present[c_ordinal[5:0]] && bound[c_ordinal[5:0]] &&
  c_member == c_reference && c_suffix_read == c_suffix && c_stage_available;
assign c_ready = legal_c && c_sink_ready;
assign c_issue = legal_c && c_valid;
endmodule
"""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New output directory; refuses overwrite")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    for gated in (False, True):
        side = "gated" if gated else "reference"
        (args.output / f"{side}.v").write_text(design(gated))


if __name__ == "__main__":
    main()
