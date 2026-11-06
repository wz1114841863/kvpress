# WCG1 library-only metadata probe. No design input, compile or clock change.
if {[catch {
  set db $::env(KVZAP_DC_TARGET_LIBRARY)
  set out $::env(KVZAP_WCG1_LIBRARY_OUT)
  if {![file isfile $db]} { error "missing library" }
  if {[file exists $out]} { error "refusing to overwrite output: $out" }
  file mkdir $out
  read_db $db
  redirect [file join $out lib_cell_attributes.rpt] {
    list_attributes -application -class lib_cell
  }
  redirect [file join $out lib_pin_attributes.rpt] {
    list_attributes -application -class lib_pin
  }
  proc wcg1_optional_attribute {object name} {
    set value [get_attribute -quiet $object $name]
    if {$value eq ""} { return "UNKNOWN" }
    return $value
  }
  set rows [open [file join $out cells.tsv] w]
  puts $rows "cell\tarea\tcp_capacitance\td_capacitance\te_capacitance\tq_max_capacitance\tdont_use\tclock_gating_integrated_cell"
  set names {}
  foreach drive {1 2 4} {
    lappend names "EDFQD${drive}BWP12T30P140LVT" "DFQD${drive}BWP12T30P140LVT"
  }
  foreach drive {1 2 3 4 6 8 12 16 20 24} {
    lappend names "CKLNQD${drive}BWP12T30P140LVT"
  }
  set count 0
  set gate_count 0
  foreach name $names {
    set cell [get_lib_cells -quiet "*/$name"]
    if {[sizeof_collection $cell] != 1} { error "expected one library cell: $name" }
    set full [get_object_name $cell]
    set area [get_attribute $cell area]
    if {![string is double -strict $area] || $area <= 0} { error "invalid area for $name" }
    set values [list $name $area]
    foreach pair {{CP capacitance} {D capacitance} {E capacitance} {Q max_capacitance}} {
      set pin [get_lib_pins -quiet "$full/[lindex $pair 0]"]
      set value "NA"
      if {[sizeof_collection $pin] == 1} {
        set value [wcg1_optional_attribute $pin [lindex $pair 1]]
      }
      lappend values $value
    }
    lappend values [wcg1_optional_attribute $cell dont_use]
    lappend values [wcg1_optional_attribute $cell clock_gating_integrated_cell]
    puts $rows [join $values "\t"]
    incr count
    if {[string match "CKLNQ*" $name]} { incr gate_count }
    set library_name [lindex [split $full /] 0]
  }
  close $rows
  set identity [open [file join $out library_identity.tsv] w]
  puts $identity "metric\tvalue"
  puts $identity "library_name\t$library_name"
  puts $identity "library_db\t$db"
  puts $identity "capacitance_unit_policy\tnative_library_units_for_all_compared_pins"
  close $identity
  if {$count != 16 || $gate_count != 10} { error "incomplete cell inventory" }
  puts "KVZAP_WCG1_LIBRARY_METADATA_PASS cells=$count gates=$gate_count"
  exit 0
} message options]} {
  puts stderr "KVZAP_WCG1_LIBRARY_METADATA_FAIL $message"
  if {[dict exists $options -errorinfo]} { puts stderr [dict get $options -errorinfo] }
  exit 1
}
