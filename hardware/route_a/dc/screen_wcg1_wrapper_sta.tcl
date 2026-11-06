# Real standalone wrapper, matched 2-ns numerical profile and propagated clocks.
proc wcg1_area {path} {
  set f [open $path r]; set text [read $f]; close $f
  set values {}
  foreach label {{Total cell area} {Combinational area} {Noncombinational area}} {
    set found {}
    foreach line [split $text \n] {
      if {[regexp "^${label}:\\s+(\\S+)\\s*$" $line all v]} {lappend found $v}
    }
    if {[llength $found] != 1 || ![string is double -strict [lindex $found 0]]} {error "missing native area $label"}
    lappend values [lindex $found 0]
  }
  lassign $values total comb seq
  if {$total <= 0 || abs($total-$comb-$seq)>0.00001} {error "native area disagreement"}
  return $values
}
proc wcg1_slack {paths} {
  if {[sizeof_collection $paths] == 0} {error "missing required timing path"}
  return [get_attribute [index_collection $paths 0] slack]
}
proc wcg1_data {} {
  if {$::env(KVZAP_WCG1_SIDE) eq "gated"} {
    return [get_cells -hier -quiet -filter {full_name =~ *memberWord*_reg* || full_name =~ *suffixWord*_reg*}]
  }
  return [get_cells -hier -quiet -filter {full_name =~ *membershipEntries*_reg* || full_name =~ *membershipPayloadBindings*_reg*}]
}
proc wcg1_entry_check {dest} {
  set ports [get_ports -quiet {io_authority_transition_out_bits_entry_id* io_publication_member_observation_bits_entry_id*}]
  if {[sizeof_collection $ports] != 48} {error "entry_id output width changed"}
  set f [open [file join $dest entry_id.rpt] w]
  set failures 0
  foreach_in_collection p $ports {
    set n [sizeof_collection [all_fanin -flat -startpoints_only -to $p]]
    puts $f "[get_object_name $p] startpoints=$n"
    if {$n == 0} {incr failures}
  }
  puts $f "checked_bits=48 undriven_bits=$failures"; close $f
  if {$failures != 0} {error "entry_id lost driver"}
}
proc wcg1_snapshot {stage} {
  set dest [file join $::env(KVZAP_WCG1_SIDE_OUT) $stage]; file mkdir $dest
  update_timing
  set data [wcg1_data]
  if {[sizeof_collection $data] != 366336} {error "data bits lost or inventory naming mismatch: [sizeof_collection $data]"}
  set gates [get_cells -hier -quiet -filter {ref_name =~ CKLNQ*}]
  set expected 0
  if {$::env(KVZAP_WCG1_SIDE) eq "gated"} {set expected 4608}
  if {[sizeof_collection $gates] != $expected} {error "native gate inventory changed"}
  if {[sizeof_collection [get_cells -hier -filter {ref_name == route_a_p3_stage_array_boundary}]] != 1} {error "P3 boundary lost"}
  wcg1_entry_check $dest
  redirect [file join $dest area.rpt] {report_area -hierarchy -nosplit}
  redirect [file join $dest references.rpt] {report_reference -hierarchy -nosplit}
  redirect [file join $dest qor.rpt] {report_qor}
  redirect [file join $dest check_design.rpt] {check_design}
  redirect [file join $dest check_timing.rpt] {check_timing}
  redirect [file join $dest constraints.rpt] {report_constraint -all_violators -significant_digits 6}
  redirect [file join $dest clocks.rpt] {report_clock -attributes -skew -nosplit}
  redirect [file join $dest gating.rpt] {report_clock_gating -gating_elements -gated -verbose -nosplit}
  redirect [file join $dest clock_net.rpt] {report_net -nosplit [get_nets -of_objects [get_ports clock]]}
  redirect [file join $dest setup.rpt] {report_timing -delay_type max -path_type full_clock_expanded -max_paths 20 -nets -input_pins -transition_time -capacitance -significant_digits 6 -nosplit}
  redirect [file join $dest hold.rpt] {report_timing -delay_type min -path_type full_clock_expanded -max_paths 20 -nets -input_pins -transition_time -capacitance -significant_digits 6 -nosplit}
  set f [open [file join $dest metrics.tsv] w]; puts $f "metric\tvalue"
  puts $f "data_flops\t[sizeof_collection $data]"
  puts $f "clock_gates\t[sizeof_collection $gates]"
  puts $f "period_ns\t[get_attribute [get_clocks kvzap_control_clk] period]"
  puts $f "propagated\t[get_attribute [get_clocks kvzap_control_clk] propagated_clock]"
  lassign [wcg1_area [file join $dest area.rpt]] total comb seq
  puts $f "total_area\t$total"; puts $f "combinational_area\t$comb"; puts $f "sequential_area\t$seq"
  puts $f "max_slack_ns\t[wcg1_slack [get_timing_paths -delay_type max -max_paths 1]]"
  puts $f "min_slack_ns\t[wcg1_slack [get_timing_paths -delay_type min -max_paths 1]]"
  if {$expected > 0} {
    set enables [filter_collection [get_pins -of_objects $gates] {full_name =~ */E}]
    if {[sizeof_collection $enables] != 4608} {error "missing real native E pins"}
    redirect [file join $dest gate_setup.rpt] {report_timing -to $enables -delay_type max -path_type full_clock_expanded -max_paths 20 -significant_digits 6 -nosplit}
    redirect [file join $dest gate_hold.rpt] {report_timing -to $enables -delay_type min -path_type full_clock_expanded -max_paths 20 -significant_digits 6 -nosplit}
    set captures [filter_collection [get_pins -of_objects $data] {full_name =~ */D}]
    redirect [file join $dest gated_data_hold.rpt] {report_timing -to $captures -delay_type min -path_type full_clock_expanded -max_paths 20 -nets -input_pins -transition_time -significant_digits 6 -nosplit}
    puts $f "gate_max_slack_ns\t[wcg1_slack [get_timing_paths -to $enables -delay_type max -max_paths 1]]"
    puts $f "gate_min_slack_ns\t[wcg1_slack [get_timing_paths -to $enables -delay_type min -max_paths 1]]"
  }
  close $f
  write -format ddc -hierarchy -output [file join $dest mapped.ddc]
  write -format verilog -hierarchy -output [file join $dest mapped.v]
  write_sdc [file join $dest mapped.sdc]
  puts "KVZAP_WCG1_WRAPPER_STAGE_PASS side=$::env(KVZAP_WCG1_SIDE) stage=$stage"
}
if {[catch {
  set out $::env(KVZAP_WCG1_SIDE_OUT); file mkdir $out
  set src $::env(KVZAP_WCG1_INPUTS); set side $::env(KVZAP_WCG1_SIDE)
  set_host_options -max_cores 2
  define_design_lib WORK -path [file join $out WORK]
  set_app_var target_library [list $::env(KVZAP_DC_TARGET_LIBRARY)]
  set_app_var link_library [concat [list *] $target_library]
  set f [open [file join $src $side sources.f] r]; set files {}
  foreach n [split [read $f] \n] {if {$n ne ""} {lappend files [file join $src $side $n]}}
  close $f
  analyze -format sverilog -define SYNTHESIS $files
  elaborate route_a_m2_p3_wrapper
  current_design route_a_m2_p3_wrapper
  if {![link]} {error "wrapper link failed"}
  source [file join $::env(KVZAP_WCG1_SCRIPTS) constraints_control_projection.tcl]
  kvzap_apply_control_projection_constraints
  set_input_transition 0.05 [get_ports clock]
  set_propagated_clock [all_clocks]
  set proxy [get_cells -hier -quiet -filter {ref_name == route_a_p3_stage_array_boundary}]
  if {[sizeof_collection $proxy] != 1} {error "expected exactly one P3 interior proxy"}
  set_dont_touch $proxy true; set_ungroup $proxy false
  set gates [get_cells -hier -quiet -filter {ref_name =~ CKLNQ*}]
  set count 0
  if {$side eq "gated"} {set count 4608}
  if {[sizeof_collection $gates] != $count} {error "native gate link incomplete"}
  if {$count > 0} {
    # The inline module is multiply instantiated. DC 2018 requires explicit
    # all-instance application to its shared native leaf definition.
    if {![set_size_only -all_instances $gates true]} {error "native gate size-only application failed"}
    set enables [filter_collection [get_pins -of_objects $gates] {full_name =~ */E}]
    if {[sizeof_collection $enables] != 4608} {error "native enable pins missing"}
    set libgate [get_lib_cells */CKLNQD1BWP12T30P140LVT]
    if {[get_attribute $libgate clock_gating_integrated_cell] ne "latch_posedge_precontrol"} {error "wrong native gate characterization"}
  }
  set_app_var enable_keep_signal_dt_net true
  set identity [get_ports io_authority_transition_out_bits_entry_id*]
  if {[sizeof_collection $identity] != 24} {error "identity preservation width"}
  set_dont_touch [get_nets -of_objects $identity] true
  redirect [file join $out preflight_link.rpt] {check_design}
  puts "KVZAP_WCG1_WRAPPER_NATIVE_BINDING_PASS side=$side gates=$count P3_proxies=1"
  if {[info exists ::env(KVZAP_WCG1_PREFLIGHT_ONLY)] && $::env(KVZAP_WCG1_PREFLIGHT_ONLY) eq "1"} {exit 0}
  compile -map_effort medium
  wcg1_snapshot raw
  set_fix_hold [all_clocks]
  compile -only_hold_time
  wcg1_snapshot repaired
  puts "KVZAP_WCG1_WRAPPER_SIDE_RUN_PASS side=$side"
  exit 0
} message options]} {
  puts stderr "KVZAP_WCG1_WRAPPER_SIDE_FAIL $message"
  if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
  exit 1
}
