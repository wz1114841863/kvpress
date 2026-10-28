# KVZap paired control-projection DC environment

This directory is the reproducible **environment preflight** for the two
generated control-projection HDL units.  It is intentionally not a DC run
script: it performs no `analyze`, `elaborate`, `link`, `compile`, timing,
area, power, CACTI, or PPA action.

On the current EDA server, run:

```bash
source hardware/route_a/dc/env_kvzap_control_projection_dc.sh
hardware/route_a/dc/check_kvzap_control_projection_dc_env.sh
```

The preflight verifies the explicit DC executable, its version, the candidate
standard-cell `.db`, the frozen HDL archive SHA-256, and the independent
Full-KV (1 SV) and Route-A (182 SV) filelists.  The default library is the
existing H3 flow's TSMC28 LVT SSG `.db`; it is a feasibility-environment
default only, not a selected PPA corner or a design decision.  Every path can
be overridden through the exported `KVZAP_DC_*` variables.  The sourceable
environment also supplies the server's existing license-server endpoint only
when `LM_LICENSE_FILE` is otherwise unset; it stores no credential or license
file and can be overridden with `KVZAP_DC_LICENSE_FILE`.

It deliberately reports the following as `unselected`:

- array-interior/black-box materialization for M2, P3, R5 and S2;
- typed external-service stubs for memory, sidecar, partial and R4 services.

Those remain required DC-feasibility inputs.  Each future DC top must use its
own frozen `.f`; do not combine the two filelists because the
independent generated units define common module names.  See
[`analysis/paired_control_projection_hdl_freeze_20261028.md`](../../../analysis/paired_control_projection_hdl_freeze_20261028.md)
for the HDL, source and evidence boundary.

## Constraint contract

`constraints_control_projection.tcl` is a parameterized, single-clock
constraint procedure for either selected top.  The approved
`dc_feasibility_fair_v1` manifest supplies a 2.0 ns period, 0.10/0.02 ns
setup/hold uncertainty, 0.20 ns input/output delays, 0.05 ns input transition
and 0.005 pF output load.  These are identical for both tops and are a control
feasibility baseline, not a target frequency or system-I/O model.
The only frozen top-level facts are one `clock` and one synchronous `reset`;
reset remains timed as an input and is not marked false-path.  Check the
contract without DC via:

```bash
hardware/route_a/dc/check_kvzap_control_projection_constraints.sh
```

The procedure is sourced and called only after a future DC run has analyzed
and elaborated one top.  Supplying its numerical values and running that Tcl
still require the separate DC-feasibility authorization.

Generate the frozen static coverage report on the EDA server without invoking
DC:

```bash
hardware/route_a/dc/check_kvzap_control_projection_dc_feasibility_fair_v1.sh
```

It verifies that no clock/reset exception is hidden, clock is the only
input-delay exclusion, reset is a timed ordinary input, and all other actual
top ports fall under the collection-based constraint rule.  DC's own ignored
constraint and unconstrained-path reports remain required after authorization.
