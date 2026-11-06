`timescale 1ps/1ps
module wcg1_wrapper_gate_tb;
reg clock=0, enable=0;
always #1000 clock=~clock;
wire actual, native_clock;
route_a_compact_word_clock_gate dut(.clock(clock),.enable(enable),.gated_clock(actual));
CKLNQD1BWP12T30P140LVT reference_gate(.CP(clock),.E(enable),.TE(1'b0),.Q(native_clock));
integer checks=0, index;
always @(posedge actual) if ($time%2000 != 1000) $fatal(1,"unexpected gated positive edge");
always @(negedge actual) if ($time%2000 != 0) $fatal(1,"truncated gated pulse");
task compare;
begin
 if (actual !== native_clock) $fatal(1,"WCG1 wrapper gate differs from native cell");
 checks=checks+1;
end
endtask
initial begin
 for(index=0;index<80;index=index+1) begin
   @(negedge clock); #800; enable=index[0]; #1; compare;
   @(posedge clock); #1; compare;
   #200; enable=~enable; #1; compare;
 end
 // The source can change through NBA on the same root edge. The low latch
 // must keep the pre-edge enable throughout HIGH, including its full pulse.
 for(index=0;index<32;index=index+1) begin
   @(negedge clock); #800; enable=index[0]; #1; compare;
   @(posedge clock); enable <= ~enable; #1; compare;
   #200; enable=~enable; #1; compare;
   @(negedge clock); #1; compare;
 end
 $display("WCG1_WRAPPER_GATE_NATIVE_EQUIVALENCE_PASS checks=%0d",checks);
 $finish;
end
endmodule
