# Read-only STA of immutable mapped designs. Never compile or rewrite a DDC.
if {[catch {
  set_host_options -max_cores 2
  set_app_var target_library [list $::env(KVZAP_DIAG_LIBRARY)]
  set_app_var link_library [concat [list *] $target_library]
  read_ddc $::env(KVZAP_DIAG_DDC)
  current_design route_a_control_projection
  if {![link]} {error "saved design link failed"}
  set out $::env(KVZAP_DIAG_OUT)
  set clocks [get_clocks *]
  if {[sizeof_collection $clocks] != 1} {error "saved clock count changed"}
  if {[get_attribute $clocks period] != 2.0} {error "saved 2-ns period missing"}
  if {[get_attribute $clocks propagated_clock]} {error "unexpected propagated-clock policy"}
  update_timing
  redirect [file join $out qor.rpt] {report_qor}
  redirect [file join $out clocks.rpt] {report_clock -attributes -skew -nosplit}
  redirect [file join $out check_timing.rpt] {check_timing}
  redirect [file join $out area.rpt] {report_area -hierarchy -nosplit}
  redirect [file join $out setup_top.rpt] {
    report_timing -delay_type max -path_type full_clock_expanded -max_paths 20 -significant_digits 6 -nosplit
  }
  set reclaim [get_pins -hier -quiet -filter {full_name =~ pageManager/reclaimLine_reg*/D}]
  if {[sizeof_collection $reclaim] != 16} {error "expected 16 reclaimLine capture pins"}
  redirect [file join $out reclaim_setup.rpt] {
    report_timing -to $reclaim -delay_type max -path_type full_clock_expanded -max_paths 16 -significant_digits 6 -nosplit
  }
  foreach name {
    io_functional_sidecar_read_issue_in_ready
    io_functional_sidecar_registry_allocate_in_ready
    io_functional_sidecar_registry_allocation_ack_out_valid
    io_external_core_mem_if_v1_request_valid
  } {
    set port [get_ports -quiet $name]
    if {[sizeof_collection $port] != 1} {error "missing common endpoint $name"}
    redirect [file join $out ${name}.rpt] {
      report_timing -to $port -delay_type max -path_type full_clock_expanded -max_paths 1 -significant_digits 6 -nosplit
    }
  }
  # One worst path per endpoint/path group. The postcheck compares coverage
  # with native QoR; do not silently equate these two counting conventions.
  set paths [get_timing_paths -delay_type max -slack_lesser_than 0 -nworst 1 -max_paths 100000]
  set f [open [file join $out endpoints.tsv] w]
  puts $f "endpoint\tstartpoint\tslack_ns\tendpoint_partition"
  foreach_in_collection path $paths {
    set end [get_object_name [get_attribute $path endpoint]]
    set start [get_object_name [get_attribute $path startpoint]]
    set part other
    if {[string match {pageManager/*} $end]} {set part page_manager}
    puts $f "$end\t$start\t[format %.9f [get_attribute $path slack]]\t$part"
  }
  close $f
  puts "KVZAP_RD1_PM1_SAVED_SETUP_PASS paths=[sizeof_collection $paths] reclaim_pins=[sizeof_collection $reclaim] period_ns=2"
  exit 0
} message options]} {
  puts stderr "KVZAP_RD1_PM1_SAVED_SETUP_FAIL $message"
  if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
  exit 1
}
