# Isolated RD1+remaining-read baseline versus RD2 decode. One DC process/side.
if {[catch {
  set root $::env(KVZAP_RD2_SCREEN_ROOT)
  set side $::env(KVZAP_RD2_SCREEN_SIDE)
  if {$side ni {rd1 decoded}} { error "invalid RD2 side: $side" }
  set top rd2_${side}_read_network
  set out [file join $root $side]
  if {[file exists $out]} { error "refusing to overwrite $out" }
  file mkdir [file join $out work]
  set_app_var target_library [list $::env(KVZAP_DC_TARGET_LIBRARY)]
  set_app_var link_library [list * $::env(KVZAP_DC_TARGET_LIBRARY)]
  define_design_lib WORK -path [file join $out work]
  source [file join $root scripts constraints_control_projection.tcl]
  if {![analyze -format sverilog -define SYNTHESIS [file join $root inputs $top.sv]]} {
    error "RD2 $side analyze failed"
  }
  if {[elaborate $top] eq ""} { error "RD2 $side elaborate failed" }
  current_design $top
  if {![link]} { error "RD2 $side link failed" }
  kvzap_apply_control_projection_constraints
  redirect [file join $out resources_precompile.rpt] { report_resources }
  if {![compile -map_effort medium]} { error "RD2 $side compile failed" }
  set register_count [sizeof_collection [all_registers]]
  if {$register_count != 0} { error "RD2 unexpectedly contains $register_count registers" }
  redirect [file join $out check_design.rpt] { check_design }
  redirect [file join $out check_timing.rpt] { check_timing }
  redirect [file join $out clocks.rpt] { report_clock }
  redirect [file join $out qor.rpt] { report_qor }
  redirect [file join $out area.rpt] { report_area -hierarchy -nosplit }
  redirect [file join $out timing_setup.rpt] {
    report_timing -delay_type max -max_paths 20 -nets -significant_digits 6
  }
  redirect [file join $out timing_hold.rpt] {
    report_timing -delay_type min -max_paths 20 -nets -significant_digits 6
  }
  redirect [file join $out constraints.rpt] { report_constraint -all_violators }
  write -format ddc -hierarchy -output [file join $out $top.ddc]
  write -format verilog -hierarchy -output [file join $out ${top}_mapped.v]
  set summary [open [file join $out summary.tsv] w]
  puts $summary "metric\tvalue"
  puts $summary "side\t$side"
  puts $summary "registers\t$register_count"
  close $summary
  puts "KVZAP_RD2_SCREEN_SIDE_PASS side=$side"
} message options]} {
  puts stderr "KVZAP_RD2_SCREEN_FAIL $message"
  if {[dict exists $options -errorinfo]} { puts stderr [dict get $options -errorinfo] }
  exit 1
}
exit 0
