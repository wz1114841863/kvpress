# Validate the existing mapped PM1 child against the accepted mapped top.
#
# This is a saved-DDC-only closure.  It performs no analyze, elaborate,
# characterize, compile or mapped-design write.
if {[catch {
  set root $::env(KVZAP_PM1_SAVED_DDC_ROOT)
  set baseline_ddc $::env(KVZAP_PM1_BASELINE_DDC)
  set candidate_ddc $::env(KVZAP_PM1_CANDIDATE_DDC)
  set top route_a_control_projection
  set baseline_ref route_a_page_manager
  set candidate_ref route_a_page_manager_pm1
  set proxy_ref route_a_r5_availability_array_boundary
  set expected_registers 62000
  set expected_boundary_pins 4289
  set expected_top_registers 577106

  foreach required [list $baseline_ddc $candidate_ddc] {
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

  read_ddc $baseline_ddc
  current_design $top
  if {![link]} { error "baseline top link failed" }
  set baseline_instance [get_cells -quiet pageManager]
  set baseline_instance_count [sizeof_collection $baseline_instance]
  if {$baseline_instance_count != 1} {
    error "expected exactly one baseline pageManager instance"
  }
  if {[get_attribute $baseline_instance ref_name] ne $baseline_ref} {
    error "unexpected baseline Page Manager reference"
  }
  set boundary_pins [sizeof_collection [get_pins -quiet -of_objects $baseline_instance]]
  if {$boundary_pins != $expected_boundary_pins} {
    error "expected $expected_boundary_pins Page Manager pins, found $boundary_pins"
  }
  set baseline_registers [get_cells -quiet -hierarchical * -filter \
    "full_name =~ pageManager/* && is_sequential == true"]
  set baseline_register_count [sizeof_collection $baseline_registers]
  if {$baseline_register_count != $expected_registers} {
    error "expected $expected_registers baseline registers, found $baseline_register_count"
  }
  redirect [file join $baseline_out top_check_design.rpt] { check_design }
  redirect [file join $baseline_out top_check_timing.rpt] { check_timing }
  redirect [file join $baseline_out top_qor.rpt] { report_qor }
  redirect [file join $baseline_out top_area_hierarchy.rpt] { report_area -hierarchy -nosplit }
  redirect [file join $baseline_out top_timing_setup.rpt] {
    report_timing -delay_type max -max_paths 20 -transition_time -nets -significant_digits 6
  }
  redirect [file join $baseline_out top_timing_hold.rpt] {
    report_timing -delay_type min -max_paths 20 -transition_time -nets -significant_digits 6
  }
  current_design $baseline_ref
  redirect [file join $baseline_out child_qor.rpt] { report_qor }
  redirect [file join $baseline_out child_area.rpt] { report_area -hierarchy -nosplit }

  read_ddc $candidate_ddc
  current_design $candidate_ref
  if {![link]} { error "candidate saved DDC link failed" }
  set candidate_register_count [sizeof_collection [all_registers]]
  if {$candidate_register_count != $expected_registers} {
    error "expected $expected_registers candidate registers, found $candidate_register_count"
  }
  set candidate_proxy_cells [get_cells -quiet -hierarchical * -filter \
    "ref_name == $proxy_ref"]
  set candidate_proxy_count [sizeof_collection $candidate_proxy_cells]
  if {$candidate_proxy_count != 1} {
    error "expected one candidate R5 proxy, found $candidate_proxy_count"
  }
  set candidate_clock_count [sizeof_collection [get_clocks -quiet *]]
  if {$candidate_clock_count != 1} {
    error "expected one candidate clock, found $candidate_clock_count"
  }
  redirect [file join $candidate_out check_design.rpt] { check_design }
  redirect [file join $candidate_out check_timing.rpt] { check_timing }
  redirect [file join $candidate_out clocks.rpt] { report_clock }
  redirect [file join $candidate_out qor.rpt] { report_qor }
  redirect [file join $candidate_out area_hierarchy.rpt] { report_area -hierarchy -nosplit }
  redirect [file join $candidate_out references.rpt] { report_reference -hierarchy }
  redirect [file join $candidate_out timing_setup.rpt] {
    report_timing -delay_type max -max_paths 20 -transition_time -nets -significant_digits 6
  }
  redirect [file join $candidate_out timing_hold.rpt] {
    report_timing -delay_type min -max_paths 20 -transition_time -nets -significant_digits 6
  }

  current_design $top
  set replacement_instance [get_cells -quiet pageManager]
  if {[sizeof_collection $replacement_instance] != 1} {
    error "expected one Page Manager instance before saved-DDC relink"
  }
  if {![change_link $replacement_instance $candidate_ref]} {
    error "fail-closed saved-DDC change_link rejected the PM1 child"
  }
  if {![link]} { error "saved-DDC relinked top link failed" }
  set final_instance [get_cells -quiet pageManager]
  set final_instance_count [sizeof_collection $final_instance]
  if {$final_instance_count != 1 || \
      [get_attribute $final_instance ref_name] ne $candidate_ref} {
    error "saved-DDC relinked top lost the PM1 child"
  }
  set final_top_register_count [sizeof_collection [all_registers]]
  if {$final_top_register_count != $expected_top_registers} {
    error "expected $expected_top_registers relinked-top registers, found $final_top_register_count"
  }
  redirect [file join $relinked_out check_design.rpt] { check_design }
  redirect [file join $relinked_out check_timing.rpt] { check_timing }
  redirect [file join $relinked_out qor.rpt] { report_qor }
  redirect [file join $relinked_out area_hierarchy.rpt] { report_area -hierarchy -nosplit }
  redirect [file join $relinked_out timing_setup.rpt] {
    report_timing -delay_type max -max_paths 20 -transition_time -nets -significant_digits 6
  }
  redirect [file join $relinked_out timing_hold.rpt] {
    report_timing -delay_type min -max_paths 20 -transition_time -nets -significant_digits 6
  }

  set summary [open [file join $root summary.tsv] w]
  puts $summary "metric\tvalue"
  puts $summary "validation_kind\tsaved_ddc_only"
  puts $summary "top_design\t$top"
  puts $summary "baseline_ref\t$baseline_ref"
  puts $summary "candidate_ref\t$candidate_ref"
  puts $summary "page_manager_boundary_pins\t$boundary_pins"
  puts $summary "baseline_registers\t$baseline_register_count"
  puts $summary "candidate_registers\t$candidate_register_count"
  puts $summary "candidate_clocks\t$candidate_clock_count"
  puts $summary "candidate_proxy_instances\t$candidate_proxy_count"
  puts $summary "relinked_top_registers\t$final_top_register_count"
  close $summary

  puts "KVZAP_PM1_SAVED_DDC_NATIVE_PASS candidate=$candidate_ref"
} message options]} {
  puts stderr "KVZAP_PM1_SAVED_DDC_NATIVE_FAIL $message"
  if {[dict exists $options -errorinfo]} { puts stderr [dict get $options -errorinfo] }
  exit 1
}
exit 0
