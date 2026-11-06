// Minimal functional scheduler test; no propagation delays or timing signoff.
module wcg1_gate_minimal(
  input clock, reset, registered_mode, unsafe_bare_and, merged_enable,
  input member_enable, suffix_enable,
  input [14:0] member_position, input [63:0] member_payload,
  input [15:0] suffix_prefix, input [63:0] suffix_handle,
  output member_clock, suffix_clock,
  output member_known, suffix_known, member_equal, suffix_equal);
reg launch_m, launch_s;
reg [78:0] launch_member;
reg [79:0] launch_suffix;
always @(posedge clock) begin
 if(reset) begin launch_m<=0; launch_s<=0; end
 else begin launch_m<=member_enable; launch_s<=suffix_enable; end
 launch_member <= {member_position,member_payload};
 launch_suffix <= {suffix_prefix,suffix_handle};
end
wire me = registered_mode ? launch_m : member_enable;
wire se = registered_mode ? launch_s : suffix_enable;
wire [78:0] md = registered_mode ? launch_member : {member_position,member_payload};
wire [79:0] sd = registered_mode ? launch_suffix : {suffix_prefix,suffix_handle};
wire mg, sg;
route_a_compact_word_clock_gate m_gate(.clock(clock),.enable(me),.gated_clock(mg));
route_a_compact_word_clock_gate s_gate(.clock(clock),.enable(merged_enable ? me : se),.gated_clock(sg));
assign member_clock = unsafe_bare_and ? clock & me : mg;
assign suffix_clock = unsafe_bare_and ? clock & se : sg;
reg mk,sk;
reg [78:0] reference_member,candidate_member;
reg [79:0] reference_suffix,candidate_suffix;
always @(posedge clock) begin
 if(reset) begin mk<=0;sk<=0;end
 else begin if(me) mk<=1; if(se) sk<=1;end
 if(me) reference_member<=md;
 if(se) reference_suffix<=sd;
end
always @(posedge member_clock) candidate_member<=md;
always @(posedge suffix_clock) candidate_suffix<=sd;
assign member_known=mk;
assign suffix_known=sk;
assign member_equal=reference_member==candidate_member;
assign suffix_equal=reference_suffix==candidate_suffix;
endmodule
