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

- array-interior/black-box treatment for M2, P3, R5 and S2;
- typed external-service stubs for memory, sidecar, partial and R4 services;
- clock/reset and I/O constraints.

Those are the next separately approved DC-feasibility inputs.  Each future DC
top must use its own frozen `.f`; do not combine the two filelists because the
independent generated units define common module names.  See
[`analysis/paired_control_projection_hdl_freeze_20261028.md`](../../../analysis/paired_control_projection_hdl_freeze_20261028.md)
for the HDL, source and evidence boundary.

## Constraint contract

`constraints_control_projection.tcl` is a parameterized, single-clock
constraint procedure for either selected top.  It requires the run manifest to
provide a period, setup/hold uncertainty, input/output delays, input transition
and output load.  It does not default these from a previous decoder project.
The only frozen top-level facts are one `clock` and one synchronous `reset`;
reset remains timed as an input and is not marked false-path.  Check the
contract without DC via:

```bash
hardware/route_a/dc/check_kvzap_control_projection_constraints.sh
```

The procedure is sourced and called only after a future DC run has analyzed
and elaborated one top.  Supplying its numerical values and running that Tcl
still require the separate DC-feasibility authorization.
