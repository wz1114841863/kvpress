# DC successor input preflight — R5 descriptor externalized

**Status:** `preflight_pass_no_DC_run` (2026-10-29).

This record advances the descriptor-externalized Route-A source freeze through
the already-approved typed array-interior proxy transformation.  It does not
run DC, select a physical macro, provide PPA, or change the frozen fair
numerical constraints.

## Selected immutable input

| Item | Value |
| --- | --- |
| source archive SHA-256 | `9d58f0df438555dba433390b9db2c4f5a1e85fee67e431d142b60d026b810093` |
| source record | `r5_descriptor_externalized_successor_input_freeze_20261029.md` |
| proxy manifest | `hardware/route_a/dc/dc_array_proxy_r5_descriptor_externalized_v1.json` |
| proxy root (EDA server) | `/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/qwen3_8b_32k_s1_control_projection_r5_descriptor_externalized_v1_dc_array_proxy_v1_r1` |
| Full-KV filelist | 1 source |
| Route-A successor filelist | 48 sources |
| numerical profile | unchanged `dc_feasibility_fair_v1` (2.0 ns, 0.10/0.02 ns uncertainty, 0.20 ns I/O delay, 0.05 ns transition, 0.005 pF load) |

## Verified transformation

The materializer and independent checker both passed.  Only these five child
modules are empty same-header `syn_black_box` proxies:

- `full_kv_s2_payload_array_boundary`;
- `route_a_m2_entry_array_boundary`;
- `route_a_p3_stage_array_boundary`;
- `route_a_r5_availability_array_boundary`;
- `route_a_s2_payload_sidecar_array_boundary`.

Their named parent controls remain nonempty.  In particular,
`route_a_page_manager` remains in the Route-A filelist and retains descriptor
service requests, append/reclaim sequencing, R2/R1 ordering, stale checks and
availability-release control.  The external R5 descriptor service is a typed
top port and remains `nonzero_unestimated`; no internal service stub is added.

## Preflight result

The remote no-DC checks passed:

1. proxy body/header and retained-parent validation;
2. Full-KV and Route-A filelist closure/top-module checks;
3. library/archive SHA validation;
4. static fair-constraint coverage for both successor top headers.

The environment and runner now select this successor proxy root and the new
48-entry Route-A filelist.  An actual DC run remains a separate action whose
only permitted initial claims are tool feasibility, netlist completeness and
constraint/optimization diagnostics.
