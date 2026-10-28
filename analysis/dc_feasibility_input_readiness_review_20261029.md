# DC feasibility input-readiness review — 2026-10-29

**Status:** `blocked_only_by_array_interior_blackbox_materialization`.

This bounded review does not reopen Route-A architecture or run DC. It asks
whether the exact paired control-projection HDL can enter DC without silently
changing scope or counting unmodeled hardware as free.

## Passed input checks

| Required check | Evidence | Result |
| --- | --- | --- |
| Numerical profile, library and source integrity | `hardware/route_a/dc/dc_feasibility_fair_v1.json` records the seven approved values, library corner, archive/library/constraint hashes and independent filelists. | PASS |
| Clock/reset/I-O classification | `constraints_control_projection.tcl` creates only `kvzap_control_clk`; clock alone is excluded; synchronous reset is timed; no false-path or multicycle exception exists. | PASS |
| Actual static coverage | `dc_feasibility_fair_v1_constraint_coverage_20261029.json` finds Full-KV 41 ordinary inputs/36 outputs and Route-A 244/115, all collection-covered. | PASS |
| Output-load qualification | 0.005 pF is explicitly a lightweight top-level feasibility load, not HBM/package/PHY/system-interconnect load. | PASS |
| External boundary/filelist rule | Filelists are exact and separate; core memory, P3/R5 service, sidecar, partial and R4 remain typed top boundaries and nonzero/unestimated. | PASS |

## Correctly deferred observations

No DC tool has elaborated either top. Actual `check_timing`,
`report_constraint -all_violators`, unconstrained-path and ignored-constraint
reports are therefore `deferred_until_DC_check_timing_and_report_constraint`,
not falsely reported as empty.

## Blocking condition

The generated HDL still contains behavioral M2/P3/R5/S2 array interiors. The
frozen rule permits only those interiors to become generic typed
black-box/proxy modules. Parent RMW, prepare/commit/abort, credit, READY,
stale, reclaim, fault, adapters, muxes and fanout must remain in projected RTL.

That generic black-box materialization has **not** been implemented. Synthesizing
behavioral arrays as ordinary logic answers a different question; black-boxing
a whole boundary incorrectly discards retained control cost. Thus external
service treatment is consistent, but the paired package is not DC-admissible.

## Acceptance conclusion

`dc_feasibility_fair_v1` and static coverage are accepted as frozen pre-DC
constraints. **DC input readiness is BLOCKED solely by typed array-interior
black-box/proxy materialization for M2, P3, R5 and S2.** The next work must
preserve the parent access contracts and produce successor filelists plus
structural/semantic non-regression. Only then may an authorized DC run emit the
deferred native tool reports.
