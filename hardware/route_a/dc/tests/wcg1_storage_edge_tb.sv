`timescale 1ps/1ps
// Library-cell storage unit only. This is not the production wrapper or STA.
module wcg1_storage_edge_tb;
  localparam ROWS = 8;
  reg clock = 0;
  always #1000 clock = ~clock;
  reg reset = 1;
  reg admission_valid = 0, admission_ready = 0, binding_valid = 0;
  reg [2:0] write_row = 0;
  reg [78:0] member_d = 0;
  reg [79:0] suffix_d = 0;
  wire [78:0] member_ref [0:ROWS-1], member_new [0:ROWS-1];
  wire [79:0] suffix_ref [0:ROWS-1], suffix_new [0:ROWS-1];
  reg [78:0] expected_member [0:ROWS-1];
  reg [79:0] expected_suffix [0:ROWS-1];
  reg [ROWS-1:0] known_member = 0, known_suffix = 0;
  reg [ROWS-1:0] present = 0, binding_present = 0;
  reg [2:0] reader [0:3];
  reg c_valid = 0, c_sink_ready = 1;
  reg [79:0] c_expected = 0;
  wire c_legal_ref = present[reader[1]] && binding_present[reader[1]] &&
    suffix_ref[reader[1]] == c_expected;
  wire c_legal_new = present[reader[1]] && binding_present[reader[1]] &&
    suffix_new[reader[1]] == c_expected;
  wire c_ready_ref = c_legal_ref && c_sink_ready;
  wire c_ready_new = c_legal_new && c_sink_ready;
  wire c_issue_ref = c_legal_ref && c_valid;
  wire c_issue_new = c_legal_new && c_valid;
  integer checks = 0;
  integer pulse_checks = 0;
  integer seed = 32'h193bca17;
  reg bare_and, merged_enable, clock_skew;

  generate for (genvar row = 0; row < ROWS; row = row + 1) begin: rows
    wire member_e = admission_valid && admission_ready && write_row == row;
    wire suffix_e = member_e && binding_valid;
    wire member_g, suffix_g, member_cp, suffix_cp;
    wire member_cp_delayed, suffix_cp_delayed;
    wire native_member_g, native_suffix_g;
    CKLNQD1BWP12T30P140LVT member_gate(
      .TE(1'b0), .E(member_e), .CP(clock), .Q(native_member_g));
    CKLNQD1BWP12T30P140LVT suffix_gate(
      .TE(1'b0), .E(merged_enable ? member_e : suffix_e), .CP(clock), .Q(native_suffix_g));
    assign member_g = bare_and ? (clock & member_e) : native_member_g;
    assign suffix_g = bare_and ? (clock & suffix_e) : native_suffix_g;
    always @(posedge member_g or posedge suffix_g) begin
      if ($time % 2000 != 1000)
        $fatal(1, "WCG1_COMPARE_FAIL case=high_phase_enable_rise unexpected_clock_edge");
      pulse_checks = pulse_checks + 1;
    end
    always @(negedge member_g or negedge suffix_g) begin
      if ($time % 2000 != 0)
        $fatal(1, "WCG1_COMPARE_FAIL truncated_clock_pulse");
      pulse_checks = pulse_checks + 1;
    end
    // Delayed-clock mode is a separate hold/skew diagnostic, not SDF timing.
    assign #(50) member_cp_delayed = member_g;
    assign #(50) suffix_cp_delayed = suffix_g;
    assign member_cp = clock_skew ? member_cp_delayed : member_g;
    assign suffix_cp = clock_skew ? suffix_cp_delayed : suffix_g;
    for (genvar bit_index = 0; bit_index < 79; bit_index = bit_index + 1) begin: m
      EDFQD2BWP12T30P140LVT reference_ff(
        .D(member_d[bit_index]), .E(member_e), .CP(clock), .Q(member_ref[row][bit_index]));
      DFQD2BWP12T30P140LVT candidate_ff(
        .D(member_d[bit_index]), .CP(member_cp), .Q(member_new[row][bit_index]));
    end
    for (genvar bit_index = 0; bit_index < 80; bit_index = bit_index + 1) begin: s
      EDFQD2BWP12T30P140LVT reference_ff(
        .D(suffix_d[bit_index]), .E(suffix_e), .CP(clock), .Q(suffix_ref[row][bit_index]));
      DFQD2BWP12T30P140LVT candidate_ff(
        .D(suffix_d[bit_index]), .CP(suffix_cp), .Q(suffix_new[row][bit_index]));
    end
  end endgenerate

  // Unreset data flops must retain their values across control reset.
  always @(posedge clock) begin
    if (admission_valid && admission_ready) begin
      known_member[write_row] <= 1;
      expected_member[write_row] <= member_d;
      if (binding_valid) begin
        known_suffix[write_row] <= 1;
        expected_suffix[write_row] <= suffix_d;
      end
    end
    if (reset) begin
      present <= 0;
      binding_present <= 0;
    end else if (admission_valid && admission_ready) begin
      present[write_row] <= 1;
      if (binding_valid) binding_present[write_row] <= 1;
    end
  end

  task check_storage(input [255:0] label_text);
    integer row, port_index;
    begin
      for (row = 0; row < ROWS; row = row + 1) begin
        if (known_member[row] &&
            (member_ref[row] !== expected_member[row] || member_new[row] !== expected_member[row]))
          $fatal(1, "WCG1_COMPARE_FAIL member row=%0d case=%0s ref=%h new=%h expected=%h", row, label_text,
                 member_ref[row], member_new[row], expected_member[row]);
        if (known_suffix[row] &&
            (suffix_ref[row] !== expected_suffix[row] || suffix_new[row] !== expected_suffix[row]))
          $fatal(1, "WCG1_COMPARE_FAIL suffix row=%0d case=%0s", row, label_text);
      end
      for (port_index = 0; port_index < 4; port_index = port_index + 1)
        if (known_member[reader[port_index]] && member_ref[reader[port_index]] !== member_new[reader[port_index]])
          $fatal(1, "WCG1_READ_PORT_FAIL port=%0d", port_index);
      if (c_ready_ref !== c_ready_new || c_issue_ref !== c_issue_new)
        $fatal(1, "WCG1_READY_FAIL valid=%b", c_valid);
      checks = checks + 1;
    end
  endtask

  task cycle(input integer row, input reg valid, input reg ready, input reg bound,
             input [78:0] m, input [79:0] s);
    begin
      @(negedge clock); #100;
      write_row = row; admission_valid = valid; admission_ready = ready;
      binding_valid = bound; member_d = m; suffix_d = s;
      reader[0] = row; reader[1] = (row + 1) % ROWS;
      reader[2] = (row + 3) % ROWS; reader[3] = (row + 6) % ROWS;
      #100; check_storage("pre_edge");
      @(posedge clock); #100; check_storage("post_edge");
    end
  endtask

  integer row, bit_index, iteration;
  reg [78:0] m_pattern;
  reg [79:0] s_pattern;
  initial begin
    bare_and = $test$plusargs("BARE_AND");
    merged_enable = $test$plusargs("MERGED_ENABLE");
    clock_skew = $test$plusargs("CLOCK_SKEW");
    reader[0] = 0; reader[1] = 1; reader[2] = 2; reader[3] = 3;
    cycle(0, 0, 0, 0, 0, 0);
    reset = 0;
    for (row = 0; row < ROWS; row = row + 1)
      cycle(row, 1, 1, 1, {15'h7000, 64'h8000000000000000} ^ row,
            {5'h1f, 64'h8000000000000000, 8'hff, 3'h7} ^ row);
    // Optional binding must leave the old suffix untouched.
    for (row = 0; row < ROWS; row = row + 1)
      cycle(row, 1, 1, 0, {79{1'b1}} ^ row, 80'h0123456789abcdef0123);
    cycle(0, 0, 1, 1, 79'h1, 80'h2);
    cycle(0, 1, 0, 1, 79'h3, 80'h4);
    // Late low-phase assertion, before the next edge; no extra-cycle write.
    @(negedge clock); #700;
    admission_valid = 1; admission_ready = 1; binding_valid = 1;
    write_row = 2; member_d = 79'h123; suffix_d = 80'h456;
    @(posedge clock); #100; check_storage("late_low_enable");
    @(negedge clock); #700;
    admission_valid = 0; member_d = 79'hbad; suffix_d = 80'hbad;
    @(posedge clock); #100; check_storage("late_low_disable");
    // Changing data and enabling another row during HIGH must not write it.
    @(negedge clock); #100; admission_valid = 0;
    @(posedge clock); #100;
    write_row = 3; member_d = 79'h111; suffix_d = 80'h222;
    admission_valid = 1; binding_valid = 1;
    #100; check_storage("high_phase_enable_rise");
    @(negedge clock); #100;
    @(posedge clock); #100; check_storage("next_edge_after_high_change");
    admission_valid = 0; member_d = 79'h333; suffix_d = 80'h444;
    #100; check_storage("high_phase_enable_fall");
    // Source-flop NBA change on the root edge: ideal functional models only.
    @(negedge clock); #100;
    write_row = 4; admission_valid = 1; binding_valid = 1;
    member_d = 79'h555; suffix_d = 80'h666;
    @(posedge clock);
    member_d <= 79'h777; suffix_d <= 80'h888; admission_valid <= 0;
    #100; check_storage("root_edge_nba_data_change");
    // Every member/suffix bit, including both upper 64-bit-field bits.
    for (bit_index = 0; bit_index < 80; bit_index = bit_index + 1) begin
      m_pattern = 79'b1 << (bit_index % 79);
      s_pattern = 80'b1 << bit_index;
      cycle(bit_index % ROWS, 1, 1, 1, m_pattern, s_pattern);
    end
    reset = 1;
    cycle(0, 0, 0, 0, 79'h1234, 80'h5678);
    // Raw data Reg has no reset; preserve its original enabled-write rule.
    cycle(5, 1, 1, 1, 79'h13579, 80'h24680);
    reset = 0;
    cycle(0, 1, 1, 0, 79'h9999, 80'haaaa);
    for (iteration = 0; iteration < 256; iteration = iteration + 1) begin
      m_pattern = {$random(seed), $random(seed), $random(seed)};
      s_pattern = {$random(seed), $random(seed), $random(seed)};
      cycle(iteration % ROWS, iteration % 5 != 0, iteration % 7 != 0,
            iteration % 3 != 0, m_pattern, s_pattern);
      c_valid = iteration[0]; c_sink_ready = iteration[1];
      c_expected = expected_suffix[reader[1]] ^ (iteration[2] ? 80'b1 : 80'b0);
      #100; check_storage("independent_reads_valid_low_ready");
    end
    if (bare_and || merged_enable || clock_skew)
      $fatal(1, "WCG1_NEGATIVE_CONTROL_NOT_DETECTED");
    $display("WCG1_EDGE_UNIT_PASS rows=%0d member_width=79 suffix_width=80 checks=%0d pulse_checks=%0d", ROWS, checks, pulse_checks);
    $finish;
  end
endmodule
