# Paired DC feasibility run — R5 descriptor-externalized successor

**Status:** `tool_feasibility_pass_timing_and_cleanliness_blocked` (completed
2026-10-30).

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

## Launch and completion state

The runner started only after the descriptor-externalized 48-file Route-A
successor passed the array-proxy, source/filelist, archive/library and static
constraint checks.  It uses five same-header array-interior proxies and retains
all named parents in the HDL filelists.

The immutable run completed with all three required runner markers:

- `KVZAP_DC_FEASIBILITY_FULL_KV_EXIT=0`;
- `KVZAP_DC_FEASIBILITY_ROUTE_A_EXIT=0`;
- `KVZAP_DC_FEASIBILITY_RUN_PASS run_id=dc_feasibility_fair_r5desc_20261029_r1`.

Both DDC and mapped-Verilog outputs exist. The source archive SHA-256, the
candidate TSMC28 library SHA-256, and both checked proxy-report SHA-256 values
are recorded in `input_sha256.txt`. The detailed disposition is
[`dc_feasibility_result_r5_descriptor_externalized_20261030.md`](dc_feasibility_result_r5_descriptor_externalized_20261030.md).

## Required completion evidence

The completed result required inspection of both top-level directories for:

1. a zero per-top runner exit marker and the final run-level marker;
2. `check_design`, `check_timing`, port/constraint, reference and array-proxy
   reports;
3. native unconstrained/ignored-constraint diagnostics and actual linked
   black-box treatment;
4. the generated netlist/DDC artifacts and input SHA record.

That review passes the narrow tool/link/proxy provenance gate, but does not
pass timing closure or a clean structural-lint gate. It still does not
constitute macro selection, physical-array realization, power/PPA,
external-service-zero-cost, throughput or net-benefit evidence.
