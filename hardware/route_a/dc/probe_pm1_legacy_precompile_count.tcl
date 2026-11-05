# Diagnostic-only legacy Page Manager precompile count probe.
# Reads the accepted DDC for its R5 proxy reference, then analyzes a uniquely
# renamed but byte-body-identical frozen legacy child.  Performs no compile,
# change_link, characterize, constraint mutation or mapped-design write.
if {[catch {
  set root $::env(KVZAP_PM1_LEGACY_COUNT_ROOT)
  set ddc $::env(KVZAP_PM1_BASELINE_DDC)
  set legacy_sv $::env(KVZAP_PM1_LEGACY_PROBE_SV)
  set probe_ref route_a_page_manager_legacy_raw_probe
  set proxy_ref route_a_r5_availability_array_boundary
  set expected_registers 62002

  foreach required [list $ddc $legacy_sv] {
    if {![file isfile $required]} { error "missing input: $required" }
  }
  if {[file exists [file join $root work]]} {
    error "refusing to overwrite probe work directory"
  }
  file mkdir [file join $root work]

  set target_libraries [split $::env(KVZAP_DC_TARGET_LIBRARY) ":"]
  define_design_lib WORK -path [file join $root work]
  set_app_var target_library $target_libraries
  set_app_var link_library [concat "*" $target_libraries]
  read_ddc $ddc

  if {![analyze -format sverilog -define SYNTHESIS $legacy_sv]} {
    error "legacy raw probe analyze failed"
  }
  if {[elaborate $probe_ref] eq ""} { error "legacy raw probe elaborate failed" }
  current_design $probe_ref
  if {![link]} { error "legacy raw probe link failed" }

  set register_count [sizeof_collection [all_registers]]
  set proxy_cells [get_cells -quiet -hierarchical * -filter "ref_name == $proxy_ref"]
  redirect [file join $root check_design.rpt] { check_design }
  redirect [file join $root resources.rpt] { report_resources }
  redirect [file join $root references.rpt] { report_reference -hierarchy }
  redirect [file join $root designs.rpt] { list_designs }

  set summary [open [file join $root summary.tsv] w]
  puts $summary "metric\tvalue"
  puts $summary "probe_ref\t$probe_ref"
  puts $summary "precompile_registers\t$register_count"
  puts $summary "r5_proxy_instances\t[sizeof_collection $proxy_cells]"
  close $summary

  if {$register_count != $expected_registers} {
    error "expected $expected_registers legacy precompile registers, found $register_count"
  }
  if {[sizeof_collection $proxy_cells] != 1} {
    error "expected one retained R5 availability proxy in legacy probe"
  }
  puts "KVZAP_PM1_LEGACY_PRECOMPILE_COUNT_PASS registers=$register_count"
} message options]} {
  puts stderr "KVZAP_PM1_LEGACY_PRECOMPILE_COUNT_FAIL $message"
  if {[dict exists $options -errorinfo]} { puts stderr [dict get $options -errorinfo] }
  exit 1
}
exit 0
