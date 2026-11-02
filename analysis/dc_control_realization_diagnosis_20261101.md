# Route-A DC control-realization diagnosis — 2026-11-01

## Scope and evidence

This is a read-only diagnosis of the completed
`dc_feasibility_fair_r5desc_20261029_r1` result.  It uses the saved DDC,
mapped HDL, hierarchy, timing and `check_design` reports; it does not rerun
the frozen DC configuration and is not a PPA result.

## Mapped state and area concentration

| hierarchy | leaf cells | sequential cells | mapped area share |
| --- | ---: | ---: | ---: |
| `route_a_m2_p3_wrapper` | 2,380,199 | 476,140 | 44.2% |
| `route_a_metadata_admission_bridge` | 1,332,508 | 662,404 | 42.2% |
| `route_a_page_manager` | 383,681 | 62,000 | 6.1% |
| `route_a_m2_production_control_owner` | 117,190 | 33,168 | 2.8% |

The Route-A top contains 1,298,150 mapped sequential cells.  The first two
hierarchies therefore contain 87.7% of all mapped state and 86.4% of mapped
cell area.  This is primarily a state-representation problem, not only a
Boolean-optimization problem.

`route_a_metadata_admission_bridge` accounts exactly as follows under the
frozen profile:

- the duplicate `36 x 64 x 281-bit` `PendingPayloadReadBinding` ledger is
  647,424 bits;
- all other group, credit, sequence/tail and held-prepare state is 14,980
  bits;
- their sum is the DDC-observed 662,404 sequential cells.

The full binding is already retained by the R3/P3 membership owner.  M2 only
uses `layer/head/tag/valid_records/ordinal/mapping_ref/mapping_owner` to
validate a group before lowering.  Retaining payload identity, payload
handle, source generation and destination for all 2,304 slots in the metadata
bridge is therefore duplicate state.  Its dynamic whole-Vec read also creates
a 36-way mux for 64 wide bindings.

`route_a_m2_p3_wrapper` separately declares full `36 x 64`
`AdmissionContext` and `PendingPayloadReadBinding` tables plus present and
materialized bitmaps.  The source declaration envelope exceeds 960 Kbits;
DC prunes unused fields to 476,140 mapped state bits, while dynamic layer and
ordinal selection plus the 36-by-64 materializer candidate masks remain a
major combination-network source.  That owner needs a later banked/indexed
ledger refinement; it is not changed in the first sub-batch.

## High fanout and lint classification

The reported `directPendingIssue/net188753` has 1,298,154 leaf loads, exactly
the 1,298,150 mapped sequential cells plus four control loads.  The named
`directPendingIssue` hierarchy itself has only 16 combinational leaf cells and
zero sequential cells, and the transient compile net is not retained under
that name in either the written DDC or mapped HDL.  DDC fanout probes identify
the source exactly: the top-level clock reaches 1,298,154 endpoint cells,
whereas synchronous reset reaches 67,632 endpoint objects.  Thus
`directPendingIssue/net188753` is a compiler-generated clock-distribution
alias whose transient hierarchy name is misleading, not a direct-pending
transaction field broadcast to 1.3 million semantic consumers.  The first
state reduction should reduce this clock load naturally.  A later physical
clock-tree implementation remains nonzero work, but registering a
direct-pending carrier would not address this warning.

The 56,677 post-compile warnings are dominated by typed-carrier expansion:

- `route_a_m2_production_control_owner`: 11,729 `LINT-28`, largely fields of
  the 64 full bindings that M2 does not consume;
- `route_a_r4_external_protocol_adapter`: 8,375 `LINT-29`, intentional typed
  external-boundary feedthrough;
- lifecycle/S2/page-manager `LINT-28`: mostly unused payload/value or response
  fields, but identity/status subsets require later per-port review;
- router/demux/adapter `LINT-29` and `LINT-31`: mostly intentional typed
  feedthrough/fanout, not evidence that the path is active or dead;
- 4 `LINT-55`: the approved array-interior proxies.

Thus lint count alone is not a deletion license.  The first refinement removes
only a proved duplicate carrier/state representation and adds explicit
mapping-provenance checks at the accepting owner.

## First refinement and expected structural effect

The selected change replaces the metadata bridge's duplicate full binding
ledger with one immutable mapping reference, one mapping owner and the existing
64-bit accepted-member mask per group.  R3/P3 remains the full membership
owner; M2 still checks the exact mask and all preparation fields it consumes.
Later members and preparation with mismatched mapping provenance fail closed.

Using the prior DDC count, the predicted mapped metadata-bridge state is
17,392 bits.  The deterministic representation reduction is 645,012 bits
(97.4% inside this module and 49.7% of the prior Route-A total), before a new
DC run.  This is a control-realization refinement, not a zero-cost memory
proxy or a change to admission,
publication, authority, ordering, lifecycle, fault or reset semantics.

The result must pass directed and cross-stage Chisel regressions before
generated-HDL structural checks and a same-constraint successor DC run.  No
mapped-area, fanout, timing or lint improvement is claimed before that run.

## First-sub-batch validation

The source-level refinement passed the remote directed run in
`kvzap-control-refine:p1`; the preserved log is
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/control_refine_p1_20261101.log`.
Scala compilation completed and the two production suites passed 8/8 actual
tests: three metadata-admission tests (including immutable mapping-provenance
mismatch) and five grouped M2 control-owner tests.

The local executable structural checks passed 3/3 for this refinement, 2/2
for the existing M2 array-only boundary, and 3/3 for synthesis-top candidate
scope.  The BOM parses as JSON and `git diff --check` passes.

The first cross-stage P2 attempt passed 37/41 tests.  Its four
`RouteAMeasurementDutR3Spec` cases first exposed an undriven dormant R5
descriptor-service port in the non-projection measurement mode; after that
was initialized fail-closed, Verilator exposed the already documented
ChiselSim long-name mismatch for unused deep sidecar-root DPI fields.  The
bounded repair keeps the complete, unchanged `RouteAMeasurementDut` as the
only child of a simulator-facing root and hides only those unused outer ports
from the DPI ABI.  Remote P4 then executed and passed all four behavioral
cases in `control_refine_p4_r3_harness_20261102.log`.

The clean complete P2 rerun then passed all 10 suites and 41/41 actual tests
with `KVZAP_CONTROL_REFINE_P5_FULL_P2_EXIT=0`; the preserved log is
`control_refine_p5_full_p2_20261102.log`.  This accepts the functional
cross-stage gate on the latest source.

The regenerated 48-file successor subsequently passed the source closure,
owner/port/control and typed-array checks recorded in
[`dc_control_refinement_successor_20261102.md`](dc_control_refinement_successor_20261102.md).
Its raw generated metadata bridge contains 17,492 logical state bits versus
662,504 in the old raw successor, an observed source-level reduction of
645,012 bits.  The 100-bit difference from the DDC-based 17,392 estimate is
kept explicit; the same-constraint successor DC comparison remains required
before any mapped-state, area, fanout, lint or timing improvement is claimed.
