# Preserve only the reconstructed R3 identity result.  No parent/control state
# is frozen, and no new functional consumer or timing exception is introduced.
proc kvzap_entry_id_policy {} {
  if {![info exists ::env(KVZAP_DC_ENTRY_ID_DRIVER_POLICY)]} {return none}
  set policy $::env(KVZAP_DC_ENTRY_ID_DRIVER_POLICY)
  if {$policy ni {none r3_entry_id_driver_v1}} {error "unknown entry_id policy: $policy"}
  return $policy
}

proc kvzap_preserve_r3_entry_id_driver {top report_dir} {
  if {[kvzap_entry_id_policy] eq "none" || $top ne "route_a_control_projection"} {return}
  set parent [get_cells -quiet m2P3]
  if {[sizeof_collection $parent] != 1} {error "expected one implemented m2P3 parent"}
  set reference [get_attribute $parent ref_name]
  current_design $reference
  set ports [get_ports -quiet io_authority_transition_out_bits_entry_id*]
  if {[sizeof_collection $ports] != 24} {error "expected 24 authority entry_id ports"}
  set nets [get_nets -of_objects $ports]
  if {[sizeof_collection $nets] != 24} {error "expected 24 distinct entry_id result nets"}
  # Ordinary dont_touch on an unmapped net is ignored. This documented DC
  # variable preserves its input cone while still allowing technology mapping.
  set_app_var enable_keep_signal_dt_net true
  set_dont_touch $nets true
  current_design $top
  set handle [open [file join $report_dir entry_id_driver_policy.rpt] w]
  puts $handle "policy=r3_entry_id_driver_v1 reference=$reference result_nets=24"
  puts $handle "enable_keep_signal_dt_net=true; only selected nets have dont_touch"
  close $handle
}

proc kvzap_check_r3_entry_id_driver {top report_dir} {
  if {[kvzap_entry_id_policy] eq "none" || $top ne "route_a_control_projection"} {return}
  set reference [get_attribute [get_cells m2P3] ref_name]
  current_design $reference
  set ports [get_ports -quiet {io_authority_transition_out_bits_entry_id* io_publication_member_observation_bits_entry_id*}]
  if {[sizeof_collection $ports] != 48} {error "expected 48 entry_id output bits"}
  set handle [open [file join $report_dir entry_id_driver_check.rpt] w]
  set failures 0
  foreach_in_collection port $ports {
    set sources [all_fanin -to $port -flat -startpoints_only]
    set count [sizeof_collection $sources]
    puts $handle "[get_object_name $port] startpoints=$count"
    if {$count == 0} {incr failures}
  }
  puts $handle "checked_bits=48 undriven_bits=$failures"
  close $handle
  current_design $top
  if {$failures != 0} {error "entry_id output driver check failed: $failures bits"}
  puts "KVZAP_R3_ENTRY_ID_DRIVER_PASS bits=48"
}
