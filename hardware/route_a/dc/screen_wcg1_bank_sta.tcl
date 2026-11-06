# Matched bank-only WCG1 experiment. No production RTL or full paired DC.
proc wcg1_native_area_values {path} {
  set f [open $path r]
  set text [read $f]
  close $f
  set values {}
  foreach label {{Total cell area} {Combinational area} {Noncombinational area}} {
    set matches {}
    foreach line [split $text \n] {
      if {[regexp "^${label}:\\s+(\\S+)\\s*$" $line all value]} {lappend matches $value}
    }
    if {[llength $matches] != 1} {error "missing/duplicate native area field: $label"}
    set value [lindex $matches 0]
    if {![regexp {^[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?$} $value] || ![string is double -strict $value]} {
      error "invalid native area field: $label"
    }
    lappend values $value
  }
  lassign $values total comb seq
  if {$total <= 0 || abs($total - $comb - $seq) > 0.000002} {error "inconsistent native area components"}
  return $values
}
# End native area reader (also tested using ordinary Tcl, without DC).
if {[catch {
  set out $::env(KVZAP_WCG1_SIDE_OUT)
  set side $::env(KVZAP_WCG1_SIDE)
  set src $::env(KVZAP_WCG1_INPUTS)
  file mkdir $out
  define_design_lib WORK -path [file join $out WORK]
  set_app_var target_library [list $::env(KVZAP_DC_TARGET_LIBRARY)]
  set_app_var link_library [concat [list *] $target_library]
  analyze -format verilog [file join $src ${side}.v]
  elaborate wcg1_$side
  current_design wcg1_$side
  if {![link]} {error "link failed"}
  source [file join $src constraints_control_projection.tcl]
  kvzap_apply_control_projection_constraints
  # Matched addition to the numerical fair profile: propagate actual cell arcs
  # on BOTH sides and specify the same 50-ps root clock port transition.
  set_input_transition 0.05 [get_ports clock]
  set_propagated_clock [all_clocks]
  set storage [get_cells {member_ff_* suffix_ff_*}]
  if {[sizeof_collection $storage] != 10176} {error "incomplete storage before mapping"}
  # Preserve the compared storage architecture, allowing drive-strength sizing.
  set_size_only $storage true
  if {$side eq "gated"} {
    set gates [get_cells {*_gate_*}]
    if {[sizeof_collection $gates] != 128} {error "incomplete gate inventory"}
    set_size_only $gates true
  }
  if {[info exists ::env(KVZAP_WCG1_PREFLIGHT_ONLY)] && $::env(KVZAP_WCG1_PREFLIGHT_ONLY) eq "1"} {
    if {$side ne "gated"} {error "preflight requires gated side"}
    set enables [get_pins -quiet {*_gate_*/E}]
    if {[sizeof_collection $enables] != 128} {error "preflight gate E pins missing"}
    if {![get_attribute [get_clocks kvzap_control_clk] propagated_clock]} {error "clock not propagated"}
    redirect [file join $out gating.rpt] {report_clock_gating -gating_elements -gated -verbose -nosplit}
    redirect [file join $out gate_setup.rpt] {report_timing -to $enables -delay_type max -path_type full_clock_expanded -max_paths 1 -significant_digits 6}
    redirect [file join $out gate_hold.rpt] {report_timing -to $enables -delay_type min -path_type full_clock_expanded -max_paths 1 -significant_digits 6}
    puts "KVZAP_WCG1_PREFLIGHT_PASS data_flops=10176 clock_gates=128"
    exit 0
  }
  proc wcg1_worst_slack {paths} {
    if {[sizeof_collection $paths] < 1} {error "missing required timing path"}
    set worst 1.0e30
    foreach_in_collection path $paths {
      set value [get_attribute $path slack]
      if {$value < $worst} {set worst $value}
    }
    return $worst
  }
  proc wcg1_snapshot {out stage side} {
    set dest [file join $out $stage]
    file mkdir $dest
    update_timing
    set storage [get_cells {member_ff_* suffix_ff_*}]
    set gates [get_cells -quiet -filter {ref_name =~ CKLNQ*}]
    if {[sizeof_collection $storage] != 10176} {error "mapped storage count mismatch"}
    set expected_gates 0
    if {$side eq "gated"} {set expected_gates 128}
    if {[sizeof_collection $gates] != $expected_gates} {error "mapped gate count mismatch"}
    foreach_in_collection cell $storage {
      set ref [get_attribute $cell ref_name]
      if {$side eq "gated" && ![string match DFQD* $ref]} {error "gated storage remapped: $ref"}
      if {$side eq "reference" && ![string match EDFQD* $ref]} {error "reference storage remapped: $ref"}
    }
    redirect [file join $dest check_design.rpt] {check_design}
    redirect [file join $dest check_timing.rpt] {check_timing}
    redirect [file join $dest area.rpt] {report_area -hierarchy -nosplit}
    redirect [file join $dest references.rpt] {report_reference -hierarchy -nosplit}
    redirect [file join $dest qor.rpt] {report_qor}
    redirect [file join $dest constraints.rpt] {report_constraint -all_violators -significant_digits 6}
    redirect [file join $dest clocks.rpt] {report_clock -attributes -skew -nosplit}
    redirect [file join $dest gating.rpt] {report_clock_gating -gating_elements -gated -verbose -nosplit}
    redirect [file join $dest setup.rpt] {
      report_timing -delay_type max -path_type full_clock_expanded -max_paths 20 -nets -input_pins -transition_time -capacitance -significant_digits 6 -nosplit
    }
    redirect [file join $dest hold.rpt] {
      report_timing -delay_type min -path_type full_clock_expanded -max_paths 20 -nets -input_pins -transition_time -capacitance -significant_digits 6 -nosplit
    }
    set f [open [file join $dest metrics.tsv] w]
    puts $f "metric\tvalue"
    puts $f "data_flops\t[sizeof_collection $storage]"
    puts $f "clock_gates\t[sizeof_collection $gates]"
    puts $f "period_ns\t[get_attribute [get_clocks kvzap_control_clk] period]"
    puts $f "propagated\t[get_attribute [get_clocks kvzap_control_clk] propagated_clock]"
    lassign [wcg1_native_area_values [file join $dest area.rpt]] total_area comb_area seq_area
    puts $f "total_area\t$total_area"
    puts $f "combinational_area\t$comb_area"
    puts $f "sequential_area\t$seq_area"
    puts $f "area_basis\tnative_report_total_cell_area"
    foreach delay {max min} {
      set paths [get_timing_paths -delay_type $delay -max_paths 1]
      puts $f "${delay}_slack_ns\t[wcg1_worst_slack $paths]"
    }
    if {$side eq "gated"} {
      set enable_pins [get_pins -quiet {*_gate_*/E}]
      if {[sizeof_collection $enable_pins] != 128} {error "missing gate E pins"}
      redirect [file join $dest gate_setup.rpt] {
        report_timing -to $enable_pins -delay_type max -path_type full_clock_expanded -max_paths 20 -significant_digits 6 -nosplit
      }
      redirect [file join $dest gate_hold.rpt] {
        report_timing -to $enable_pins -delay_type min -path_type full_clock_expanded -max_paths 20 -significant_digits 6 -nosplit
      }
      foreach delay {max min} {
        set paths [get_timing_paths -to $enable_pins -delay_type $delay -max_paths 1]
        puts $f "gate_${delay}_slack_ns\t[wcg1_worst_slack $paths]"
      }
      set captures [get_pins -quiet {member_ff_*/D suffix_ff_*/D}]
      if {[sizeof_collection $captures] != 10176} {error "missing gated D endpoints"}
      redirect [file join $dest gated_data_hold.rpt] {
        report_timing -to $captures -delay_type min -path_type full_clock_expanded -max_paths 20 -nets -input_pins -transition_time -significant_digits 6 -nosplit
      }
    }
    close $f
    write -format ddc -hierarchy -output [file join $dest mapped.ddc]
    write -format verilog -hierarchy -output [file join $dest mapped.v]
    write_sdc [file join $dest mapped.sdc]
    puts "KVZAP_WCG1_STAGE_REPORTED side=$side stage=$stage"
  }
  compile -map_effort medium
  wcg1_snapshot $out raw $side
  set_fix_hold [all_clocks]
  compile -only_hold_time
  wcg1_snapshot $out repaired $side
  puts "KVZAP_WCG1_SIDE_RUN_PASS side=$side"
  exit 0
} message options]} {
  puts stderr "KVZAP_WCG1_SIDE_FAIL $message"
  if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
  exit 1
}
