// RTL1.0.b non-synthesizable SVA binding registry.
//
// This binds the frozen assertion inventory to the structural top without
// pretending that stateful R1--R6 properties exist before their owners do.
// Each marker is validated against the Gate-RTL0 matrix and oracle manifest.
// RTL1.1 supplies the three R1 safety bodies as Chisel `assert` statements;
// this zero-port registry remains the stable top-level SVA/formal attachment.

module route_a_rtl1_0_assertion_binding_registry;
  localparam int unsigned ROUTE_A_RTL1_0_ASSERTION_COUNT = 15;

  // assertion-id: a_descriptor_unique_memory_path
  // r1-chisel-assertion: a_descriptor_unique_memory_path
  // assertion-id: a_metadata_publish_commit
  // r3-chisel-assertion: a_metadata_publish_commit
  // assertion-id: a_ready_low_nonmutation
  // r2-chisel-assertion: a_ready_low_nonmutation
  // assertion-id: a_descriptor_invalidate_before_free
  // assertion-id: a_numeric_fault_consumer
  // assertion-id: a_reset_stale_exclusion
  // r1-chisel-assertion: a_reset_stale_exclusion
  // assertion-id: a_global_retirement_membership
  // assertion-id: a_authority_conservation
  // assertion-id: a_fifo_credit_losslessness
  // r2-chisel-assertion: a_fifo_credit_losslessness
  // assertion-id: a_gqa_release
  // s2-chisel-assertion: a_gqa_release
  // assertion-id: a_stale_response
  // r1-chisel-assertion: a_stale_response
  // assertion-id: a_exactly_one_terminal
  // assertion-id: p_accepted_to_terminal
  // assertion-id: p_retire_to_ack
  // assertion-id: p_credit_return
endmodule

// The zero-port bind intentionally adds no implementation behavior. It gives
// later SVA/formal harnesses one stable attachment point at the frozen top.
bind route_a_kv_subsystem_top route_a_rtl1_0_assertion_binding_registry
  route_a_rtl1_0_assertion_binding_registry_i ();
