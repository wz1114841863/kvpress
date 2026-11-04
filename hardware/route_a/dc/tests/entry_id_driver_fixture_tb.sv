`timescale 1ns/1ps
module entry_id_driver_fixture_tb;
  reg [14:0] position;
  reg [5:0] layer;
  reg [2:0] head;
  reg valid;
  wire accepted;
  integer i, l, h, tested = 0;
  integer positions [0:4];
  reg [23:0] expected;
  route_a_control_projection dut(position, layer, head, valid, accepted);
  task check;
    begin
      expected = position * 288 + layer * 8 + head;
      #1;
      if (dut.m2P3.io_authority_transition_out_bits_entry_id !== expected ||
          dut.m2P3.io_publication_member_observation_bits_entry_id !== expected ||
          accepted !== valid) $fatal(1, "entry_id/handshake mismatch");
      tested = tested + 1;
    end
  endtask
  initial begin
    positions[0]=0; positions[1]=1; positions[2]=127; positions[3]=128; positions[4]=32767;
    for (i=0; i<5; i=i+1)
      for (l=0; l<36; l=l+1)
        for (h=0; h<8; h=h+1) begin
          position=positions[i]; layer=l; head=h; valid=h%2; check;
        end
    for (i=0; i<4096; i=i+1) begin
      position=$urandom; layer=$urandom_range(35,0); head=$urandom_range(7,0);
      valid=$urandom_range(1,0); check;
    end
    $display("ENTRY_ID_MAPPED_SIM_PASS vectors=%0d", tested);
    $finish;
  end
endmodule
