# Isolated read-network experiment, never a complete Route-A DC run.
if {[catch {
  set root $::env(KVZAP_RD1_SCREEN_ROOT)
  # The Bash launcher sources the copied environment before invoking dc_shell.
  set target_library $::env(KVZAP_DC_TARGET_LIBRARY)
  set link_library [list * $target_library]
  source $root/scripts/constraints_control_projection.tcl
  foreach side {original shared} {
    set top rd1_${side}_read_network
    set out $root/$side
    if {[file exists $out]} {error "refusing to overwrite $out"}
    file mkdir $out
    file mkdir $out/work
    remove_design -all
    define_design_lib WORK -path $out/work
    if {![analyze -format sverilog -define SYNTHESIS $root/inputs/$top.sv]} {error "analyze failed"}
    if {[elaborate $top] eq ""} {error "elaborate failed"}
    current_design $top
    if {![link]} {error "link failed"}
    kvzap_apply_control_projection_constraints
    report_resources > $out/resources_before_mapping.rpt
    if {![compile -map_effort medium]} {error "compile failed"}
    if {[sizeof_collection [all_registers]] != 0} {error "screen unexpectedly contains registers"}
    check_design > $out/check_design.rpt
    check_timing > $out/check_timing.rpt
    report_qor > $out/qor.rpt
    report_area -hierarchy -nosplit > $out/area.rpt
    report_timing -delay_type max -max_paths 10 -nets -significant_digits 6 > $out/timing.rpt
    report_constraint -all_violators > $out/constraints.rpt
    write -format ddc -hierarchy -output $out/$top.ddc
    write -format verilog -hierarchy -output $out/${top}_mapped.v
    puts "KVZAP_RD1_SCREEN_SIDE_PASS side=$side"
  }
} message options]} {
  puts stderr "KVZAP_RD1_SCREEN_FAIL $message"
  if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
  exit 1
}
puts KVZAP_RD1_READ_NETWORK_SCREEN_PASS
exit 0
