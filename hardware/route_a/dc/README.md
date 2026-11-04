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

The following remain deliberately unselected:

- typed external-service stubs for memory, sidecar, partial and R4 services.

M2/P3/R5/S2 array interiors are now materialized separately as same-header
`syn_black_box` proxies by `materialize_dc_array_proxies.py`; see
[`analysis/dc_array_proxy_materialization_20261029.md`](../../../analysis/dc_array_proxy_materialization_20261029.md).
This preserves parent control and does not select a macro, latency, or physical
cost. Each future DC top must use its own frozen `.f`; do not combine the two filelists because the
independent generated units define common module names.  See
[`analysis/paired_control_projection_hdl_freeze_20261028.md`](../../../analysis/paired_control_projection_hdl_freeze_20261028.md)
for the HDL, source and evidence boundary.

## Constraint contract

The reconstructed R3 entry-id repair uses the explicit
`run_m2p3_compact_entry_id_repair_dc.sh IMMUTABLE_RUN_ID` launcher.  See
[`dc_entry_id_driver_repair_20261104.md`](../../../analysis/dc_entry_id_driver_repair_20261104.md)
for the opt-in `r3_entry_id_driver_v1` policy, focused mapped regression and
production acceptance gate.  It preserves only 24 internal result nets and
requires a real driver on both 24-bit outputs after mapping.  No RTL or timing
constraint changes are made, but the preservation may affect QoR and is
recorded in each new run.  The general runner retains policy `none` by default.

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
