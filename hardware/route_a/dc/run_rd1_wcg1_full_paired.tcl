# Reuse the original compile procedure unchanged; add native-gate inventory
# and separate propagated-clock/hold snapshots after its primary result.
proc wcg1_inventory {phase} {
  set gates [get_cells -hier -quiet -filter {ref_name =~ CKLNQ*}]
  set count 0
  if {$::env(KVZAP_DC_TOP) eq "route_a_control_projection"} {set count 4608}
  if {[sizeof_collection $gates] != $count} {error "native gate count $phase"}
  if {$count > 0} {
    foreach pin {CP E TE Q} {
      if {[sizeof_collection [filter_collection [get_pins -of_objects $gates] "full_name =~ */$pin"]] != 4608} {error "native gate pin $pin missing"}
    }
    if {$phase eq "post-link"} {
      if {![set_size_only -all_instances $gates true]} {error "native size-only status"}
      set libgate [get_lib_cells */CKLNQD1BWP12T30P140LVT]
      if {[get_attribute $libgate clock_gating_integrated_cell] ne "latch_posedge_precontrol"} {error "native characterization mismatch"}
    } else {
      set data [get_cells -hier -quiet -filter {full_name =~ m2P3/memberWord*_reg* || full_name =~ m2P3/suffixWord*_reg*}]
      if {[sizeof_collection $data] != 366336} {error "compact data inventory changed: [sizeof_collection $data]"}
    }
  }
  puts "KVZAP_RD1_WCG1_NATIVE_INVENTORY_PASS phase=$phase gates=$count"
}

proc wcg1_snapshot {stage propagated} {
  set dest [file join $::env(KVZAP_DC_REPORT_DIR) $stage]
  file mkdir $dest
  update_timing
  wcg1_inventory post-compile
  kvzap_dc_require_array_proxies $::env(KVZAP_DC_ARRAY_PROXY_MODULE_LIST) post-compile
  kvzap_check_r3_entry_id_driver $::env(KVZAP_DC_TOP) $dest
  redirect [file join $dest area.rpt] {report_area -hierarchy -nosplit}
  redirect [file join $dest qor.rpt] {report_qor}
  redirect [file join $dest references.rpt] {report_reference -hierarchy -nosplit}
  redirect [file join $dest check_design.rpt] {check_design}
  redirect [file join $dest check_timing.rpt] {check_timing}
  redirect [file join $dest constraints.rpt] {report_constraint -all_violators -significant_digits 6}
  redirect [file join $dest clocks.rpt] {report_clock -attributes -skew -nosplit}
  redirect [file join $dest clock_net.rpt] {report_net -nosplit [get_nets -of_objects [get_ports clock]]}
  redirect [file join $dest gating.rpt] {report_clock_gating -gating_elements -gated -verbose -nosplit}
  redirect [file join $dest setup.rpt] {report_timing -delay_type max -path_type full_clock_expanded -max_paths 20 -significant_digits 6 -nosplit}
  redirect [file join $dest hold.rpt] {report_timing -delay_type min -path_type full_clock_expanded -max_paths 20 -significant_digits 6 -nosplit}
  set f [open [file join $dest metrics.tsv] w]; puts $f "metric\tvalue"
  puts $f "period_ns\t[get_attribute [get_clocks kvzap_control_clk] period]"
  puts $f "propagated\t$propagated"
  puts $f "max_slack_ns\t[get_attribute [index_collection [get_timing_paths -delay_type max -max_paths 1] 0] slack]"
  puts $f "min_slack_ns\t[get_attribute [index_collection [get_timing_paths -delay_type min -max_paths 1] 0] slack]"
  set gates [get_cells -hier -quiet -filter {ref_name =~ CKLNQ*}]
  puts $f "clock_gates\t[sizeof_collection $gates]"
  if {$::env(KVZAP_DC_TOP) eq "route_a_control_projection"} {
    set data [get_cells -hier -quiet -filter {full_name =~ m2P3/memberWord*_reg* || full_name =~ m2P3/suffixWord*_reg*}]
    puts $f "data_flops\t[sizeof_collection $data]"
    set enables [filter_collection [get_pins -of_objects $gates] {full_name =~ */E}]
    redirect [file join $dest gate_setup.rpt] {report_timing -to $enables -delay_type max -path_type full_clock_expanded -max_paths 20 -significant_digits 6 -nosplit}
    redirect [file join $dest gate_hold.rpt] {report_timing -to $enables -delay_type min -path_type full_clock_expanded -max_paths 20 -significant_digits 6 -nosplit}
    if {$propagated} {
      set captures [filter_collection [get_pins -of_objects $data] {full_name =~ */D}]
      redirect [file join $dest gated_data_hold.rpt] {report_timing -to $captures -delay_type min -path_type full_clock_expanded -max_paths 20 -nets -input_pins -transition_time -significant_digits 6 -nosplit}
    }
  }
  close $f
  write -format ddc -hierarchy -output [file join $dest mapped.ddc]
  write -format verilog -hierarchy -output [file join $dest mapped.v]
  write_sdc [file join $dest mapped.sdc]
  puts "KVZAP_RD1_WCG1_STAGE_PASS top=$::env(KVZAP_DC_TOP) stage=$stage"
}

if {[catch {
  set_host_options -max_cores 2
  set f [open [file join $::env(KVZAP_DC_SCRIPT_DIR) run_kvzap_control_projection_dc_feasibility.tcl] r]
  set original [read $f]; close $f
  set marker "if \{\[catch \{kvzap_dc_main\}"
  set boundary [string first $marker $original]
  if {$boundary < 0} {error "original procedure boundary missing"}
  eval [string range $original 0 [expr {$boundary - 1}]]
  rename kvzap_dc_require_array_proxies wcg1_original_proxies
  proc kvzap_dc_require_array_proxies {modules phase} {
    wcg1_original_proxies $modules $phase
    wcg1_inventory $phase
    if {$phase eq "post-link" && [info exists ::env(KVZAP_WCG1_BINDING_ONLY)] && $::env(KVZAP_WCG1_BINDING_ONLY) eq "1"} {
      if {$::env(KVZAP_DC_TOP) ne "route_a_control_projection"} {error "binding preflight requires real Route-A top"}
      source [file join $::env(KVZAP_DC_SCRIPT_DIR) constraints_control_projection.tcl]
      kvzap_apply_control_projection_constraints
      redirect [file join $::env(KVZAP_DC_REPORT_DIR) link_check.rpt] {check_design}
      puts "KVZAP_RD1_WCG1_FULL_NATIVE_BINDING_PASS gates=4608 proxies=4 period_ns=2"
      exit 0
    }
  }
  set ::env(KVZAP_DC_ARRAY_PROXY_MODULE_LIST) [split $::env(KVZAP_DC_ARRAY_PROXY_MODULES) ,]
  # The original compile, constraints and entry_id policy execute unmodified.
  kvzap_dc_main
  wcg1_snapshot primary_raw 0
  set_input_transition 0.05 [get_ports clock]
  set_propagated_clock [all_clocks]
  wcg1_snapshot propagated_raw 1
  set_fix_hold [all_clocks]
  compile -only_hold_time
  wcg1_snapshot propagated_hold_repaired 1
  puts "KVZAP_RD1_WCG1_SIDE_PASS top=$::env(KVZAP_DC_TOP)"
  exit 0
} message options]} {
  puts stderr "KVZAP_RD1_WCG1_SIDE_FAIL $message"
  if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
  exit 1
}
