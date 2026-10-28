#!/usr/bin/env bash
# Static check of the parameterized constraint contract.  It neither sources
# DC nor selects numerical values; the check guards the generated HDL's actual
# top-port names and prevents accidental asynchronous-reset false paths.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env_kvzap_control_projection_dc.sh
source "$script_dir/env_kvzap_control_projection_dc.sh"
constraint_tcl="$script_dir/constraints_control_projection.tcl"

fail() { printf 'KVZAP_DC_CONSTRAINT_CONTRACT_FAIL: %s\n' "$*" >&2; exit 1; }
note() { printf 'KVZAP_DC_CONSTRAINT_CONTRACT: %s\n' "$*"; }
[[ -f "$constraint_tcl" ]] || fail "missing constraints Tcl: $constraint_tcl"

for variable in \
  KVZAP_DC_CLOCK_PERIOD_NS KVZAP_DC_CLOCK_SETUP_UNCERTAINTY_NS \
  KVZAP_DC_CLOCK_HOLD_UNCERTAINTY_NS KVZAP_DC_INPUT_DELAY_NS \
  KVZAP_DC_OUTPUT_DELAY_NS KVZAP_DC_INPUT_TRANSITION_NS KVZAP_DC_OUTPUT_LOAD_PF; do
  grep -Fq "$variable" "$constraint_tcl" || fail "constraint variable absent: $variable"
done
grep -Fq 'create_clock -name kvzap_control_clk' "$constraint_tcl" || fail "missing named clock"
grep -Fq 'set_clock_uncertainty -setup' "$constraint_tcl" || fail "missing setup uncertainty"
grep -Fq 'set_clock_uncertainty -hold' "$constraint_tcl" || fail "missing hold uncertainty"
grep -Fq 'set_input_delay' "$constraint_tcl" || fail "missing input delay"
grep -Fq 'set_output_delay' "$constraint_tcl" || fail "missing output delay"
grep -Fq 'set_input_transition' "$constraint_tcl" || fail "missing input transition"
grep -Fq 'set_load' "$constraint_tcl" || fail "missing output load"
if grep -Eq '^[[:space:]]*set_false_path' "$constraint_tcl"; then
  fail "synchronous reset must not be hidden by set_false_path"
fi

archive="$KVZAP_DC_HDL_ARCHIVE"
[[ -f "$archive" ]] || fail "missing frozen HDL archive: $archive"
for member in full_kv_control_projection.sv route_a_control_projection_split/route_a_control_projection.sv; do
  # Do not use grep -q here: with pipefail, an early grep exit sends SIGPIPE
  # to tar while it is streaming a large generated SV and creates a false
  # negative despite a valid top-port match.
  tar -xOf "$archive" "$member" | grep -E '^[[:space:]]*(input|output)[[:space:]]+.*(clock|reset)' >/dev/null || fail "cannot observe clock/reset in $member"
  note "$member has top-level clock/reset declaration"
done

if command -v tclsh >/dev/null 2>&1; then
  tclsh "$constraint_tcl"
fi
printf '%s\n' 'KVZAP_DC_CONSTRAINT_CONTRACT_PASS: parameterized synchronous clock/reset and I/O contract is structurally valid; dc_feasibility_fair_v1 numerical defaults are separately manifest-verified.'
