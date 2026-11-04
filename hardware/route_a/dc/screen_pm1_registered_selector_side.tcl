# One isolated registered PM1 selector side; launched in its own DC process.
if {[catch {
  set root $::env(KVZAP_PM1_SCREEN_ROOT)
  set side $::env(KVZAP_PM1_SCREEN_SIDE)
  if {$side ni {original banked}} {error "invalid PM1 side $side"}
  set top pm1_${side}_registered_selector
  set out $root/$side
  if {[file exists $out]} {error "refusing to overwrite $out"}
  file mkdir $out
  file mkdir $out/work
  set target_library $::env(KVZAP_DC_TARGET_LIBRARY)
  set link_library [list * $target_library]
  source $root/scripts/constraints_control_projection.tcl
  define_design_lib WORK -path $out/work
  if {![analyze -format sverilog -define SYNTHESIS $root/inputs/$top.sv]} {error "analyze failed"}
  if {[elaborate $top] eq ""} {error "elaborate failed"}
  current_design $top
  if {![link]} {error "link failed"}
  kvzap_apply_control_projection_constraints
  set expected_registers 36737
  set pre_registers [sizeof_collection [all_registers]]
  if {$pre_registers != $expected_registers} {
    error "expected $expected_registers precompile registers, found $pre_registers"
  }
  check_design > $out/check_design_precompile.rpt
  check_timing > $out/check_timing_precompile.rpt
  report_constraint -all_violators > $out/constraints_precompile.rpt
  report_resources > $out/resources_before_mapping.rpt
  if {![compile -map_effort medium]} {error "compile failed"}
  set post_registers [sizeof_collection [all_registers]]
  if {$post_registers != $expected_registers} {
    error "expected $expected_registers postcompile registers, found $post_registers"
  }
  check_design > $out/check_design_postcompile.rpt
  check_timing > $out/check_timing_postcompile.rpt
  report_qor > $out/qor.rpt
  report_area -hierarchy -nosplit > $out/area.rpt
  report_timing -delay_type max -max_paths 20 -nets -significant_digits 6 > $out/timing.rpt
  report_constraint -all_violators > $out/constraints_postcompile.rpt
  write -format ddc -hierarchy -output $out/$top.ddc
  write -format verilog -hierarchy -output $out/${top}_mapped.v
  puts "KVZAP_PM1_REGISTERED_SCREEN_SIDE_PASS side=$side"
} message options]} {
  puts stderr "KVZAP_PM1_REGISTERED_SCREEN_SIDE_FAIL side=$::env(KVZAP_PM1_SCREEN_SIDE) message=$message"
  if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
  exit 1
}
exit 0
