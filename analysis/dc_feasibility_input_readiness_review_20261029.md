# DC feasibility input-readiness review — 2026-10-29

**Status:** `superseded_by_array_proxy_materialization_pass`.

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

## Historical blocking condition (resolved)

The generated HDL still contains behavioral M2/P3/R5/S2 array interiors. The
frozen rule permits only those interiors to become generic typed
black-box/proxy modules. Parent RMW, prepare/commit/abort, credit, READY,
stale, reclaim, fault, adapters, muxes and fanout must remain in projected RTL.

That generic black-box materialization is now implemented as a deterministic
successor.  See
[`dc_array_proxy_materialization_20261029.md`](dc_array_proxy_materialization_20261029.md)
and its machine-readable reports.  Synthesizing behavioral arrays as ordinary
logic still answers a different question, and black-boxing a whole boundary
still incorrectly discards retained control cost.

## Acceptance conclusion

`dc_feasibility_fair_v1`, static coverage and typed array-interior proxy
materialization are accepted as frozen pre-DC inputs. **The package is ready
only for a separately authorized DC-feasibility run.** That run remains the
first evidence for DC parser/elaboration/link behavior and native timing or
constraint reports; this review does not claim any of those results.
