# Paired control-projection constraint contract — 2026-10-29

**Status:** `parameterized_contract_ready_numerical_profile_unselected`.

This record implements the second pre-DC item: a clock/reset/I-O constraint
contract for the already frozen `full_kv_control_projection` and
`route_a_control_projection` HDL tops.  It is a contract and static check,
not a DC run and not a timing/PPA result.

## Fixed interface facts

Both generated roots expose exactly one port named `clock` and one named
`reset`.  The selected control projection assumes one ordinary synchronous
clock/reset domain; a separate asynchronous reset or CDC is not selected.
Therefore the constraint Tcl times `reset` as an ordinary input and does not
use `set_false_path` to hide reset timing.

All typed outer interfaces—including `external_core_mem_if_v1`, sidecar,
partial and R4 boundaries—are constrained as synchronous top-level inputs or
outputs in this control-only feasibility contract.  This does not implement
those services or claim their physical latency; their service/cost treatment
remains a later external-boundary decision.

## Required numerical fields

`hardware/route_a/dc/constraints_control_projection.tcl` refuses to run until
the DC run manifest supplies positive values for:

| Environment variable | Meaning |
| --- | --- |
| `KVZAP_DC_CLOCK_PERIOD_NS` | named `kvzap_control_clk` period |
| `KVZAP_DC_CLOCK_SETUP_UNCERTAINTY_NS` | setup uncertainty |
| `KVZAP_DC_CLOCK_HOLD_UNCERTAINTY_NS` | hold uncertainty |
| `KVZAP_DC_INPUT_DELAY_NS` / `KVZAP_DC_OUTPUT_DELAY_NS` | synchronous top-level I/O delays |
| `KVZAP_DC_INPUT_TRANSITION_NS` | top-level input transition assumption |
| `KVZAP_DC_OUTPUT_LOAD_PF` | top-level output load assumption |

No number is inherited from H3 or other decoder experiments.  Consequently,
this package does not select frequency, output load, drive cell, timing corner
or PPA target.  The library remains the separately recorded feasibility
candidate from `dc_environment_preflight_20261029.md`.

## Validation and next condition

`check_kvzap_control_projection_constraints.sh` checks both frozen HDL roots,
all required Tcl variables and commands, and rejects an accidental synchronous
reset false path. It may run without DC; its required variables are supplied
by the separately frozen `dc_feasibility_fair_v1` manifest/environment.

The remote static contract check passed on 2026-10-29 for both actual generated
top roots.  `tclsh` is not installed on the EDA server, so no standalone Tcl
interpreter was invoked; this is intentionally not replaced with a DC launch.
The first separately authorized DC-feasibility Tcl must source this unchanged
file after elaboration, which also supplies the authoritative DC parser check.

Before a DC-feasibility invocation, the owner must approve and freeze one
numerical profile equally applicable to the two comparison runs.  Array
black-box treatment and external typed-service stubs remain separate required
inputs; this constraint contract does not decide either.
