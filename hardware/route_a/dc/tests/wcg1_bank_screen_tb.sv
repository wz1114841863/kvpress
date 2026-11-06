`timescale 1ps/1ps
module wcg1_bank_screen_tb;
reg clock=0;
always #1000 clock=~clock;
reg reset=1, claim_clear=0, accepted_event=0, binding_offered=0;
reg [5:0] write_layer=3;
reg [6:0] write_ordinal=0;
reg [78:0] member_in=0;
reg [79:0] suffix_in=0;
reg [5:0] mso_index=0, f_index=0, b_index=0, m_suffix_index=0;
reg [6:0] c_ordinal=0, member_count=64;
reg [63:0] c_reference=0;
reg [79:0] c_suffix=0;
reg c_stage_available=1, c_sink_ready=1, c_valid=0;
wire [78:0] r_mso, r_b, g_mso, g_b;
wire [63:0] r_c, r_f, g_c, g_f;
wire [79:0] r_ms, r_cs, g_ms, g_cs;
wire r_ready, r_issue, g_ready, g_issue;
`define INPUTS .clock(clock),.reset(reset),.claim_clear(claim_clear), \
 .accepted_event(accepted_event),.binding_offered(binding_offered), \
 .write_layer(write_layer),.write_ordinal(write_ordinal),.member_in(member_in),.suffix_in(suffix_in), \
 .mso_index(mso_index),.f_index(f_index),.b_index(b_index),.m_suffix_index(m_suffix_index), \
 .c_ordinal(c_ordinal),.member_count(member_count),.c_reference(c_reference),.c_suffix(c_suffix), \
 .c_stage_available(c_stage_available),.c_sink_ready(c_sink_ready),.c_valid(c_valid)
wcg1_reference ref_dut(`INPUTS,.mso_member(r_mso),.b_member(r_b),.c_member(r_c),.f_member(r_f),
 .m_suffix(r_ms),.c_suffix_read(r_cs),.c_ready(r_ready),.c_issue(r_issue));
wcg1_gated new_dut(`INPUTS,.mso_member(g_mso),.b_member(g_b),.c_member(g_c),.f_member(g_f),
 .m_suffix(g_ms),.c_suffix_read(g_cs),.c_ready(g_ready),.c_issue(g_issue));
`undef INPUTS
reg [78:0] expected_m [0:63];
reg [79:0] expected_s [0:63];
reg [63:0] known_m=0, known_s=0;
integer checks=0, i, j, seed=32'h1106cafe;
always @(posedge clock) begin
 if (ref_dut.launch_fire && ref_dut.launch_layer==3 && ref_dut.launch_ordinal<64) begin
   known_m[ref_dut.launch_ordinal] <= 1;
   expected_m[ref_dut.launch_ordinal] <= ref_dut.launch_member;
   if (ref_dut.launch_binding) begin
     known_s[ref_dut.launch_ordinal] <= 1;
     expected_s[ref_dut.launch_ordinal] <= ref_dut.launch_suffix;
   end
 end
end
generate for(genvar row=0;row<64;row=row+1) begin: compare
 always @(negedge clock) begin
   if (known_m[row] && (ref_dut.members[row] !== expected_m[row] || new_dut.members[row] !== expected_m[row]))
     $fatal(1,"WCG1_BANK_FAIL member row=%0d",row);
   if (known_s[row] && (ref_dut.suffixes[row] !== expected_s[row] || new_dut.suffixes[row] !== expected_s[row]))
     $fatal(1,"WCG1_BANK_FAIL suffix row=%0d",row);
 end
end endgenerate
task compare_outputs;
 begin
   if ({r_mso,r_b,r_c,r_f,r_ms,r_cs,r_ready,r_issue} !== {g_mso,g_b,g_c,g_f,g_ms,g_cs,g_ready,g_issue})
     $fatal(1,"WCG1_BANK_FAIL concurrent read/ready");
   checks=checks+1;
 end
endtask
initial begin
 repeat(2) @(negedge clock);
 #100; reset=0;
 for(i=0;i<64;i=i+1) begin
   @(negedge clock); #100;
   accepted_event=1; binding_offered=1; write_ordinal=i;
   member_in={15'h7fff,64'hfedcba9876543210}^i;
   suffix_in=80'hfffffedcba9876543210^i;
 end
 @(negedge clock); #100; accepted_event=0;
 repeat(2) @(negedge clock);
 #100;
 if (&known_m !== 1'b1 || &known_s !== 1'b1) $fatal(1,"not all rows initialized");
 for(i=0;i<384;i=i+1) begin
   @(negedge clock); #100;
   // Boundary/root launch activity exercises same-edge data and E changes.
   accepted_event=i%5!=0; binding_offered=i%3!=0;
   write_layer=i%11==0 ? 6'd4:6'd3;
   write_ordinal=i%17==0 ? 7'd64 : i%64;
   member_in={$random(seed),$random(seed),$random(seed)};
   suffix_in={$random(seed),$random(seed),$random(seed)};
   reset=i==150; claim_clear=i==230;
   mso_index=i%64; f_index=(i+7)%64; b_index=(i+23)%64; m_suffix_index=(i+37)%64;
   c_ordinal=i%13==0 ? 7'd64 : (i+19)%64;
   c_valid=i[0]; c_sink_ready=i[1]; c_stage_available=i%7!=0;
   c_reference=expected_m[c_ordinal[5:0]][63:0];
   c_suffix=expected_s[c_ordinal[5:0]] ^ (i%9==0 ? 80'b1:80'b0);
   #100; compare_outputs;
   @(posedge clock); #100; compare_outputs;
 end
 @(negedge clock); #100; accepted_event=0;
 repeat(2) @(negedge clock);
 #100;
 $display("WCG1_BANK_SCREEN_UNIT_PASS rows=64 data_bits=10176 output_checks=%0d",checks);
 $finish;
end
endmodule
