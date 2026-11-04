// Regression: keep the internal identity interface correct even when the
// current parent consumes only the handshake, as in the production contour.
module route_a_m2_p3_wrapper(
  input [14:0] position, input [5:0] layer, input [2:0] head,
  input valid, output accepted,
  output [23:0] io_authority_transition_out_bits_entry_id,
  output [23:0] io_publication_member_observation_bits_entry_id);
  wire [23:0] entry_id = position * 24'd288 + layer * 24'd8 + head;
  assign io_authority_transition_out_bits_entry_id = entry_id;
  assign io_publication_member_observation_bits_entry_id = entry_id;
  assign accepted = valid;
endmodule
module route_a_control_projection(
  input [14:0] position, input [5:0] layer, input [2:0] head,
  input valid, output accepted);
  wire [23:0] authority_id, member_id;
  route_a_m2_p3_wrapper m2P3(position, layer, head, valid, accepted, authority_id, member_id);
endmodule
