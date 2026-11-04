# Read-only saved-DDC attribution for RouteAPageManager P0 diagnosis.
# The script deliberately performs no compile, constraint mutation, or design write.
if {[catch {
  set ddc $::env(KVZAP_PAGE_MANAGER_P0_DDC)
  set out $::env(KVZAP_PAGE_MANAGER_P0_OUT)
  if {![file isfile $ddc]} { error "missing saved DDC: $ddc" }
  if {[file exists $out]} { error "refusing to overwrite report directory: $out" }
  file mkdir $out

  set target_library $::env(KVZAP_DC_TARGET_LIBRARY)
  set link_library [list * $target_library]
  read_ddc $ddc
  current_design route_a_control_projection

  proc collection_area {objects} {
    set total 0.0
    foreach_in_collection object $objects {
      set value [get_attribute $object area]
      if {$value ne ""} { set total [expr {$total + $value}] }
    }
    return $total
  }

  proc emit_family {handle name pattern} {
    set sequential [get_cells -quiet -hierarchical * -filter \
      "full_name =~ $pattern && is_hierarchical == false && is_sequential == true"]
    puts $handle [format "%s\t%d\t%.6f" $name [sizeof_collection $sequential] [collection_area $sequential]]
  }

  proc emit_comb_cone {handle name endpoints} {
    if {[sizeof_collection $endpoints] == 0} {
      puts $handle [format "%s\t0\t0.000000" $name]
      return
    }
    set all_cells [all_fanin -flat -to $endpoints -only_cells]
    set local_comb [filter_collection $all_cells \
      "full_name =~ pageManager/* && is_hierarchical == false && is_sequential == false"]
    puts $handle [format "%s\t%d\t%.6f" $name [sizeof_collection $local_comb] [collection_area $local_comb]]
  }

  set page_manager [get_cells -quiet pageManager]
  if {[sizeof_collection $page_manager] != 1} { error "expected one pageManager instance" }
  set page_leaf [get_cells -quiet -hierarchical * -filter \
    "full_name =~ pageManager/* && full_name !~ pageManager/availabilityStorage && is_hierarchical == false"]
  set page_seq [filter_collection $page_leaf "is_sequential == true"]
  set page_comb [filter_collection $page_leaf "is_sequential == false"]

  set summary [open [file join $out summary.tsv] w]
  puts $summary "metric\tcount\tarea"
  puts $summary [format "page_manager_leaf\t%d\t%.6f" [sizeof_collection $page_leaf] [collection_area $page_leaf]]
  puts $summary [format "page_manager_sequential\t%d\t%.6f" [sizeof_collection $page_seq] [collection_area $page_seq]]
  puts $summary [format "page_manager_combinational\t%d\t%.6f" [sizeof_collection $page_comb] [collection_area $page_comb]]
  close $summary

  set families [open [file join $out sequential_families.tsv] w]
  puts $families "family\tcell_count\tcell_area"
  foreach {name pattern} {
    allocatedLine pageManager/allocatedLine*
    buildActive pageManager/buildActive*
    buildFault pageManager/buildFault*
    buildPayloadDurable pageManager/buildPayloadDurable*
    buildPrerequisiteReported pageManager/buildPrerequisiteReported*
    buildLayer pageManager/buildLayer*
    buildHead pageManager/buildHead*
    buildValidRecords pageManager/buildValidRecords*
    buildPageId pageManager/buildPageId*
    buildGeneration pageManager/buildGeneration*
    buildTag pageManager/buildTag*
    buildNewDurable pageManager/buildNewDurable*
    buildTailDurable pageManager/buildTailDurable*
    buildNeedsTail pageManager/buildNeedsTail*
    visibleTailPresent pageManager/visibleTailPresent*
    visibleTailId pageManager/visibleTailId*
    visibleTailGeneration pageManager/visibleTailGeneration*
    appendDescriptorLineData pageManager/appendDescriptorLineData*
    reclaimDescriptorLineData pageManager/reclaimDescriptorLineData*
    releasePending pageManager/releasePending*
    releaseGeneration pageManager/releaseGeneration*
    allocationSeen pageManager/allocationSeen*
    durableInvalidation pageManager/durableInvalidation*
  } { emit_family $families $name $pattern }
  close $families

  set allocated_regs [get_cells -quiet -hierarchical * -filter \
    "full_name =~ pageManager/allocatedLine* && is_sequential == true"]
  set reclaim_regs [get_cells -quiet -hierarchical * -filter \
    "full_name =~ pageManager/reclaimLine_reg* && is_sequential == true"]
  set reclaim_d [get_pins -quiet -of_objects $reclaim_regs -filter "direction == in && full_name =~ */D"]
  if {[sizeof_collection $allocated_regs] == 0 || [sizeof_collection $reclaim_d] == 0} {
    error "failed to resolve allocatedLine -> reclaimLine endpoints"
  }
  set selection_cone [all_fanin -flat -to $reclaim_d -only_cells]
  set selection_page [filter_collection $selection_cone "full_name =~ pageManager/* && is_hierarchical == false"]
  set selection_comb [filter_collection $selection_page "is_sequential == false"]
  set cone [open [file join $out allocated_line_selection_cone.tsv] w]
  puts $cone "metric\tcount\tarea"
  puts $cone [format "allocated_line_startpoints\t%d\t%.6f" [sizeof_collection $allocated_regs] [collection_area $allocated_regs]]
  puts $cone [format "page_manager_comb_fanin_to_reclaim_line\t%d\t%.6f" [sizeof_collection $selection_comb] [collection_area $selection_comb]]
  close $cone

  set cones [open [file join $out combinational_cones.tsv] w]
  puts $cones "cone\tcell_count\tcell_area"
  emit_comb_cone $cones allocated_line_to_reclaim_line $reclaim_d
  emit_comb_cone $cones payload_durable_ready \
    [get_pins -quiet pageManager/io_p3_payload_durable_in_ready]
  emit_comb_cone $cones descriptor_terminal_ready \
    [get_pins -quiet pageManager/io_descriptor_maintenance_terminal_in_ready]
  emit_comb_cone $cones publication_visibility_ready \
    [get_pins -quiet pageManager/io_metadata_publish_visibility_in_ready]
  emit_comb_cone $cones descriptor_prerequisite_valid \
    [get_pins -quiet pageManager/io_descriptor_durability_prerequisite_out_valid]
  emit_comb_cone $cones append_candidate_valid \
    [get_pins -quiet pageManager/io_append_candidate_out_valid]
  close $cones

  puts "KVZAP_PAGE_MANAGER_P0_READ_ONLY_PASS"
  puts "PROBE_READ_ONLY_COMPLETE"
  exit 0
} message options]} {
  puts stderr "KVZAP_PAGE_MANAGER_P0_READ_ONLY_FAIL $message"
  if {[dict exists $options -errorinfo]} { puts stderr [dict get $options -errorinfo] }
  exit 1
}
