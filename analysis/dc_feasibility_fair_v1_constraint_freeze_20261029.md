# `dc_feasibility_fair_v1` constraint freeze — 2026-10-29

**Status:** `approved_static_coverage_pending_DC_tool_coverage`.

This is the approved numerical baseline for the first paired control-top DC
feasibility experiment.  It applies identically to
`full_kv_control_projection` and `route_a_control_projection`; it is not a
target operating point, physical I/O model, macro selection, or PPA claim.
The machine-readable source of truth is
[`dc_feasibility_fair_v1.json`](../hardware/route_a/dc/dc_feasibility_fair_v1.json).

| Constraint | Value | Fairness treatment |
| --- | ---: | --- |
| Period | 2.0 ns | Same named `clock` on both tops |
| Setup / hold uncertainty | 0.10 / 0.02 ns | Same SSG guardband, without copying setup uncertainty into hold |
| Input / output delay | 0.20 / 0.20 ns | Applied to all ordinary top inputs/outputs in each contour |
| Input transition | 0.05 ns | Same generic input-edge assumption; no invented pad driver cell |
| Output load | 0.005 pF | Same lightweight feasibility load; not HBM, package, PHY or system interconnect |
| Library | TSMC28 LVT SSG 0.81 V / 125 C | Existing feasibility-library candidate, SHA-256 frozen in the manifest |

Clock is the only input excluded from input delay/transition.  Reset is a
synchronous, normally timed input; neither top receives a false-path or
multicycle exception.  Every typed external service port is likewise included
in ordinary synchronous top-I/O coverage.  Route-A's larger interface and
additional fanout remain part of its own constraint workload; no dummy
Full-KV port is added to fabricate cancellation.

## Coverage evidence and remaining observation

The coverage checker parses the exact frozen archive and emits a separate
report for each top with port counts, excluded clock, timed reset, and any
unconstrained ports.  Before DC, it can prove the manifest/HDL/Tcl collection
contract only.  The report deliberately lists DC ignored constraints and
unconstrained paths as deferred: the first authorized DC run must produce
`check_timing`, `report_constraint -all_violators`, and explicit
unconstrained/ignored-constraint evidence.

## Array and external-boundary consistency rule

The input rule is frozen but is not yet physically materialized: M2, P3, R5
and S2 may black-box only their typed array interiors.  Parent RMW, atomic
prepare/commit/abort, READY, credit, stale, reclaim, fault, adapters, muxes
and fanout remain control RTL.  The current emitted HDL has not yet replaced
those interiors with generic black-box stubs, so this is an input-readiness
blocker—not permission to synthesize large behavioral arrays as free logic.

`external_core_mem_if_v1`, P3 pending backing, R5 descriptor service, sidecar,
partial provider and R4 are already real typed top-level boundaries, not
unresolved internal modules.  A later DC harness may add only
interface-conformant stubs.  Every such service and every array interior
remains nonzero/unestimated; S2 stays non-cancellable.

Therefore the numerical constraint baseline is frozen and static coverage can
pass, but DC-feasibility **input readiness remains blocked** until the bounded
array-interior black-box/stub realization is implemented and checked.
