# Paired DC feasibility run — R5 descriptor-externalized successor

**Status:** `running_no_feasibility_conclusion` (2026-10-29).

## Run identity

| Item | Value |
| --- | --- |
| run ID | `dc_feasibility_fair_r5desc_20261029_r1` |
| remote host | `dc-server` (`ercesi413`) |
| tmux | `kvzap-dc-feasibility-r5desc:r1` |
| live log | `/home/yaz80/wz_project/chisel_projects/kvpress/logs/dc_feasibility_fair_r5desc_20261029_r1.log` |
| immutable result root | `/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/dc_feasibility_fair_r5desc_20261029_r1/` |
| source archive SHA-256 | `9d58f0df438555dba433390b9db2c4f5a1e85fee67e431d142b60d026b810093` |
| numerical profile | `dc_feasibility_fair_v1` (identical 2.0 ns constraints) |

## Launch and observed execution state

The runner started only after the descriptor-externalized 48-file Route-A
successor passed the array-proxy, source/filelist, archive/library and static
constraint checks.  It uses five same-header array-interior proxies and retains
all named parents in the HDL filelists.

At this live snapshot, `full_kv` has completed its DC invocation with the
runner marker `KVZAP_DC_FEASIBILITY_FULL_KV_EXIT=0`.  Route-A compilation,
linking and constrained mapping are in progress.  This is not a paired PASS:
the Route-A marker and the run-level marker do not yet exist.

## Required completion evidence

Completion requires inspection of both top-level directories for:

1. a zero per-top runner exit marker and the final run-level marker;
2. `check_design`, `check_timing`, port/constraint, reference and array-proxy
   reports;
3. native unconstrained/ignored-constraint diagnostics and actual linked
   black-box treatment;
4. the generated netlist/DDC artifacts and input SHA record.

Only then may the result be classified as a tool-feasibility disposition.  It
will still not constitute macro selection, physical-array realization,
power/PPA, external-service-zero-cost, throughput or net-benefit evidence.
