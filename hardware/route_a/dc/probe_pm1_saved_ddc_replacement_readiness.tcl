# Read-only PM1 replacement-readiness probe for an accepted mapped Route-A DDC.
# Deliberately performs no analyze/elaborate/link/compile, constraint mutation,
# dont-touch mutation, design removal, or design/netlist/DDC write.
if {[catch {
  set ddc $::env(KVZAP_PM1_DDC)
  set out $::env(KVZAP_PM1_DDC_PROBE_OUT)
  if {![file isfile $ddc]} { error "missing saved DDC: $ddc" }
  if {[file exists $out]} { error "refusing to overwrite report directory: $out" }
  file mkdir $out

  set target_library $::env(KVZAP_DC_TARGET_LIBRARY)
  set link_library [list * $target_library]
  read_ddc $ddc
  current_design route_a_control_projection

  redirect [file join $out designs.rpt] { list_designs }
  redirect [file join $out clocks.rpt] { report_clock }
  redirect [file join $out page_manager_area.rpt] {
    report_area -hierarchy -nosplit
  }

  set instance [get_cells -quiet pageManager]
  if {[sizeof_collection $instance] != 1} {
    error "expected exactly one pageManager instance"
  }
  set ref_name [get_attribute $instance ref_name]
  set ref_design [get_designs -quiet $ref_name]
  set matching_instances [get_cells -quiet -hierarchical * -filter "ref_name == $ref_name"]
  set child_cells [get_cells -quiet -hierarchical pageManager/*]
  set child_ports [get_pins -quiet -of_objects $instance]
  set allocated_regs [get_cells -quiet -hierarchical * -filter \
    "full_name =~ pageManager/allocatedLine* && is_sequential == true"]
  set reclaim_regs [get_cells -quiet -hierarchical * -filter \
    "full_name =~ pageManager/reclaimLine_reg* && is_sequential == true"]
  set reclaim_d [get_pins -quiet -of_objects $reclaim_regs -filter \
    "direction == in && full_name =~ */D"]
  set selection_cells [all_fanin -flat -to $reclaim_d -only_cells]
  set selection_comb [filter_collection $selection_cells \
    "full_name =~ pageManager/* && is_hierarchical == false && is_sequential == false"]

  set summary [open [file join $out summary.tsv] w]
  puts $summary "metric\tvalue"
  puts $summary "top_design\t[get_object_name [current_design]]"
  puts $summary "page_manager_instance\t[get_object_name $instance]"
  puts $summary "page_manager_ref_name\t$ref_name"
  puts $summary "page_manager_ref_design_count\t[sizeof_collection $ref_design]"
  puts $summary "page_manager_ref_instance_count\t[sizeof_collection $matching_instances]"
  puts $summary "page_manager_is_hierarchical\t[get_attribute $instance is_hierarchical]"
  puts $summary "page_manager_boundary_pin_count\t[sizeof_collection $child_ports]"
  puts $summary "page_manager_hierarchical_cell_count\t[sizeof_collection $child_cells]"
  puts $summary "allocated_line_register_count\t[sizeof_collection $allocated_regs]"
  puts $summary "reclaim_line_register_count\t[sizeof_collection $reclaim_regs]"
  puts $summary "reclaim_line_d_pin_count\t[sizeof_collection $reclaim_d]"
  puts $summary "selection_comb_cell_count\t[sizeof_collection $selection_comb]"
  puts $summary "top_clock_count\t[sizeof_collection [get_clocks -quiet *]]"
  close $summary

  if {[sizeof_collection $ref_design] != 1} {
    error "Page Manager is not retained as one independently addressable design"
  }
  if {[sizeof_collection $matching_instances] != 1} {
    error "Page Manager reference is not unique in the mapped top"
  }
  if {![get_attribute $instance is_hierarchical]} {
    error "Page Manager instance was flattened"
  }
  if {[sizeof_collection $allocated_regs] != 36720} {
    error "unexpected allocatedLine mapped register count"
  }
  if {[sizeof_collection $reclaim_d] == 0 || [sizeof_collection $selection_comb] == 0} {
    error "failed to recover the mapped selector boundary"
  }

  puts "KVZAP_PM1_SAVED_DDC_REPLACEMENT_READINESS_PASS ref=$ref_name"
  puts "PROBE_READ_ONLY_COMPLETE"
  exit 0
} message options]} {
  puts stderr "KVZAP_PM1_SAVED_DDC_REPLACEMENT_READINESS_FAIL $message"
  if {[dict exists $options -errorinfo]} { puts stderr [dict get $options -errorinfo] }
  exit 1
}
