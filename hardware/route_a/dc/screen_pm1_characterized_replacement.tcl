# Controlled bottom-up PM1 Page Manager replacement screen.
#
# The accepted mapped Route-A top supplies the immutable baseline and the real
# timing/load/connection environment.  Only the compatible PM1 child is
# analyzed and compiled.  The top is relinked without -force or a pin map and
# is never recompiled by this screen.
if {[catch {
  set root $::env(KVZAP_PM1_CHARACTERIZED_ROOT)
  set ddc $::env(KVZAP_PM1_BASELINE_DDC)
  set candidate_sv $::env(KVZAP_PM1_CANDIDATE_SV)
  set top route_a_control_projection
  set baseline_ref route_a_page_manager
  set candidate_ref route_a_page_manager_pm1
  set proxy_ref route_a_r5_availability_array_boundary
  set expected_registers 62000

  foreach required [list $ddc $candidate_sv] {
    if {![file isfile $required]} { error "missing input: $required" }
  }
  foreach absent [list [file join $root work] [file join $root baseline] \
      [file join $root candidate] [file join $root relinked_top]] {
    if {[file exists $absent]} { error "refusing to overwrite $absent" }
  }
  foreach directory [list [file join $root work] [file join $root baseline] \
      [file join $root candidate] [file join $root relinked_top]] {
    file mkdir $directory
  }
  set baseline_out [file join $root baseline]
  set candidate_out [file join $root candidate]
  set relinked_out [file join $root relinked_top]

  set target_libraries [split $::env(KVZAP_DC_TARGET_LIBRARY) ":"]
  foreach library $target_libraries {
    if {![file isfile $library]} { error "missing target library: $library" }
  }
  define_design_lib WORK -path [file join $root work]
  set_app_var target_library $target_libraries
  set_app_var link_library [concat "*" $target_libraries]

  read_ddc $ddc
  current_design $top
  if {![link]} { error "baseline top link failed" }
  set instance [get_cells -quiet pageManager]
  if {[sizeof_collection $instance] != 1} {
    error "expected exactly one top-level pageManager instance"
  }
  if {[get_attribute $instance ref_name] ne $baseline_ref} {
    error "unexpected baseline Page Manager reference"
  }
  if {![get_attribute $instance is_hierarchical]} {
    error "baseline Page Manager is not hierarchical"
  }
  set boundary_pins [sizeof_collection [get_pins -quiet -of_objects $instance]]
  set baseline_registers [get_cells -quiet -hierarchical * -filter \
    "full_name =~ pageManager/* && is_sequential == true"]
  if {[sizeof_collection $baseline_registers] != $expected_registers} {
    error "expected $expected_registers baseline Page Manager registers, found [sizeof_collection $baseline_registers]"
  }
  redirect [file join $baseline_out top_qor.rpt] { report_qor }
  redirect [file join $baseline_out top_area_hierarchy.rpt] { report_area -hierarchy -nosplit }
  redirect [file join $baseline_out top_timing_setup.rpt] {
    report_timing -delay_type max -max_paths 20 -transition_time -nets -significant_digits 6
  }
  current_design $baseline_ref
  redirect [file join $baseline_out child_qor.rpt] { report_qor }
  redirect [file join $baseline_out child_area.rpt] { report_area -hierarchy -nosplit }
  redirect [file join $baseline_out child_timing_setup.rpt] {
    report_timing -delay_type max -max_paths 20 -transition_time -nets -significant_digits 6
  }

  if {![analyze -format sverilog -define SYNTHESIS $candidate_sv]} {
    error "candidate analyze failed"
  }
  if {[elaborate $candidate_ref] eq ""} { error "candidate elaborate failed" }
  current_design $candidate_ref
  if {![link]} { error "candidate child link failed" }
  set candidate_pre_registers [sizeof_collection [all_registers]]
  if {$candidate_pre_registers != $expected_registers} {
    error "expected $expected_registers candidate precompile registers, found $candidate_pre_registers"
  }
  set proxy_cells [get_cells -quiet -hierarchical * -filter "ref_name == $proxy_ref"]
  if {[sizeof_collection $proxy_cells] != 1} {
    error "expected one retained R5 availability proxy in candidate child"
  }
  set_dont_touch $proxy_cells true
  set_ungroup $proxy_cells false
  redirect [file join $candidate_out check_design_precompile.rpt] { check_design }
  redirect [file join $candidate_out check_timing_precharacterize.rpt] { check_timing }
  redirect [file join $candidate_out resources_precompile.rpt] { report_resources }

  current_design $top
  set instance [get_cells -quiet pageManager]
  if {![change_link $instance $candidate_ref]} {
    error "fail-closed change_link rejected the PM1 child"
  }
  if {![link]} { error "relinked top link failed" }
  set instance [get_cells -quiet pageManager]
  if {[sizeof_collection $instance] != 1 || [get_attribute $instance ref_name] ne $candidate_ref} {
    error "Page Manager did not resolve uniquely to the PM1 child"
  }
  characterize $instance -constraints -connections

  current_design $candidate_ref
  set characterized_clocks [sizeof_collection [get_clocks -quiet *]]
  if {$characterized_clocks != 1} {
    error "expected one characterized child clock, found $characterized_clocks"
  }
  redirect [file join $candidate_out clocks_characterized.rpt] { report_clock }
  redirect [file join $candidate_out constraints_characterized.rpt] {
    report_constraint -all_violators
  }
  redirect [file join $candidate_out timing_precompile.rpt] {
    report_timing -delay_type max -max_paths 20 -transition_time -nets -significant_digits 6
  }
  if {![compile -map_effort medium]} { error "candidate child compile failed" }
  set candidate_post_registers [sizeof_collection [all_registers]]
  if {$candidate_post_registers != $expected_registers} {
    error "expected $expected_registers candidate postcompile registers, found $candidate_post_registers"
  }
  set proxy_cells [get_cells -quiet -hierarchical * -filter "ref_name == $proxy_ref"]
  if {[sizeof_collection $proxy_cells] != 1} {
    error "candidate compile did not retain exactly one R5 availability proxy"
  }
  redirect [file join $candidate_out check_design_postcompile.rpt] { check_design }
  redirect [file join $candidate_out check_timing_postcompile.rpt] { check_timing }
  redirect [file join $candidate_out constraints_postcompile.rpt] {
    report_constraint -all_violators
  }
  redirect [file join $candidate_out qor.rpt] { report_qor }
  redirect [file join $candidate_out area_hierarchy.rpt] { report_area -hierarchy -nosplit }
  redirect [file join $candidate_out references.rpt] { report_reference -hierarchy }
  redirect [file join $candidate_out timing_setup.rpt] {
    report_timing -delay_type max -max_paths 20 -transition_time -nets -significant_digits 6
  }
  redirect [file join $candidate_out timing_hold.rpt] {
    report_timing -delay_type min -max_paths 20 -transition_time -nets -significant_digits 6
  }
  write -format ddc -hierarchy -output [file join $candidate_out ${candidate_ref}.ddc]
  write -format verilog -hierarchy -output [file join $candidate_out ${candidate_ref}_mapped.v]

  current_design $top
  if {![link]} { error "final relinked top link failed" }
  set final_instance [get_cells -quiet pageManager]
  if {[sizeof_collection $final_instance] != 1 || [get_attribute $final_instance ref_name] ne $candidate_ref} {
    error "final relinked top lost the PM1 child"
  }
  redirect [file join $relinked_out check_design.rpt] { check_design }
  redirect [file join $relinked_out check_timing.rpt] { check_timing }
  redirect [file join $relinked_out qor.rpt] { report_qor }
  redirect [file join $relinked_out area_hierarchy.rpt] { report_area -hierarchy -nosplit }
  redirect [file join $relinked_out timing_setup.rpt] {
    report_timing -delay_type max -max_paths 20 -transition_time -nets -significant_digits 6
  }

  set summary [open [file join $root summary.tsv] w]
  puts $summary "metric\tvalue"
  puts $summary "top_design\t$top"
  puts $summary "baseline_ref\t$baseline_ref"
  puts $summary "candidate_ref\t$candidate_ref"
  puts $summary "page_manager_boundary_pins\t$boundary_pins"
  puts $summary "baseline_registers\t[sizeof_collection $baseline_registers]"
  puts $summary "candidate_precompile_registers\t$candidate_pre_registers"
  puts $summary "candidate_postcompile_registers\t$candidate_post_registers"
  puts $summary "candidate_characterized_clocks\t$characterized_clocks"
  puts $summary "candidate_proxy_instances\t[sizeof_collection $proxy_cells]"
  close $summary

  puts "KVZAP_PM1_CHARACTERIZED_REPLACEMENT_PASS candidate=$candidate_ref"
} message options]} {
  puts stderr "KVZAP_PM1_CHARACTERIZED_REPLACEMENT_FAIL $message"
  if {[dict exists $options -errorinfo]} { puts stderr [dict get $options -errorinfo] }
  exit 1
}
exit 0
