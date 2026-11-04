# Run from a fresh output directory, with KVZAP_DC_SCRIPT_DIR set.
if {[catch {
  set target_library $::env(KVZAP_DC_TARGET_LIBRARY)
  set link_library [list * $target_library]
  source $::env(KVZAP_DC_SCRIPT_DIR)/preserve_r3_entry_id_driver.tcl
  foreach mode {default repaired} {
    remove_design -all
    file mkdir work_$mode
    define_design_lib WORK -path work_$mode
    if {![analyze -format sverilog $::env(KVZAP_DC_SCRIPT_DIR)/tests/entry_id_driver_fixture.sv]} {error "analyze failed"}
    elaborate route_a_control_projection
    current_design route_a_control_projection
    link
    set_app_var enable_keep_signal_dt_net false
    set ::env(KVZAP_DC_ENTRY_ID_DRIVER_POLICY) none
    if {$mode eq "repaired"} {set ::env(KVZAP_DC_ENTRY_ID_DRIVER_POLICY) r3_entry_id_driver_v1}
    kvzap_preserve_r3_entry_id_driver route_a_control_projection [pwd]
    if {![compile -map_effort medium]} {error "compile failed"}
    check_design > ${mode}_check.rpt
    if {$mode eq "default"} {
      set ::env(KVZAP_DC_ENTRY_ID_DRIVER_POLICY) r3_entry_id_driver_v1
      if {![catch {kvzap_check_r3_entry_id_driver route_a_control_projection [pwd]}]} {
        error "negative control unexpectedly passed driver check"
      }
      file rename entry_id_driver_check.rpt default_entry_id_driver_check.rpt
      set ::env(KVZAP_DC_ENTRY_ID_DRIVER_POLICY) none
      puts ENTRY_ID_NEGATIVE_DRIVER_CHECK_REJECTED
    }
    kvzap_check_r3_entry_id_driver route_a_control_projection [pwd]
    write -format verilog -hierarchy -output ${mode}_mapped.v
    puts "ENTRY_ID_FIXTURE_MODE_PASS $mode"
  }
} message]} {puts stderr "ENTRY_ID_FIXTURE_FAIL $message"; exit 1}
puts ENTRY_ID_FIXTURE_PASS
exit 0
