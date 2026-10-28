# Parameterized constraints for one paired KVZap control-projection top.
#
# Source only after analyze/elaborate/current_design in a separately approved
# DC-feasibility Tcl.  This file makes no period, I/O, macro, or PPA choice:
# all numerical values are required from the caller's frozen run manifest.
# The control projections use one ordinary synchronous `clock`/`reset` domain;
# reset is deliberately timed as an input rather than hidden by a false path.

proc kvzap_dc_require_positive_number {name} {
  if {![info exists ::env($name)] || [string trim $::env($name)] eq ""} {
    error "$name is required by constraints_control_projection.tcl"
  }
  if {![string is double -strict $::env($name)] || $::env($name) <= 0.0} {
    error "$name must be a positive number, got '$::env($name)'"
  }
  return $::env($name)
}

proc kvzap_apply_control_projection_constraints {} {
  set period [kvzap_dc_require_positive_number KVZAP_DC_CLOCK_PERIOD_NS]
  set setup_uncertainty [kvzap_dc_require_positive_number KVZAP_DC_CLOCK_SETUP_UNCERTAINTY_NS]
  set hold_uncertainty [kvzap_dc_require_positive_number KVZAP_DC_CLOCK_HOLD_UNCERTAINTY_NS]
  set input_delay [kvzap_dc_require_positive_number KVZAP_DC_INPUT_DELAY_NS]
  set output_delay [kvzap_dc_require_positive_number KVZAP_DC_OUTPUT_DELAY_NS]
  set input_transition [kvzap_dc_require_positive_number KVZAP_DC_INPUT_TRANSITION_NS]
  set output_load [kvzap_dc_require_positive_number KVZAP_DC_OUTPUT_LOAD_PF]

  set clock_port [get_ports -quiet clock]
  set reset_port [get_ports -quiet reset]
  if {[sizeof_collection $clock_port] != 1} {
    error "expected exactly one top-level port named clock"
  }
  if {[sizeof_collection $reset_port] != 1} {
    error "expected exactly one top-level port named reset"
  }

  create_clock -name kvzap_control_clk -period $period $clock_port
  set_clock_uncertainty -setup $setup_uncertainty [get_clocks kvzap_control_clk]
  set_clock_uncertainty -hold $hold_uncertainty [get_clocks kvzap_control_clk]

  # Both top boundaries are synchronous control interfaces.  This constrains
  # reset and every typed external service input instead of using a false path.
  set data_inputs [remove_from_collection [all_inputs] $clock_port]
  if {[sizeof_collection $data_inputs] > 0} {
    set_input_delay $input_delay -clock kvzap_control_clk $data_inputs
    set_input_transition $input_transition $data_inputs
  }
  set outputs [all_outputs]
  if {[sizeof_collection $outputs] > 0} {
    set_output_delay $output_delay -clock kvzap_control_clk $outputs
    set_load $output_load $outputs
  }

  puts "KVZAP_DC_CONSTRAINTS_APPLIED clock=clock reset=timed-synchronous period_ns=$period"
}
