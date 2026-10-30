# DC feasibility result — R5 descriptor-externalized successor

**Disposition:** `tool_feasibility_pass_timing_and_cleanliness_blocked`.

This is the first actual DC run for the descriptor-externalized paired control
projections. It establishes that the frozen source can be analyzed, linked,
compiled and emitted by DC under the common fair-v1 constraint baseline. It
does not establish timing closure, a clean implementation boundary, macro
realization, area/PPA, common-cost cancellation or system benefit.

## Provenance and runner integrity — pass

Run `dc_feasibility_fair_r5desc_20261029_r1` on `dc-server` ended with
`FULL_KV_EXIT=0`, `ROUTE_A_EXIT=0`, and the run-level `RUN_PASS` marker.

| Item | Verified value |
| --- | --- |
| candidate standard-cell DB SHA-256 | `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d` |
| R5-externalized source archive SHA-256 | `9d58f0df438555dba433390b9db2c4f5a1e85fee67e431d142b60d026b810093` |
| Full-KV source closure | one SV file, one retained `full_kv_s2_payload_array_boundary` proxy |
| Route-A source closure | 48 SV files, four retained M2/P3/R5/S2 array-interior proxies |
| R5 externalization in mapped Route-A HDL | typed request/response top ports and `route_a_page_manager` remain; `descriptorEntryImage`, `descriptorReadable`, and `descriptorValidRecords` are absent |

Both sides emitted a DDC and mapped Verilog. DC reports no `Error:` records,
and the required same-header proxy instances remain `dont_touch`. The
black-box count is exactly one for Full-KV and four for Route-A; that is the
approved array-interior scope, not a missing linked design.

## Common-constraint timing diagnostic

The common constraints remain unchanged: 2.0 ns period, 0.10/0.02 ns
setup/hold uncertainty, 0.20 ns input/output delay, 0.05 ns input transition,
and 0.005 pF output load. They deliberately apply equally to both top-levels.

| Metric | Full-KV | Route-A |
| --- | ---: | ---: |
| setup WNS | 0.00 ns | -0.31 ns |
| setup TNS | 0.00 ns | -7318.06 ns |
| setup violating paths | 0 | 34,814 |
| hold violations | 0 | 0 |
| max-transition/capacitance nets | 0 / 0 | 0 / 0 |
| critical logic levels | 109 | 126 |

Full-KV merely meets this feasibility constraint with no setup margin. Route-A
does not: its worst paths run from the common R1/R2 arbitration state into the
external core-memory request boundary and many M2/P3 materialized-member
registers. The fair-v1 numerical profile must not be relaxed selectively to
make this pass.

The `min_capacitance` entries labelled "increase significant digits" have zero
rounded required/actual capacitance. They are report-precision artefacts in
this zero-net-area feasibility model, not max-capacitance DRC failures; the QoR
reports zero nets with max-capacitance or max-transition violations.

## Structural-lint and optimization diagnostic — blocked

`check_timing` does not report a clock-loop, missing input-delay, or
unconstrained-endpoint diagnostic. However, post-compile `check_design` is
not clean:

| Post-compile category | Full-KV | Route-A |
| --- | ---: | ---: |
| unconnected hierarchical ports | 893 | 25,572 |
| feedthroughs | 1,665 | 22,788 |
| shorted outputs | 393 | 7,114 |
| constant outputs | 2 | 922 |
| total `Warning:` records | 3,010 | 56,677 |

These warnings have no DC `Error:` counterpart, and source-level structural
checks still prove the critical R3/R6 authority connection and the required
typed external boundaries. They therefore do **not** demonstrate an illegal
source tie-off. They do demonstrate that the present generic projection and
its broad external interfaces leave a large hierarchical lint/optimization
surface. A later acceptance must classify each relevant channel as retained,
intentional typed external, or accidental dead/unconnected logic before a
cost comparison is credible.

Two further cautions reinforce that boundary:

- DC uses its fanout-1000 timing assumption for two high-fanout nets on each
  top. The Route-A direct-pending issue net has 1,298,154 loads, so the
  reported delay is a feasibility diagnostic rather than physical routing
  timing.
- All five array proxies report zero black-box area and wire load has zero net
  area. External memory, descriptor, sidecar, partial and numeric services
  also remain `nonzero_unestimated`; the raw cell areas are not comparable
  PPA totals.

## Size diagnostic, not an area result

DC maps 23,091.43 library-area units for Full-KV and 6,716,537.64 for Route-A
(about 290.9x). That value must not be treated as a Route-A cost result. It is
useful only to localize the next realization risk: `route_a_m2_p3_wrapper`
(44.2%), `route_a_metadata_admission_bridge` (42.2%), and
`route_a_page_manager` (6.1%) make up 92.5% of the mapped Route-A control
area. Their extensive full-profile per-entry control/state is intentionally
retained outside the array proxies, so this run correctly exposes the cost of
the current realization choice rather than silently black-boxing it.

## Required follow-up before any DC cost comparison

1. Create a bounded lint/retention disposition for the high-volume Route-A
   warnings, starting with R6/lifecycle, M2 control, delivery routing and the
   typed external boundaries. Do not simply suppress warnings.
2. Trace the high-fanout direct-pending and materialized-member paths, then
   decide whether a legal control representation/refinement is needed. Keep
   the fair-v1 numerical constraints unchanged during that diagnosis.
3. Re-run a successor DC feasibility only after the selected fixes and
   structural assertions prove that no required owner/control has been
   optimized away. Macro/proxy area, physical port/timing realization,
   external-service cost and power remain later, separately authorized work.
