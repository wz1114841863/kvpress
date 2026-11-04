# First paired KVZap control-projection DC feasibility implementation.
#
# It is intentionally a bounded feasibility run: analyze/elaborate/link,
# common frozen constraints, generic typed array black boxes, compile, and
# native tool reports.  It neither selects a physical memory macro nor claims
# power, PPA, common-cost cancellation, or system performance.

proc kvzap_dc_require_env {name} {
  if {![info exists ::env($name)] || [string trim $::env($name)] eq ""} {
    error "$name is required"
  }
  return $::env($name)
}

proc kvzap_dc_read_filelist {filelist root} {
  if {![file exists $filelist]} { error "missing filelist: $filelist" }
  if {![file isdirectory $root]} { error "missing filelist root: $root" }
  set handle [open $filelist r]
  set sources {}
  while {[gets $handle line] >= 0} {
    set line [string trim $line]
    if {$line eq "" || [string match "#*" $line]} { continue }
    if {[file pathtype $line] eq "absolute"} {
      close $handle
      error "filelist uses disallowed absolute entry: $line"
    }
    set source [file normalize [file join $root $line]]
    if {![file exists $source]} {
      close $handle
      error "filelist source missing: $source"
    }
    lappend sources $source
  }
  close $handle
  if {[llength $sources] == 0} { error "empty filelist: $filelist" }
  return $sources
}

proc kvzap_dc_require_array_proxies {modules phase} {
  foreach module $modules {
    set cells [get_cells -quiet -hierarchical -filter "ref_name == $module"]
    if {[sizeof_collection $cells] == 0} {
      error "expected elaborated typed array proxy '$module' is absent during $phase"
    }
    set_dont_touch $cells true
    set_ungroup $cells false
  }
}

proc kvzap_dc_main {} {
  foreach required {
    KVZAP_DC_TOP KVZAP_DC_FILELIST KVZAP_DC_FILELIST_ROOT
    KVZAP_DC_REPORT_DIR KVZAP_DC_TARGET_LIBRARY KVZAP_DC_SCRIPT_DIR
    KVZAP_DC_ARRAY_PROXY_MODULES
  } { kvzap_dc_require_env $required }

  set top $::env(KVZAP_DC_TOP)
  set report_dir [file normalize $::env(KVZAP_DC_REPORT_DIR)]
  set filelist [file normalize $::env(KVZAP_DC_FILELIST)]
  set filelist_root [file normalize $::env(KVZAP_DC_FILELIST_ROOT)]
  set target_libraries [split $::env(KVZAP_DC_TARGET_LIBRARY) ":"]
  set proxy_modules [split $::env(KVZAP_DC_ARRAY_PROXY_MODULES) ","]
  file mkdir $report_dir

  foreach library $target_libraries {
    if {![file exists $library]} { error "target library does not exist: $library" }
  }
  define_design_lib WORK -path [file join $report_dir "work_[pid]"]
  set_app_var target_library $target_libraries
  set_app_var link_library [concat "*" $target_libraries]

  # CIRCT emits verification bind helpers in sibling directories.  They are
  # part of the frozen HDL closure even though DC does not use them for a
  # functional proof.  Add the two legal relative include roots instead of
  # silently dropping verification source or altering generated HDL.
  set verification_root [file join $filelist_root verification]
  set verification_assert_root [file join $verification_root assert]
  set extra_search_path [list $filelist_root]
  if {[file isdirectory $verification_root]} { lappend extra_search_path $verification_root }
  if {[file isdirectory $verification_assert_root]} { lappend extra_search_path $verification_assert_root }
  set_app_var search_path [concat [get_app_var search_path] $extra_search_path]

  set sources [kvzap_dc_read_filelist $filelist $filelist_root]
  analyze -format sverilog -define SYNTHESIS $sources
  elaborate $top
  current_design $top
  link
  kvzap_dc_require_array_proxies $proxy_modules "post-link"

  source [file join $::env(KVZAP_DC_SCRIPT_DIR) constraints_control_projection.tcl]
  kvzap_apply_control_projection_constraints
  source [file join $::env(KVZAP_DC_SCRIPT_DIR) preserve_r3_entry_id_driver.tcl]
  kvzap_preserve_r3_entry_id_driver $top $report_dir
  check_design > [file join $report_dir check_design_precompile.rpt]
  check_timing > [file join $report_dir check_timing_precompile.rpt]
  report_constraint -all_violators > [file join $report_dir constraints_precompile.rpt]

  # Compile retained control under the common feasibility constraints.  The
  # named array proxy cells remain dont_touch and ungroup-disabled, so this
  # does not infer or select a macro implementation.
  compile -map_effort medium
  kvzap_dc_require_array_proxies $proxy_modules "post-compile"
  kvzap_check_r3_entry_id_driver $top $report_dir

  check_design > [file join $report_dir check_design_postcompile.rpt]
  check_timing > [file join $report_dir check_timing_postcompile.rpt]
  report_constraint -all_violators > [file join $report_dir constraints_postcompile.rpt]
  report_clock > [file join $report_dir clocks.rpt]
  report_qor > [file join $report_dir qor.rpt]
  report_area -hierarchy > [file join $report_dir area_hierarchy.rpt]
  report_reference -hierarchy > [file join $report_dir references.rpt]
  report_timing -delay_type max -max_paths 20 -transition_time -nets > [file join $report_dir timing_setup.rpt]
  report_timing -delay_type min -max_paths 20 -transition_time -nets > [file join $report_dir timing_hold.rpt]
  report_port -verbose > [file join $report_dir ports.rpt]

  set proxy_report [open [file join $report_dir array_proxy_instances.rpt] w]
  foreach module $proxy_modules {
    set cells [get_cells -quiet -hierarchical -filter "ref_name == $module"]
    puts $proxy_report "$module instances=[sizeof_collection $cells] treatment=syn_black_box_dont_touch"
  }
  close $proxy_report
  write -format ddc -hierarchy -output [file join $report_dir "${top}.ddc"]
  write -format verilog -hierarchy -output [file join $report_dir "${top}_mapped.v"]
}

if {[catch {kvzap_dc_main} message options]} {
  puts stderr "KVZAP_DC_FEASIBILITY_FAILED: $message"
  if {[dict exists $options -errorinfo]} { puts stderr [dict get $options -errorinfo] }
  exit 1
}
puts "KVZAP_DC_FEASIBILITY_PASS top=$::env(KVZAP_DC_TOP)"
exit 0
